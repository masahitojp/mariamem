package store

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"sort"
"os"
"strings"
)

//go:embed migrations/*.sql
var migrations embed.FS

// Migrate applies the SQL files under migrations/ in name order and records
// each in schema_migrations, as a migration tool would.
func Migrate(ctx context.Context, db *sql.DB) error {
	if _, err := db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (version VARCHAR(255) PRIMARY KEY, applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)`); err != nil {
		return err
	}
	entries, err := migrations.ReadDir("migrations")
	if err != nil {
		return err
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
	for _, e := range entries {
		var applied bool
		if err := db.QueryRowContext(ctx, `SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = ?)`, e.Name()).Scan(&applied); err != nil {
			return err
		}
		if applied {
			continue
		}
		body, err := migrations.ReadFile("migrations/" + e.Name())
        if err == nil && os.Getenv("MARIA_AUDIT_OF")=="1" {
          const old = "CREATE TRIGGER orders_audit_update AFTER UPDATE ON orders"
          if strings.Count(string(body),old)!=1 { return fmt.Errorf("expected one audit UPDATE trigger") }
          body=[]byte(strings.Replace(string(body),old,"CREATE TRIGGER orders_audit_update AFTER UPDATE OF status ON orders",1))
        }
        if err==nil && os.Getenv("MODELCASE_MATCHED")=="1" {
         edits:=[][2]string{
          {"old_status VARCHAR(20),new_status VARCHAR(20) NOT NULL", "old_status ENUM('pending','paid','shipped','cancelled'),new_status ENUM('pending','paid','shipped','cancelled') NOT NULL"},
          {"CREATE INDEX products_name_lower ON products(name);", "ALTER TABLE products ADD COLUMN name_lower VARCHAR(255) AS (lower(name)) VIRTUAL; CREATE INDEX products_name_lower ON products(name_lower);"},
          {"FOR EACH ROW INSERT INTO audit_log(order_id,old_status,new_status) SELECT NEW.id,OLD.status,NEW.status WHERE NOT(NEW.status <=> OLD.status);", "FOR EACH ROW BEGIN IF NOT(NEW.status <=> OLD.status) THEN INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,OLD.status,NEW.status); END IF; END;"},
         }
         for _,edit:=range edits{if strings.Count(string(body),edit[0])!=1{return fmt.Errorf("missing matched schema anchor %s",edit[0])};body=[]byte(strings.Replace(string(body),edit[0],edit[1],1))}
        }

		if err != nil {
			return err
		}
		tx := db
		if _, err := tx.ExecContext(ctx, string(body)); err != nil {
			/* DDL implicitly commits on MariaDB */
			return fmt.Errorf("%s: %w", e.Name(), err)
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO schema_migrations(version) VALUES (?)`, e.Name()); err != nil {
			/* DDL implicitly commits on MariaDB */
			return err
		}

	}
	return nil
}

// Master data: the reference rows every test can rely on. They never
// change during a test, so they live in the prepared baseline.
const (
	MasterCategories = 20
	MasterProducts   = 500
	MasterUsers      = 1000
	initialStock     = 100
)

var categoryNames = []string{
	"Books", "Music", "Movies", "Games", "Toys", "Garden", "Kitchen", "Tools",
	"Sports", "Outdoors", "Beauty", "Health", "Grocery", "Pets", "Baby", "Office",
	"Electronics", "Phones", "Computers", "Automotive",
}

// SeedMaster loads categories, products and users.
func SeedMaster(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, name := range categoryNames {
		if _, err := tx.ExecContext(ctx, `INSERT INTO categories(name) VALUES (?)`, name); err != nil {
			return err
		}
	}
	if _,err := tx.ExecContext(ctx, `INSERT INTO products(category_id,sku,name,price_cents,stock) SELECT 1+(seq % ?),CONCAT('SKU-',LPAD(seq,5,'0')),CONCAT('Product ',seq),500+(seq*37)%20000,? FROM seq_1_to_500`,MasterCategories,initialStock);err!=nil{return err}
 if _,err := tx.ExecContext(ctx, `INSERT INTO users(name,email) SELECT CONCAT('user',seq),CONCAT('user',seq,'@example.com') FROM seq_1_to_1000`);err!=nil{return err}
	if err := tx.Commit(); err != nil {
		return err
	}
	_, err = db.ExecContext(ctx, `ANALYZE TABLE users,categories,products,orders,order_items,audit_log`)
	return err
}

// Sample data: the orders a test scenario starts from. Tests both read
// and modify them, so every isolated copy gets its own.
type SampleOrder struct {
	ID     int64
	UserID int64
	Status string
	Items  []OrderItem
}

const SampleOrderCount = 40

var sampleStatuses = []string{"pending", "paid", "shipped", "paid"}

// SampleOrders is the deterministic order set LoadSample inserts; tests
// derive their expectations from it. IDs are 1..SampleOrderCount because
// every copy starts from restarted sequences.
func SampleOrders() []SampleOrder {
	out := make([]SampleOrder, 0, SampleOrderCount)
	for n := 1; n <= SampleOrderCount; n++ {
		o := SampleOrder{ID: int64(n), UserID: int64(1 + (n*7)%MasterUsers), Status: sampleStatuses[n%len(sampleStatuses)]}
		for k := 0; k < 1+n%4; k++ {
			pid := int64(1 + (n*13+k*29)%MasterProducts)
			o.Items = append(o.Items, OrderItem{ProductID: pid, Quantity: 1 + (n+k)%3, UnitPriceCents: priceOf(pid)})
		}
		out = append(out, o)
	}
	return out
}

// priceOf mirrors the formula in SeedMaster.
func priceOf(productID int64) int64 { return 500 + (productID*37)%20000 }

// LoadSample inserts SampleOrders one row at a time inside one transaction,
// the way a fixture loader does, and reserves their stock.
func LoadSample(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	insOrder, err := tx.PrepareContext(ctx, `INSERT INTO orders(user_id, status) VALUES (?, ?) RETURNING id`)
	if err != nil {
		return err
	}
	defer insOrder.Close()
	insItem, err := tx.PrepareContext(ctx, `INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents) VALUES (?, ?, ?, ?)`)
	if err != nil {
		return err
	}
	defer insItem.Close()
	reserve, err := tx.PrepareContext(ctx, `UPDATE products SET stock = stock - ? WHERE id = ?`)
	if err != nil {
		return err
	}
	defer reserve.Close()
	for _, o := range SampleOrders() {
		var id int64
		if err := insOrder.QueryRowContext(ctx, o.UserID, o.Status).Scan(&id); err != nil {
			return err
		}
		if id != o.ID {
			return fmt.Errorf("store: sample order %d got id %d; the copy is not fresh", o.ID, id)
		}
		for _, it := range o.Items {
			if _, err := insItem.ExecContext(ctx, id, it.ProductID, it.Quantity, it.UnitPriceCents); err != nil {
				return err
			}
			if _, err := reserve.ExecContext(ctx, it.Quantity, it.ProductID); err != nil {
				return err
			}
		}
	}
	return tx.Commit()
}

// ResetSample returns a shared database to the master state: the sample
// orders, their lines and the audit rows go, sequences restart, and the
// stock and prices go back to what SeedMaster set. This is what a suite
// on one shared server runs between tests that write.
func ResetSample(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	if _, err := tx.ExecContext(ctx, `TRUNCATE orders, order_items, audit_log RESTART IDENTITY CASCADE`); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `UPDATE products SET stock = ?, price_cents = 500 + (id * 37) % 20000`, initialStock); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO users(id, name, email)
		SELECT i, 'user' || i, 'user' || i || '@example.com' FROM generate_series(1, ?) i
		ON CONFLICT (id) DO NOTHING`, MasterUsers); err != nil {
		return err
	}
	return tx.Commit()
}
