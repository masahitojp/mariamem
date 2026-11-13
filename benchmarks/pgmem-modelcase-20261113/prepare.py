from pathlib import Path
import shutil,re
root=Path(__file__).resolve().parents[1]; pg=root/'temp/pgmem/bench/modelcase'; dst=root/'temp/maria'
shutil.copytree(pg,dst,ignore=shutil.ignore_patterns('results','bin'))
p=dst/'go.mod';p.write_text('module github.com/shibukawa/pgmem/bench/modelcase\n\ngo 1.27\n\nrequire github.com/masahitojp/mariamem v0.0.0\nreplace github.com/masahitojp/mariamem => ../../worktree\n')
shutil.rmtree(dst/'cmd')
# Keep all test assertions; MariaDB wire accepts ? placeholders.
for p in (dst/'store').glob('*.go'):
 s=p.read_text();s=re.sub(r'\$\d+','?',s);s=s.replace("lower(?) || '%'","CONCAT(lower(?), '%')")
 s=s.replace('GROUP BY o.id','GROUP BY o.id, o.status, o.total_cents, o.created_at').replace('GROUP BY p.id','GROUP BY p.id, p.name').replace('GROUP BY c.id','GROUP BY c.id, c.name')
 s=s.replace('stock = stock - ? WHERE id = ? AND stock >= ?', 'stock = stock - ? WHERE id = ? AND stock >= ?').replace('it.ProductID, it.Quantity)\n\t\tif err', 'it.Quantity, it.ProductID, it.Quantity)\n\t\tif err')
 s=s.replace('SELECT ?, id, ?, price_cents FROM products WHERE id = ?`, id, it.ProductID, it.Quantity','SELECT ?, id, ?, price_cents FROM products WHERE id = ?`, id, it.Quantity, it.ProductID')
 s=s.replace('UPDATE products p SET stock = p.stock + i.quantity\n\t\t  FROM order_items i\n\t\t WHERE i.order_id = ? AND i.product_id = p.id','UPDATE products p JOIN order_items i ON i.product_id = p.id SET p.stock = p.stock + i.quantity WHERE i.order_id = ?')
 s=s.replace('price_cents * (100 - ?) / 100','FLOOR(price_cents * (100 - ?) / 100)').replace('categoryID, percent)','percent, categoryID)')
 p.write_text(s)
# Minimal MariaDB dialect schema, same rows, FKs, triggers and view.
for p in (dst/'store/migrations').glob('*.sql'):p.unlink()
schema='''CREATE TABLE users(id BIGINT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(255) NOT NULL,email VARCHAR(255) NOT NULL UNIQUE,created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6));
CREATE TABLE categories(id INT AUTO_INCREMENT PRIMARY KEY,name VARCHAR(255) NOT NULL UNIQUE);
CREATE TABLE products(id BIGINT AUTO_INCREMENT PRIMARY KEY,category_id INT NOT NULL,sku VARCHAR(255) NOT NULL UNIQUE,name VARCHAR(255) NOT NULL,price_cents BIGINT NOT NULL CHECK(price_cents>=0),stock INT NOT NULL DEFAULT 0 CHECK(stock>=0),FOREIGN KEY(category_id) REFERENCES categories(id));
CREATE INDEX products_category_id ON products(category_id);
CREATE INDEX products_name_lower ON products(name);
CREATE TABLE orders(id BIGINT AUTO_INCREMENT PRIMARY KEY,user_id BIGINT NOT NULL,status ENUM('pending','paid','shipped','cancelled') NOT NULL DEFAULT 'pending',total_cents BIGINT NOT NULL DEFAULT 0,created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
CREATE INDEX orders_user_id ON orders(user_id);
CREATE INDEX orders_status ON orders(status);
CREATE TABLE order_items(id BIGINT AUTO_INCREMENT PRIMARY KEY,order_id BIGINT NOT NULL,product_id BIGINT NOT NULL,quantity INT NOT NULL CHECK(quantity>0),unit_price_cents BIGINT NOT NULL,FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,FOREIGN KEY(product_id) REFERENCES products(id));
CREATE INDEX order_items_order_id ON order_items(order_id);
CREATE INDEX order_items_product_id ON order_items(product_id);
CREATE TABLE audit_log(id BIGINT AUTO_INCREMENT PRIMARY KEY,order_id BIGINT NOT NULL,old_status VARCHAR(20),new_status VARCHAR(20) NOT NULL,at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6));
CREATE INDEX audit_log_order_id ON audit_log(order_id);
CREATE TRIGGER order_items_total_insert AFTER INSERT ON order_items FOR EACH ROW UPDATE orders SET total_cents=(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=NEW.order_id),updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id;
CREATE TRIGGER order_items_total_update AFTER UPDATE ON order_items FOR EACH ROW UPDATE orders SET total_cents=(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=NEW.order_id),updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id;
CREATE TRIGGER order_items_total_delete AFTER DELETE ON order_items FOR EACH ROW UPDATE orders SET total_cents=(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=OLD.order_id),updated_at=CURRENT_TIMESTAMP(6) WHERE id=OLD.order_id;
CREATE TRIGGER orders_audit_insert AFTER INSERT ON orders FOR EACH ROW INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,NULL,NEW.status);
CREATE TRIGGER orders_audit_update AFTER UPDATE ON orders FOR EACH ROW INSERT INTO audit_log(order_id,old_status,new_status) SELECT NEW.id,OLD.status,NEW.status WHERE NOT(NEW.status <=> OLD.status);
CREATE VIEW user_order_totals AS SELECT u.id AS user_id,u.name,count(o.id) AS orders,COALESCE(sum(o.total_cents),0) AS total_cents FROM users u LEFT JOIN orders o ON o.user_id=u.id AND o.status<>'cancelled' GROUP BY u.id,u.name;
'''
(dst/'store/migrations/0001_all.sql').write_text(schema)
p=dst/'store/seed.go';s=p.read_text().replace('version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now()','version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP')
s=s.replace('tx, err := db.BeginTx(ctx, nil)\n\t\tif err != nil {\n\t\t\treturn err\n\t\t}', 'tx := db')
s=s.replace('tx.Rollback()','/* DDL implicitly commits on MariaDB */').replace('if err := tx.Commit(); err != nil {\n\t\t\treturn err\n\t\t}', '')
a=s.index('\tif _, err := tx.ExecContext(ctx, `\n\t\tINSERT INTO products');b=s.index('\tif err := tx.Commit()',a)
s=s[:a]+'''\tif _,err := tx.ExecContext(ctx, `INSERT INTO products(category_id,sku,name,price_cents,stock) SELECT 1+(seq % ?),CONCAT('SKU-',LPAD(seq,5,'0')),CONCAT('Product ',seq),500+(seq*37)%20000,? FROM seq_1_to_500`,MasterCategories,initialStock);err!=nil{return err}
 if _,err := tx.ExecContext(ctx, `INSERT INTO users(name,email) SELECT CONCAT('user',seq),CONCAT('user',seq,'@example.com') FROM seq_1_to_1000`);err!=nil{return err}
'''+s[b:]
s=s.replace('`ANALYZE`','`ANALYZE TABLE users,categories,products,orders,order_items,audit_log`').replace('reserve.ExecContext(ctx, it.ProductID, it.Quantity)','reserve.ExecContext(ctx, it.Quantity, it.ProductID)')
p.write_text(s)
p=dst/'store/fixture_test.go';s=p.read_text();a=s.index('\t"github.com/jackc/pgx/v5"');b=s.index('\n\t"github.com/shibukawa/pgmem/bench',a)
s=s[:a]+''' "github.com/go-sql-driver/mysql"
 pgmem "github.com/masahitojp/mariamem"
'''+s[b:]
s=s.replace('*pgmem.Server','*pgmem.Database').replace('pgmem.Options{Database: "app"}','pgmem.Options{}').replace('"SHOW server_version"','"SELECT VERSION()"')
a=s.index('\tcfg, err := pgx.ParseConfig');b=s.index('\n}',a)
s=s[:a]+''' cfg,err:=mysql.ParseDSN(s.DSN());if err!=nil{panic(err)}
 cfg.InterpolateParams=false;cfg.MultiStatements=true;cfg.ClientFoundRows=true;cfg.DialFunc=s.DialContext
 c,err:=mysql.NewConnector(cfg);if err!=nil{panic(err)};return sql.OpenDB(c)'''+s[b:]
s=s.replace('f.rec.Set("model", "pgmem")','f.rec.Set("model", "mariamem")')
s=s.replace('\tdone()\n\n\tf.isolated =', '\tdone()\n done=f.rec.Start("reader_fork","fork","setup");srv,err=snap.Fork(ctx);if err!=nil{return err};done()\n\n\tf.isolated =')
p.write_text(s)
# pgx dependency still needed by the unused conventional-server helper? sql.Open only; remove all driver sources.
print(dst)

p=dst/'store/seed.go';p.write_text(p.read_text().replace('defer /* DDL implicitly commits on MariaDB */','defer tx.Rollback()'))

shutil.copy2(root/'temp/pgmem/LICENSE',dst/'UPSTREAM-LICENSE')

p=dst/'store/fixture_test.go';p.write_text(p.read_text().replace('snap, err := srv.Snapshot(ctx, pgmem.SnapshotOptions{})','if err:=srv.WaitDisconnected(ctx);err!=nil{return err}\n snap, err := srv.Snapshot(ctx, pgmem.SnapshotOptions{})'))
