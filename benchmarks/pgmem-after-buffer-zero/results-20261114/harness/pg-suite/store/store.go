// Package store is the data layer of a small shop and the model project the
// benchmark measures: plain database/sql, plain SQL, one transaction per
// command. Nothing in it knows which server it talks to.
package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

// DB is what every query needs: *sql.DB and *sql.Tx both satisfy it.
type DB interface {
	ExecContext(ctx context.Context, query string, args ...any) (sql.Result, error)
	QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error)
	QueryRowContext(ctx context.Context, query string, args ...any) *sql.Row
}

type OrderItem struct {
	ProductID      int64
	Quantity       int
	UnitPriceCents int64
}

type Order struct {
	ID         int64
	UserID     int64
	Status     string
	TotalCents int64
	Items      []OrderItem
}

type OrderSummary struct {
	ID         int64
	Status     string
	TotalCents int64
	ItemCount  int
}

type ProductSales struct {
	ProductID    int64
	Name         string
	Quantity     int64
	RevenueCents int64
}

type CategoryRevenue struct {
	Category     string
	RevenueCents int64
}

type Product struct {
	ID         int64
	SKU        string
	Name       string
	PriceCents int64
	Stock      int
}

var ErrNotFound = errors.New("store: not found")

// ListOrders returns a user's orders, newest first, with their item counts.
func ListOrders(ctx context.Context, db DB, userID int64) ([]OrderSummary, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT o.id, o.status, o.total_cents, count(i.id)
		  FROM orders o
		  LEFT JOIN order_items i ON i.order_id = o.id
		 WHERE o.user_id = $1
		 GROUP BY o.id
		 ORDER BY o.created_at DESC, o.id DESC`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []OrderSummary
	for rows.Next() {
		var s OrderSummary
		if err := rows.Scan(&s.ID, &s.Status, &s.TotalCents, &s.ItemCount); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// GetOrder loads one order with its items.
func GetOrder(ctx context.Context, db DB, id int64) (*Order, error) {
	o := &Order{ID: id}
	err := db.QueryRowContext(ctx, `SELECT user_id, status, total_cents FROM orders WHERE id = $1`, id).
		Scan(&o.UserID, &o.Status, &o.TotalCents)
	if errors.Is(err, sql.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	rows, err := db.QueryContext(ctx, `SELECT product_id, quantity, unit_price_cents FROM order_items WHERE order_id = $1 ORDER BY id`, id)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var it OrderItem
		if err := rows.Scan(&it.ProductID, &it.Quantity, &it.UnitPriceCents); err != nil {
			return nil, err
		}
		o.Items = append(o.Items, it)
	}
	return o, rows.Err()
}

// TopProducts ranks products by units sold in orders that were not cancelled.
func TopProducts(ctx context.Context, db DB, n int) ([]ProductSales, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT p.id, p.name, sum(i.quantity), sum(i.quantity * i.unit_price_cents)
		  FROM order_items i
		  JOIN orders o ON o.id = i.order_id AND o.status <> 'cancelled'
		  JOIN products p ON p.id = i.product_id
		 GROUP BY p.id
		 ORDER BY sum(i.quantity) DESC, p.id
		 LIMIT $1`, n)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []ProductSales
	for rows.Next() {
		var s ProductSales
		if err := rows.Scan(&s.ProductID, &s.Name, &s.Quantity, &s.RevenueCents); err != nil {
			return nil, err
		}
		out = append(out, s)
	}
	return out, rows.Err()
}

// SearchProducts is a prefix search on the lower-cased name.
func SearchProducts(ctx context.Context, db DB, prefix string) ([]Product, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT id, sku, name, price_cents, stock
		  FROM products
		 WHERE lower(name) LIKE lower($1) || '%'
		 ORDER BY name, id
		 LIMIT 50`, prefix)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []Product
	for rows.Next() {
		var p Product
		if err := rows.Scan(&p.ID, &p.SKU, &p.Name, &p.PriceCents, &p.Stock); err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, rows.Err()
}

// RevenueByCategory sums paid and shipped order lines per category.
func RevenueByCategory(ctx context.Context, db DB) ([]CategoryRevenue, error) {
	rows, err := db.QueryContext(ctx, `
		SELECT c.name, COALESCE(sum(s.cents), 0)
		  FROM categories c
		  LEFT JOIN (
		        SELECT p.category_id, i.quantity * i.unit_price_cents AS cents
		          FROM order_items i
		          JOIN orders o ON o.id = i.order_id AND o.status IN ('paid', 'shipped')
		          JOIN products p ON p.id = i.product_id
		       ) s ON s.category_id = c.id
		 GROUP BY c.id
		 ORDER BY 2 DESC, c.name`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	var out []CategoryRevenue
	for rows.Next() {
		var r CategoryRevenue
		if err := rows.Scan(&r.Category, &r.RevenueCents); err != nil {
			return nil, err
		}
		out = append(out, r)
	}
	return out, rows.Err()
}

// CreateOrder inserts an order and its lines in one transaction, taking the
// current price of every product and reserving stock.
func CreateOrder(ctx context.Context, db *sql.DB, userID int64, items []OrderItem) (int64, error) {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback()
	var id int64
	if err := tx.QueryRowContext(ctx, `INSERT INTO orders(user_id, status) VALUES ($1, 'pending') RETURNING id`, userID).Scan(&id); err != nil {
		return 0, err
	}
	for _, it := range items {
		res, err := tx.ExecContext(ctx, `UPDATE products SET stock = stock - $2 WHERE id = $1 AND stock >= $2`, it.ProductID, it.Quantity)
		if err != nil {
			return 0, err
		}
		if n, _ := res.RowsAffected(); n != 1 {
			return 0, fmt.Errorf("store: product %d out of stock", it.ProductID)
		}
		if _, err := tx.ExecContext(ctx, `
			INSERT INTO order_items(order_id, product_id, quantity, unit_price_cents)
			SELECT $1, id, $3, price_cents FROM products WHERE id = $2`, id, it.ProductID, it.Quantity); err != nil {
			return 0, err
		}
	}
	return id, tx.Commit()
}

// CancelOrder marks an order cancelled and returns its stock.
func CancelOrder(ctx context.Context, db *sql.DB, id int64) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	res, err := tx.ExecContext(ctx, `UPDATE orders SET status = 'cancelled' WHERE id = $1 AND status IN ('pending', 'paid')`, id)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n != 1 {
		return ErrNotFound
	}
	if _, err := tx.ExecContext(ctx, `
		UPDATE products p SET stock = p.stock + i.quantity
		  FROM order_items i
		 WHERE i.order_id = $1 AND i.product_id = p.id`, id); err != nil {
		return err
	}
	return tx.Commit()
}

// ShipOrder moves a paid order to shipped.
func ShipOrder(ctx context.Context, db DB, id int64) error {
	res, err := db.ExecContext(ctx, `UPDATE orders SET status = 'shipped' WHERE id = $1 AND status = 'paid'`, id)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n != 1 {
		return ErrNotFound
	}
	return nil
}

// DeleteUser removes a user; the orders and their lines go with it.
func DeleteUser(ctx context.Context, db DB, id int64) error {
	res, err := db.ExecContext(ctx, `DELETE FROM users WHERE id = $1`, id)
	if err != nil {
		return err
	}
	if n, _ := res.RowsAffected(); n != 1 {
		return ErrNotFound
	}
	return nil
}

// ApplyDiscount lowers every price in a category by percent and returns
// how many products changed.
func ApplyDiscount(ctx context.Context, db DB, categoryID int, percent int) (int64, error) {
	res, err := db.ExecContext(ctx, `UPDATE products SET price_cents = price_cents * (100 - $2) / 100 WHERE category_id = $1`, categoryID, percent)
	if err != nil {
		return 0, err
	}
	return res.RowsAffected()
}
