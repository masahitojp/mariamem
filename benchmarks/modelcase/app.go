// The same application SQL and assertions run against every fixture model.
package modelcase

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

var schema = []string{
	`CREATE TABLE categories(id INT PRIMARY KEY,name VARCHAR(64) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
	`CREATE TABLE products(id INT PRIMARY KEY,category_id INT NOT NULL,price INT NOT NULL,stock INT NOT NULL,FOREIGN KEY(category_id) REFERENCES categories(id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
	`CREATE TABLE users(id INT PRIMARY KEY,name VARCHAR(64) NOT NULL) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
	`CREATE TABLE orders(id INT PRIMARY KEY,user_id INT NOT NULL,status VARCHAR(20) NOT NULL,total INT NOT NULL,FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
	`CREATE TABLE order_items(order_id INT NOT NULL,product_id INT NOT NULL,quantity INT NOT NULL,PRIMARY KEY(order_id,product_id),FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,FOREIGN KEY(product_id) REFERENCES products(id)) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci`,
}

func insert(ctx context.Context, db *sql.DB, table string, n, cols int, values func(int) []any) error {
	tuples := make([]string, n)
	args := make([]any, 0, n*cols)
	for i := 1; i <= n; i++ {
		tuples[i-1] = "(" + strings.TrimSuffix(strings.Repeat("?,", cols), ",") + ")"
		args = append(args, values(i)...)
	}
	_, err := db.ExecContext(ctx, "INSERT INTO "+table+" VALUES "+strings.Join(tuples, ","), args...)
	return err
}
func prepare(ctx context.Context, db *sql.DB) error {
	for _, s := range schema {
		if _, err := db.ExecContext(ctx, s); err != nil {
			return err
		}
	}
	if err := insert(ctx, db, "categories", 20, 2, func(i int) []any { return []any{i, fmt.Sprintf("category-%d", i)} }); err != nil {
		return err
	}
	if err := insert(ctx, db, "products", 500, 4, func(i int) []any { return []any{i, (i-1)%20 + 1, 100 + i, 1000} }); err != nil {
		return err
	}
	if err := insert(ctx, db, "users", 1000, 2, func(i int) []any { return []any{i, fmt.Sprintf("user-%d", i)} }); err != nil {
		return err
	}
	return sampleOrders(ctx, db)
}
func sampleOrders(ctx context.Context, db *sql.DB) error {
	if err := insert(ctx, db, "orders", 40, 4, func(i int) []any { return []any{i, (i-1)%10 + 1, "pending", 100 + i} }); err != nil {
		return err
	}
	if err := insert(ctx, db, "order_items", 40, 3, func(i int) []any { return []any{i, i, 1} }); err != nil {
		return err
	}
	_, err := db.ExecContext(ctx, "UPDATE products SET stock=999 WHERE id<=40")
	return err
}
func reset(ctx context.Context, db *sql.DB) error {
	for _, s := range []string{
		`DELETE FROM orders`,
		`INSERT IGNORE INTO users VALUES(1,'user-1'),(2,'user-2'),(3,'user-3'),(4,'user-4')`,
		`UPDATE products SET price=100+id,stock=1000`,
	} {
		if _, err := db.ExecContext(ctx, s); err != nil {
			return err
		}
	}
	return sampleOrders(ctx, db)
}
func pristine(ctx context.Context, db *sql.DB) error {
	var categories, products, users, orders, items, price, stock int
	err := db.QueryRowContext(ctx, `SELECT (SELECT COUNT(*) FROM categories),(SELECT COUNT(*) FROM products),(SELECT COUNT(*) FROM users),(SELECT COUNT(*) FROM orders),(SELECT COUNT(*) FROM order_items),(SELECT SUM(price) FROM products),(SELECT SUM(stock) FROM products)`).Scan(&categories, &products, &users, &orders, &items, &price, &stock)
	if err != nil {
		return err
	}
	if categories != 20 || products != 500 || users != 1000 || orders != 40 || items != 40 || price != 175250 || stock != 499960 {
		return fmt.Errorf("pristine input differs: %d/%d/%d/%d/%d price=%d stock=%d", categories, products, users, orders, items, price, stock)
	}
	return nil
}

type appCase struct {
	Name        string
	Write       bool
	Kind, Index int
}

func cases() []appCase {
	out := []appCase{}
	for kind := 0; kind < 5; kind++ {
		for i := 1; i <= 10; i++ {
			out = append(out, appCase{fmt.Sprintf("read-%d-%02d", kind, i), false, kind, i})
		}
	}
	for kind := 0; kind < 5; kind++ {
		for i := 1; i <= 4; i++ {
			out = append(out, appCase{fmt.Sprintf("write-%d-%02d", kind, i), true, kind, i})
		}
	}
	return out
}
func same(got, want int) error {
	if got != want {
		return fmt.Errorf("result=%d, expected=%d", got, want)
	}
	return nil
}
func runCase(ctx context.Context, db *sql.DB, c appCase) error {
	var got int
	if !c.Write {
		switch c.Kind {
		case 0:
			rows, err := db.QueryContext(ctx, "SELECT id FROM orders WHERE user_id=? ORDER BY id", c.Index)
			if err != nil {
				return err
			}
			defer rows.Close()
			i := 0
			for rows.Next() {
				if err = rows.Scan(&got); err != nil {
					return err
				}
				if err = same(got, c.Index+10*i); err != nil {
					return err
				}
				i++
			}
			if err = rows.Err(); err != nil {
				return err
			}
			return same(i, 4)
		case 1:
			var user, price, quantity int
			err := db.QueryRowContext(ctx, "SELECT o.user_id,p.price,i.quantity FROM orders o JOIN order_items i ON i.order_id=o.id JOIN products p ON p.id=i.product_id WHERE o.id=?", c.Index).Scan(&user, &price, &quantity)
			if err != nil {
				return err
			}
			if err = same(user, c.Index); err != nil {
				return err
			}
			if err = same(price, 100+c.Index); err != nil {
				return err
			}
			return same(quantity, 1)
		case 2:
			rows, err := db.QueryContext(ctx, "SELECT product_id,SUM(quantity) FROM order_items GROUP BY product_id ORDER BY SUM(quantity) DESC,product_id LIMIT 5")
			if err != nil {
				return err
			}
			defer rows.Close()
			i := 0
			for rows.Next() {
				var quantity int
				if err = rows.Scan(&got, &quantity); err != nil {
					return err
				}
				i++
				if err = same(got, i); err != nil {
					return err
				}
				if err = same(quantity, 1); err != nil {
					return err
				}
			}
			if err = rows.Err(); err != nil {
				return err
			}
			return same(i, 5)
		case 3:
			var minimum int
			err := db.QueryRowContext(ctx, "SELECT COUNT(*),MIN(id) FROM products WHERE category_id=?", c.Index).Scan(&got, &minimum)
			if err != nil {
				return err
			}
			if err = same(got, 25); err != nil {
				return err
			}
			return same(minimum, c.Index)
		case 4:
			err := db.QueryRowContext(ctx, "SELECT SUM(i.quantity*p.price) FROM order_items i JOIN products p ON p.id=i.product_id WHERE p.category_id=?", c.Index).Scan(&got)
			if err != nil {
				return err
			}
			return same(got, 220+2*c.Index)
		}
	}
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	exec := func(q string, args ...any) error { _, e := tx.ExecContext(ctx, q, args...); return e }
	switch c.Kind {
	case 0:
		if err = exec("INSERT INTO orders VALUES(?,1,'pending',202)", 100+c.Index); err != nil {
			return err
		}
		if err = exec("INSERT INTO order_items VALUES(?,1,2)", 100+c.Index); err != nil {
			return err
		}
		err = exec("UPDATE products SET stock=stock-2 WHERE id=1")
	case 1:
		if err = exec("UPDATE orders SET status='cancelled' WHERE id=?", c.Index); err != nil {
			return err
		}
		err = exec("UPDATE products SET stock=stock+1 WHERE id=?", c.Index)
	case 2:
		err = exec("UPDATE orders SET status='shipped' WHERE id=?", c.Index)
	case 3:
		err = exec("DELETE FROM users WHERE id=?", c.Index)
	case 4:
		err = exec("UPDATE products SET price=price-10 WHERE category_id=?", c.Index)
	}
	if err != nil {
		return err
	}
	if err = tx.Commit(); err != nil {
		return err
	}
	switch c.Kind {
	case 0:
		if err = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM orders").Scan(&got); err != nil {
			return err
		}
		if err = same(got, 41); err != nil {
			return err
		}
		if err = db.QueryRowContext(ctx, "SELECT stock FROM products WHERE id=1").Scan(&got); err != nil {
			return err
		}
		return same(got, 997)
	case 1:
		var status string
		if err = db.QueryRowContext(ctx, "SELECT status FROM orders WHERE id=?", c.Index).Scan(&status); err != nil {
			return err
		}
		if status != "cancelled" {
			return fmt.Errorf("status=%s", status)
		}
		if err = db.QueryRowContext(ctx, "SELECT stock FROM products WHERE id=?", c.Index).Scan(&got); err != nil {
			return err
		}
		return same(got, 1000)
	case 2:
		var status string
		if err = db.QueryRowContext(ctx, "SELECT status FROM orders WHERE id=?", c.Index).Scan(&status); err != nil {
			return err
		}
		if status != "shipped" {
			return fmt.Errorf("status=%s", status)
		}
		if err = db.QueryRowContext(ctx, "SELECT stock FROM products WHERE id=?", c.Index).Scan(&got); err != nil {
			return err
		}
		return same(got, 999)
	case 3:
		if err = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM orders").Scan(&got); err != nil {
			return err
		}
		if err = same(got, 36); err != nil {
			return err
		}
		if err = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM users").Scan(&got); err != nil {
			return err
		}
		return same(got, 999)
	case 4:
		if err = db.QueryRowContext(ctx, "SELECT MIN(price) FROM products WHERE category_id=?", c.Index).Scan(&got); err != nil {
			return err
		}
		return same(got, 90+c.Index)
	}
	return fmt.Errorf("unknown case: %+v", c)
}
