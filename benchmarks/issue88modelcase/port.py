"""Reproduce the bounded MariaDB SQL-dialect port of upstream MIT modelcase."""
from pathlib import Path
import sys,json,hashlib,shutil,re
up=Path(sys.argv[1]);out=Path(__file__).resolve().parent
original=up/'bench/modelcase';prefix='github.com/masahitojp/mariamem/benchmarks/issue88modelcase'
manifest={}
for engine in ('postgres','maria'):
 d=out/engine/'store';d.mkdir(parents=True,exist_ok=True)
 for name in ('store.go','seed.go','read_test.go','write_test.go'):
  p=original/'store'/name;s=p.read_text();manifest[str(p.relative_to(up))]=hashlib.sha256(p.read_bytes()).hexdigest()
  s=s.replace('github.com/shibukawa/pgmem/bench/modelcase/store',prefix+'/'+engine+'/store')
  if engine=='maria':
   if name=='store.go':
    s=s.replace("lower(name) LIKE lower($1) || '%'", "lower(name) LIKE CONCAT(lower($1), '%')")
    s=s.replace('`UPDATE products SET stock = stock - $2 WHERE id = $1 AND stock >= $2`, it.ProductID, it.Quantity','`UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?`, it.Quantity, it.ProductID, it.Quantity')
    s=s.replace('SELECT $1, id, $3, price_cents FROM products WHERE id = $2`, id, it.ProductID, it.Quantity','SELECT ?, id, ?, price_cents FROM products WHERE id = ?`, id, it.Quantity, it.ProductID')
    s=s.replace('UPDATE products p SET stock = p.stock + i.quantity\n\t\t  FROM order_items i\n\t\t WHERE i.order_id = $1 AND i.product_id = p.id','UPDATE products p JOIN order_items i ON i.product_id=p.id SET p.stock=p.stock+i.quantity WHERE i.order_id=$1')
    s=s.replace('price_cents = price_cents * (100 - $2) / 100 WHERE category_id = $1`, categoryID, percent','price_cents = price_cents * (100 - ?) DIV 100 WHERE category_id = ?`, percent, categoryID')
   if name=='seed.go':
    s=s.replace('"sort"','"sort"\n"strings"')
    s=s.replace('version text PRIMARY KEY, applied_at timestamptz', 'version VARCHAR(128) PRIMARY KEY, applied_at TIMESTAMP')
    old='''		if _, err := tx.ExecContext(ctx, string(body)); err != nil {
			tx.Rollback()
			return fmt.Errorf("%s: %w", e.Name(), err)
		}'''
    new='''		for _, statement := range strings.Split(string(body), "\\n-- NEXT\\n") {
            if _,err:=tx.ExecContext(ctx,statement);err!=nil {tx.Rollback();return fmt.Errorf("%s: %w",e.Name(),err)}
        }'''
    assert old in s;s=s.replace(old,new)
    a=s.index('\tif _, err := tx.ExecContext(ctx, `\n\t\tINSERT INTO products');z=s.index('\tif err := tx.Commit()',a)
    s=s[:a]+'''
 values:=[]string{};args:=[]any{}
 for i:=1;i<=MasterProducts;i++ {values=append(values,"(?,?,?,?,?)");args=append(args,1+i%MasterCategories,fmt.Sprintf("SKU-%05d",i),fmt.Sprintf("Product %d",i),500+(i*37)%20000,initialStock)}
 if _,err:=tx.ExecContext(ctx,"INSERT INTO products(category_id,sku,name,price_cents,stock) VALUES "+strings.Join(values,","),args...);err!=nil{return err}
 values=nil;args=nil
 for i:=1;i<=MasterUsers;i++ {values=append(values,"(?,?)");args=append(args,fmt.Sprintf("user%d",i),fmt.Sprintf("user%d@example.com",i))}
 if _,err:=tx.ExecContext(ctx,"INSERT INTO users(name,email) VALUES "+strings.Join(values,","),args...);err!=nil{return err}
'''+s[z:]
    s=s.replace('`ANALYZE`','`ANALYZE TABLE categories, products, users`')
    # Preserve quantity/product ordering in the prepared reserve statement.
    s=s.replace('`UPDATE products SET stock = stock - $2 WHERE id = $1`','`UPDATE products SET stock = stock - ? WHERE id = ?`')
    s=s.replace('reserve.ExecContext(ctx, it.ProductID, it.Quantity)','reserve.ExecContext(ctx, it.Quantity, it.ProductID)')
    # Shared-server resets are not part of this experiment and must not accidentally run.
    a=s.index('func ResetSample(');s=s[:a]+'''func ResetSample(ctx context.Context, db *sql.DB) error {return fmt.Errorf("shared-server reset outside this benchmark")}
'''
   s=re.sub(r'\$\d+','?',s)
  (d/name).write_text('// Derived from pgmem a61005d modelcase, MIT; see ../../UPSTREAM-LICENSE.\n'+s)
 if engine=='postgres':shutil.copytree(original/'store/migrations',d/'migrations',dirs_exist_ok=True)
trace=out/'internal/trace';trace.mkdir(parents=True,exist_ok=True);shutil.copyfile(original/'internal/trace/trace.go',trace/'trace.go')
shutil.copyfile(up/'LICENSE',out/'UPSTREAM-LICENSE');(out/'upstream-files.json').write_text(json.dumps(manifest,indent=2)+'\n')
