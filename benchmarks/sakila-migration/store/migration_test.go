package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
)

const lateReturn = "2020-01-15 12:00:00"
const timelyReturn = "2020-01-04 12:00:00"

var migration = []string{
	`CREATE TABLE late_fee (
		rental_id INT PRIMARY KEY,
		amount DECIMAL(5,2) NOT NULL,
		FOREIGN KEY (rental_id) REFERENCES rental(rental_id)
	) ENGINE=InnoDB`,
	"CREATE INDEX payment_rental_amount ON payment (rental_id, amount)",
	`INSERT INTO late_fee (rental_id, amount)
		SELECT r.rental_id, 2.49 FROM rental r
		WHERE r.return_date > DATE_ADD(r.rental_date, INTERVAL 7 DAY)
		AND NOT EXISTS (SELECT 1 FROM payment p WHERE p.rental_id=r.rental_id AND p.amount=2.49)`,
	`CREATE TRIGGER rental_late_fee AFTER UPDATE ON rental FOR EACH ROW
	BEGIN
		IF OLD.return_date IS NULL AND NEW.return_date > DATE_ADD(NEW.rental_date, INTERVAL 7 DAY)
		AND NOT EXISTS (SELECT 1 FROM payment p WHERE p.rental_id=NEW.rental_id AND p.amount=2.49) THEN
			INSERT INTO late_fee (rental_id, amount) VALUES (NEW.rental_id, 2.49);
		END IF;
	END`,
}

func prepareMigration(ctx context.Context, db *sql.DB, variant int) error {
	if err := baseline(ctx, db); err != nil {
		return err
	}
	if err := expect(ctx, db, 0, `SELECT COUNT(*) FROM information_schema.TABLES
		WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='late_fee'`); err != nil {
		return err
	}
	if _, err := db.ExecContext(ctx, "UPDATE rental SET return_date=? WHERE rental_id<=?", lateReturn, variant-1); err != nil {
		return err
	}
	if _, err := db.ExecContext(ctx, "UPDATE rental SET return_date=? WHERE rental_id=?", timelyReturn, 10+variant); err != nil {
		return err
	}
	_, err := db.ExecContext(ctx, `INSERT INTO payment (customer_id, staff_id, rental_id, amount, payment_date)
		SELECT customer_id, staff_id, rental_id, 2.49, '2020-01-14' FROM rental WHERE rental_id<=?`, variant/3)
	return err
}

func migrateAndVerify(ctx context.Context, db *sql.DB, variant int) error {
	writer, err := db.Conn(ctx)
	if err != nil {
		return err
	}
	defer writer.Close()
	for index, statement := range migration {
		if _, err := writer.ExecContext(ctx, statement); err != nil {
			return fmt.Errorf("migration statement %d: %w", index+1, err)
		}
	}
	oldLate, prepaid := variant-1, variant/3
	backfilled := oldLate - prepaid
	feeSum := `SELECT COALESCE(CAST(SUM(amount)*100 AS UNSIGNED),0) FROM late_fee`
	// writer remains checked out, so the pool reads committed changes over
	// a separate connection.
	if err := errors.Join(
		expect(ctx, db, backfilled, "SELECT COUNT(*) FROM late_fee"),
		expect(ctx, db, backfilled, `SELECT COUNT(*) FROM late_fee
			WHERE rental_id>? AND rental_id<=? AND amount=2.49`, prepaid, oldLate),
		expect(ctx, db, backfilled*249, feeSum),
		expect(ctx, db, 1, `SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.STATISTICS
			WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='payment' AND INDEX_NAME='payment_rental_amount'`),
	); err != nil {
		return err
	}
	lateID, timelyID := 20+variant, 30+variant
	tx, err := writer.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	result, err := tx.ExecContext(ctx, `UPDATE rental SET return_date=CASE rental_id
		WHEN ? THEN ? ELSE ? END WHERE rental_id IN (?,?)`, lateID, lateReturn, timelyReturn, lateID, timelyID)
	if err != nil {
		return err
	}
	if count, err := result.RowsAffected(); err != nil || count != 2 {
		return fmt.Errorf("return updates: %d, expected 2: %w", count, err)
	}
	if err := tx.Commit(); err != nil {
		return err
	}
	return errors.Join(
		expect(ctx, db, backfilled+1, "SELECT COUNT(*) FROM late_fee"),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM late_fee WHERE rental_id=? AND amount=2.49", lateID),
		expect(ctx, db, 0, "SELECT COUNT(*) FROM late_fee WHERE rental_id=?", timelyID),
		expect(ctx, db, (backfilled+1)*249, feeSum),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental WHERE rental_id=? AND return_date=?", lateID, lateReturn),
		expect(ctx, db, 1, "SELECT COUNT(*) FROM rental WHERE rental_id=? AND return_date=?", timelyID, timelyReturn),
		expect(ctx, db, 40, "SELECT COUNT(*) FROM rental"),
		expect(ctx, db, 40+prepaid, "SELECT COUNT(*) FROM payment"),
		expect(ctx, db, oldLate+3, "SELECT COUNT(*) FROM rental_audit WHERE event_type='update'"),
		expect(ctx, db, 2, `SELECT COUNT(*) FROM rental_audit
			WHERE rental_id IN (?,?) AND event_type='update' AND old_return_date IS NULL
			AND ((rental_id=? AND new_return_date=?) OR (rental_id=? AND new_return_date=?))`,
			lateID, timelyID, lateID, lateReturn, timelyID, timelyReturn),
	)
}
