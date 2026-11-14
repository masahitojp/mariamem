package store

import (
	"context"
	"database/sql"
	"embed"
	"fmt"
	"sort"
)

//go:embed migrations/*.sql
var migrations embed.FS

// Migrate applies the SQL files under migrations/ in name order and records
// each in schema_migrations, as a migration tool would.
func Migrate(ctx context.Context, db *sql.DB) error {
	if _, err := db.ExecContext(ctx, `CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())`); err != nil {
		return err
	}
	entries, err := migrations.ReadDir("migrations")
	if err != nil {
		return err
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name() < entries[j].Name() })
	for _, e := range entries {
		var applied bool
		if err := db.QueryRowContext(ctx, `SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE version = $1)`, e.Name()).Scan(&applied); err != nil {
			return err
		}
		if applied {
			continue
		}
		body, err := migrations.ReadFile("migrations/" + e.Name())
		if err != nil {
			return err
		}
		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		if _, err := tx.ExecContext(ctx, string(body)); err != nil {
			tx.Rollback()
			return fmt.Errorf("%s: %w", e.Name(), err)
		}
		if _, err := tx.ExecContext(ctx, `INSERT INTO schema_migrations(version) VALUES ($1)`, e.Name()); err != nil {
			tx.Rollback()
			return err
		}
		if err := tx.Commit(); err != nil {
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
		if _, err := tx.ExecContext(ctx, `INSERT INTO categories(name) VALUES ($1)`, name); err != nil {
			return err
		}
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO products(category_id, sku, name, price_cents, stock)
		SELECT 1 + (i % $1), 'SKU-' || lpad(i::text, 5, '0'), 'Product ' || i, 500 + (i * 37) % 20000, $3
		  FROM generate_series(1, $2) i`, MasterCategories, MasterProducts, initialStock); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO users(name, email)
		SELECT 'user' || i, 'user' || i || '@example.com' FROM generate_series(1, $1) i`, MasterUsers); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	_, err = db.ExecContext(ctx, `ANALYZE`)
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
	insOrder, err := tx.PrepareContext(ctx, `INSERT INTO orders(user_id, status) VALUES ($1, $2) RETURNING id`)
	if err != nil {
		return err
	}
	defer insOrder.Close()
	insItem, err := tx.PrepareContext(ctx, `INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents) VALUES ($1, $2, $3, $4)`)
	if err != nil {
		return err
	}
	defer insItem.Close()
	reserve, err := tx.PrepareContext(ctx, `UPDATE products SET stock = stock - $2 WHERE id = $1`)
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
			if _, err := reserve.ExecContext(ctx, it.ProductID, it.Quantity); err != nil {
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
	if _, err := tx.ExecContext(ctx, `UPDATE products SET stock = $1, price_cents = 500 + (id * 37) % 20000`, initialStock); err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `
		INSERT INTO users(id, name, email)
		SELECT i, 'user' || i, 'user' || i || '@example.com' FROM generate_series(1, $1) i
		ON CONFLICT (id) DO NOTHING`, MasterUsers); err != nil {
		return err
	}
	return tx.Commit()
}
