package sakila

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

type scenario struct {
	name string
	run  func(context.Context, *sql.DB, int) error
}

var readScenarios = []scenario{
	{"customer_rentals", customerRentals},
	{"catalog", func(ctx context.Context, db *sql.DB, variant int) error {
		first := variant * 37
		return expect(ctx, db, variant*(2*first+variant-1)/2,
			`SELECT SUM(f.film_id) FROM inventory i JOIN film f ON i.film_id=f.film_id
			  WHERE i.inventory_id BETWEEN ? AND ?`, first, first+variant-1)
	}},
	{"customer_payments", func(ctx context.Context, db *sql.DB, customer int) error {
		want := 0
		for _, r := range initialRentals {
			if r.customer == customer {
				want += r.cents
			}
		}
		return expect(ctx, db, want, "SELECT CAST(SUM(amount)*100 AS UNSIGNED) FROM payment WHERE customer_id=?", customer)
	}},
	{"store_sales", func(ctx context.Context, db *sql.DB, variant int) error {
		store, last := 1+variant%2, variant*4
		want := 0
		for _, r := range initialRentals {
			if r.staff == store && r.id <= last {
				want += r.cents
			}
		}
		return expect(ctx, db, want, `SELECT CAST(SUM(p.amount)*100 AS UNSIGNED)
			FROM payment p JOIN staff s ON s.staff_id=p.staff_id WHERE s.store_id=? AND p.rental_id<=?`, store, last)
	}},
	{"rental_history", func(ctx context.Context, db *sql.DB, customer int) error {
		return expect(ctx, db, len(customerRentalIDs(customer)), `SELECT COUNT(*) FROM rental_audit a
			JOIN rental r ON a.rental_id=r.rental_id WHERE r.customer_id=? AND a.event_type='insert'
			AND a.old_return_date IS NULL AND a.new_return_date IS NULL`, customer)
	}},
}

func customerRentalIDs(customer int) []int {
	var ids []int
	for _, r := range initialRentals {
		if r.customer == customer {
			ids = append(ids, r.id)
		}
	}
	return ids
}

func customerRentals(ctx context.Context, db *sql.DB, customer int) error {
	want := customerRentalIDs(customer)
	results, err := db.QueryContext(ctx, `SELECT f.title, r.return_date IS NULL
		FROM customer c JOIN rental r ON r.customer_id=c.customer_id
		JOIN inventory i ON i.inventory_id=r.inventory_id JOIN film f ON f.film_id=i.film_id
		WHERE c.customer_id=? ORDER BY r.rental_id`, customer)
	if err != nil {
		return err
	}
	defer results.Close()
	count := 0
	for results.Next() {
		var title string
		var outstanding bool
		if err := results.Scan(&title, &outstanding); err != nil {
			return err
		}
		if count >= len(want) || title != fmt.Sprintf("Film %d", want[count]) || !outstanding {
			return fmt.Errorf("unexpected rental: %q, outstanding=%v", title, outstanding)
		}
		count++
	}
	if err := results.Err(); err != nil {
		return err
	}
	if count != len(want) {
		return fmt.Errorf("got %d customer rentals, want %d", count, len(want))
	}
	return nil
}

func returnDate(variant int) string {
	return fmt.Sprintf("2020-01-%02d 12:00:00", variant+2)
}

var writeScenarios = []scenario{
	{"checkout", checkout},
	{"return", func(ctx context.Context, db *sql.DB, variant int) error {
		id, date := variant*4-3, returnDate(variant)
		for range 2 {
			if err := setReturn(ctx, db, id, date); err != nil {
				return err
			}
		}
		return checkReturn(ctx, db, id, date)
	}},
	{"rollback", func(ctx context.Context, db *sql.DB, variant int) error {
		id, date := variant*4-2, returnDate(variant)
		tx, err := db.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		defer tx.Rollback()
		if err := setReturn(ctx, tx, id, date); err != nil {
			return err
		}
		if err := checkReturn(ctx, tx, id, date); err != nil {
			return err
		}
		if err := tx.Rollback(); err != nil {
			return err
		}
		return pristine(ctx, db)
	}},
	{"reopen", func(ctx context.Context, db *sql.DB, variant int) error {
		id, date := variant*4-1, returnDate(variant)
		if err := setReturn(ctx, db, id, date); err != nil {
			return err
		}
		if err := setReturn(ctx, db, id, nil); err != nil {
			return err
		}
		return errors.Join(
			expect(ctx, db, 1, "SELECT COUNT(*) FROM rental WHERE rental_id=? AND return_date IS NULL", id),
			expect(ctx, db, 1, "SELECT COUNT(*) FROM rental_audit WHERE rental_id=? AND event_type='update' AND old_return_date=? AND new_return_date IS NULL", id, date),
			expect(ctx, db, 2, "SELECT COUNT(*) FROM rental_audit WHERE rental_id=? AND event_type='update'", id),
		)
	}},
	{"adjust_payment", func(ctx context.Context, db *sql.DB, variant int) error {
		id, cents := variant*4, 199+variant*13
		if _, err := db.ExecContext(ctx, "UPDATE payment SET amount=? WHERE rental_id=?", decimal(cents), id); err != nil {
			return err
		}
		return errors.Join(
			expect(ctx, db, cents, "SELECT CAST(amount*100 AS UNSIGNED) FROM payment WHERE rental_id=?", id),
			pristine(ctx, db),
		)
	}},
}

func checkout(ctx context.Context, db *sql.DB, variant int) error {
	tx, err := db.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	item, customer := 100+variant, 200+variant
	staff, cents := 1+(item-1)%2, 349+variant*23
	date := returnDate(variant)
	result, err := tx.ExecContext(ctx, `INSERT INTO rental (rental_date,inventory_id,customer_id,staff_id)
		VALUES (?,?,?,?)`, date, item, customer, staff)
	if err != nil {
		return err
	}
	id, err := result.LastInsertId()
	if err != nil {
		return err
	}
	if _, err := tx.ExecContext(ctx, `INSERT INTO payment (customer_id,staff_id,rental_id,amount,payment_date)
		VALUES (?,?,?,?,?)`, customer, staff, id, decimal(cents), date); err != nil {
		return err
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	return errors.Join(
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental WHERE rental_id=? AND inventory_id=? AND customer_id=? AND staff_id=? AND rental_date=?", id, item, customer, staff, date),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM payment WHERE rental_id=? AND customer_id=? AND CAST(amount*100 AS UNSIGNED)=? AND payment_date=?", id, customer, cents, date),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental_audit WHERE rental_id=? AND event_type='insert' AND old_return_date IS NULL AND new_return_date IS NULL", id),
	)
}

func setReturn(ctx context.Context, db executor, id int, date any) error {
	_, err := db.ExecContext(ctx, "UPDATE rental SET return_date=? WHERE rental_id=?", date, id)
	return err
}

func checkReturn(ctx context.Context, db executor, id int, date string) error {
	return errors.Join(
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental WHERE rental_id=? AND return_date=?", id, date),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental_audit WHERE rental_id=? AND event_type='update' AND old_return_date IS NULL AND new_return_date=?", id, date),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental_audit WHERE rental_id=? AND event_type='update'", id),
	)
}
