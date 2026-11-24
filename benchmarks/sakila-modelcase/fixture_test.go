package sakila

import (
	"context"
	"database/sql"
	"fmt"
	"strings"
)

var schema = []string{
	"CREATE TABLE customer (customer_id INT PRIMARY KEY, first_name VARCHAR(45), last_name VARCHAR(45)) ENGINE=InnoDB",
	"CREATE TABLE film (film_id INT PRIMARY KEY, title VARCHAR(128) NOT NULL) ENGINE=InnoDB",
	"CREATE TABLE store (store_id INT PRIMARY KEY) ENGINE=InnoDB",
	"CREATE TABLE staff (staff_id INT PRIMARY KEY, store_id INT NOT NULL, FOREIGN KEY (store_id) REFERENCES store(store_id)) ENGINE=InnoDB",
	"CREATE TABLE inventory (inventory_id INT PRIMARY KEY, film_id INT NOT NULL, store_id INT NOT NULL, FOREIGN KEY (film_id) REFERENCES film(film_id), FOREIGN KEY (store_id) REFERENCES store(store_id)) ENGINE=InnoDB",
	"CREATE TABLE rental (rental_id INT AUTO_INCREMENT PRIMARY KEY, rental_date DATETIME NOT NULL, inventory_id INT NOT NULL, customer_id INT NOT NULL, return_date DATETIME, staff_id INT NOT NULL, UNIQUE (rental_date, inventory_id, customer_id), FOREIGN KEY (inventory_id) REFERENCES inventory(inventory_id), FOREIGN KEY (customer_id) REFERENCES customer(customer_id), FOREIGN KEY (staff_id) REFERENCES staff(staff_id)) ENGINE=InnoDB",
	"CREATE TABLE payment (payment_id INT AUTO_INCREMENT PRIMARY KEY, customer_id INT NOT NULL, staff_id INT NOT NULL, rental_id INT, amount DECIMAL(5,2) NOT NULL, payment_date DATETIME NOT NULL, FOREIGN KEY (customer_id) REFERENCES customer(customer_id), FOREIGN KEY (staff_id) REFERENCES staff(staff_id), FOREIGN KEY (rental_id) REFERENCES rental(rental_id)) ENGINE=InnoDB",
	"CREATE TABLE rental_audit (audit_id INT AUTO_INCREMENT PRIMARY KEY, rental_id INT NOT NULL, event_type VARCHAR(8) NOT NULL, old_return_date DATETIME, new_return_date DATETIME, recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, KEY (rental_id)) ENGINE=InnoDB",
	"CREATE TRIGGER rental_audit_insert AFTER INSERT ON rental FOR EACH ROW INSERT INTO rental_audit (rental_id, event_type, new_return_date) VALUES (NEW.rental_id, 'insert', NEW.return_date)",
	`CREATE TRIGGER rental_audit_update AFTER UPDATE ON rental FOR EACH ROW
	BEGIN
		IF NOT (OLD.return_date <=> NEW.return_date) THEN
			INSERT INTO rental_audit (rental_id, event_type, old_return_date, new_return_date)
			VALUES (NEW.rental_id, 'update', OLD.return_date, NEW.return_date);
		END IF;
	END`,
}

func rows(count int, format func(int) string) string {
	values := make([]string, count)
	for index := range values {
		values[index] = format(index + 1)
	}
	return strings.Join(values, ",")
}

var seed = []string{
	"INSERT INTO customer VALUES " + rows(599, func(i int) string { return fmt.Sprintf("(%d,'Customer','%d')", i, i) }),
	"INSERT INTO film VALUES " + rows(500, func(i int) string { return fmt.Sprintf("(%d,'Film %d')", i, i) }),
	"INSERT INTO store VALUES (1),(2)",
	"INSERT INTO staff VALUES (1,1),(2,2)",
	"INSERT INTO inventory VALUES " + rows(500, func(i int) string { return fmt.Sprintf("(%d,%d,%d)", i, i, 1+(i-1)%2) }),
}

type rentalSeed struct {
	id, customer, staff, cents int
}

var initialRentals = sampleRentals()

func sampleRentals() []rentalSeed {
	var samples []rentalSeed
	for customer, count := range []int{1, 2, 3, 4, 5, 6, 7, 2, 4, 6} {
		for range count {
			id := len(samples) + 1
			samples = append(samples, rentalSeed{id, customer + 1, 1 + (id-1)%2, 249 + (id*37)%500})
		}
	}
	return samples
}

func decimal(cents int) string {
	return fmt.Sprintf("%d.%02d", cents/100, cents%100)
}

func transactionRows(format func(rentalSeed) string) string {
	return rows(len(initialRentals), func(id int) string { return format(initialRentals[id-1]) })
}

var transactionSeed = []string{
	"INSERT INTO rental (rental_id,rental_date,inventory_id,customer_id,staff_id) VALUES " +
		transactionRows(func(r rentalSeed) string {
			return fmt.Sprintf("(%d,'2020-01-01',%d,%d,%d)", r.id, r.id, r.customer, r.staff)
		}),
	"INSERT INTO payment (customer_id,staff_id,rental_id,amount,payment_date) VALUES " +
		transactionRows(func(r rentalSeed) string {
			return fmt.Sprintf("(%d,%d,%d,%s,'2020-01-01')", r.customer, r.staff, r.id, decimal(r.cents))
		}),
}

type executor interface {
	ExecContext(context.Context, string, ...any) (sql.Result, error)
	QueryRowContext(context.Context, string, ...any) *sql.Row
}

func fixture(ctx context.Context, db executor) error {
	for _, batch := range [][]string{schema, seed, transactionSeed} {
		for _, statement := range batch {
			if _, err := db.ExecContext(ctx, statement); err != nil {
				firstLine, _, _ := strings.Cut(statement, "\n")
				return fmt.Errorf("%s: %w", firstLine[:min(len(firstLine), 100)], err)
			}
		}
	}
	return nil
}

func expect(ctx context.Context, db executor, want int, query string, args ...any) error {
	var got int
	if err := db.QueryRowContext(ctx, query, args...).Scan(&got); err != nil {
		return fmt.Errorf("%s: %w", query, err)
	}
	if got != want {
		return fmt.Errorf("%s: got %d, want %d", query, got, want)
	}
	return nil
}

func pristine(ctx context.Context, db executor) error {
	for _, query := range []string{
		"SELECT COUNT(*) FROM rental WHERE return_date IS NULL",
		"SELECT COUNT(*) FROM payment",
		"SELECT COUNT(*) FROM rental_audit WHERE event_type='insert' AND old_return_date IS NULL AND new_return_date IS NULL",
		"SELECT COUNT(*) FROM rental_audit",
	} {
		if err := expect(ctx, db, len(initialRentals), query); err != nil {
			return err
		}
	}
	return nil
}

func baseline(ctx context.Context, db executor) error {
	if err := pristine(ctx, db); err != nil {
		return err
	}
	total := 0
	for _, r := range initialRentals {
		total += r.cents
	}
	return expect(ctx, db, total, "SELECT CAST(SUM(amount)*100 AS UNSIGNED) FROM payment")
}

func reset(ctx context.Context, db *sql.DB) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	for _, batch := range [][]string{
		{"DELETE FROM payment", "DELETE FROM rental", "DELETE FROM rental_audit"},
		transactionSeed,
	} {
		for _, statement := range batch {
			if _, err := tx.ExecContext(ctx, statement); err != nil {
				return err
			}
		}
	}
	return tx.Commit()
}
