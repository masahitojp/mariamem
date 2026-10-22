// A fixed-driver P4 lifetime probe. It connects to an existing database; no
// generated runtime or public-library API is replaced by this consumer.
package main

import (
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sync"
	"time"

	"github.com/go-sql-driver/mysql"
)

type report struct {
	Result         string   `json:"result"`
	Checks         []string `json:"checks"`
	Error          string   `json:"error,omitempty"`
	PreparedBefore int      `json:"prepared_before"`
	PreparedAfter  int      `json:"prepared_after"`
	OpenAfter      int      `json:"open_after"`
}

func count(ctx context.Context, db *sql.DB) (int, error) {
	var name string
	var n int
	err := db.QueryRowContext(ctx, "SHOW GLOBAL STATUS LIKE 'Prepared_stmt_count'").Scan(&name, &n)
	return n, err
}
func integer(ctx context.Context, stmt *sql.Stmt, input int) error {
	var got int
	if err := stmt.QueryRowContext(ctx, input).Scan(&got); err != nil {
		return err
	}
	if got != input {
		return fmt.Errorf("binding crossed: got %d expected %d", got, input)
	}
	return nil
}
func exercise(r *report) (err error) {
	cfg, err := mysql.ParseDSN(os.Getenv("MARIAMEM_P4_DSN"))
	if err != nil {
		return err
	}
	cfg.InterpolateParams = true // Explicit Prepare must still use prepared protocol.
	db, err := sql.Open("mysql", cfg.FormatDSN())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, db.Close()); r.OpenAfter = db.Stats().OpenConnections }()
	db.SetMaxOpenConns(4)
	db.SetMaxIdleConns(4)
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
	defer cancel()
	if err = db.PingContext(ctx); err != nil {
		return err
	}
	if r.PreparedBefore, err = count(ctx, db); err != nil {
		return err
	}
	stmt, err := db.PrepareContext(ctx, "SELECT ?")
	if err != nil {
		return err
	}
	defer stmt.Close()
	for _, v := range []int{0, 1, -1, 123456} {
		if err = integer(ctx, stmt, v); err != nil {
			return err
		}
	}
	r.Checks = append(r.Checks, "DB.Prepare-explicit-with-interpolation")
	if _, err = db.ExecContext(ctx, "DROP TABLE IF EXISTS test.p4_lifetime"); err != nil {
		return err
	}
	if _, err = db.ExecContext(ctx, "CREATE TABLE test.p4_lifetime(id INT PRIMARY KEY,v INT) ENGINE=InnoDB"); err != nil {
		return err
	}
	if _, err = db.ExecContext(ctx, "INSERT INTO test.p4_lifetime VALUES(1,7)"); err != nil {
		return err
	}
	update, err := db.PrepareContext(ctx, "UPDATE test.p4_lifetime SET v=? WHERE id=1")
	if err != nil {
		return err
	}
	defer update.Close()
	for _, commit := range []bool{false, true} {
		tx, e := db.BeginTx(ctx, nil)
		if e != nil {
			return e
		}
		scoped := tx.StmtContext(ctx, update)
		if _, e = scoped.ExecContext(ctx, 29); e != nil {
			tx.Rollback()
			return e
		}
		direct, e := tx.PrepareContext(ctx, "SELECT v FROM test.p4_lifetime WHERE id=1")
		if e != nil {
			tx.Rollback()
			return e
		}
		var v int
		e = direct.QueryRowContext(ctx).Scan(&v)
		if e != nil || v != 29 {
			tx.Rollback()
			return fmt.Errorf("Tx visibility: %d %v", v, e)
		}
		if commit {
			e = tx.Commit()
		} else {
			e = tx.Rollback()
		}
		if e != nil {
			return e
		}
		if _, e = scoped.ExecContext(ctx, 99); e == nil {
			return errors.New("Tx.Stmt survived completed transaction")
		}
		if e = direct.QueryRowContext(ctx).Scan(&v); e == nil {
			return errors.New("Tx.Prepare survived completed transaction")
		}
		direct.Close()
		scoped.Close()
		if e = db.QueryRowContext(ctx, "SELECT v FROM test.p4_lifetime WHERE id=1").Scan(&v); e != nil {
			return e
		}
		expected := 7
		if commit {
			expected = 29
		}
		if v != expected {
			return fmt.Errorf("commit/rollback: %d expected %d", v, expected)
		}
	}
	r.Checks = append(r.Checks, "Tx.Prepare-Tx.Stmt-commit-rollback-and-invalidation")
	conn, err := db.Conn(ctx)
	if err != nil {
		return err
	}
	local, err := conn.PrepareContext(ctx, "SELECT ?")
	if err != nil {
		conn.Close()
		return err
	}
	if err = integer(ctx, local, 83); err != nil {
		local.Close()
		conn.Close()
		return err
	}
	if err = conn.Close(); err != nil {
		local.Close()
		return err
	}
	if err = integer(ctx, local, 84); !errors.Is(err, sql.ErrConnDone) {
		local.Close()
		return fmt.Errorf("Conn statement survived Conn.Close: %v", err)
	}
	if err = local.Close(); err != nil {
		return err
	}
	if _, err = conn.PrepareContext(ctx, "SELECT ?"); !errors.Is(err, sql.ErrConnDone) {
		return fmt.Errorf("closed Conn reusable: %v", err)
	}
	r.Checks = append(r.Checks, "Conn.Prepare-and-Conn-close")
	var wg sync.WaitGroup
	failures := make(chan error, 16)
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			for j := 0; j < 8; j++ {
				if e := integer(ctx, stmt, 1000+i*10+j); e != nil {
					failures <- e
					return
				}
			}
		}(i)
	}
	wg.Wait()
	close(failures)
	for e := range failures {
		return e
	}
	r.Checks = append(r.Checks, "shared-DB.Stmt-16-workers-128-executions-4-physical-connections")
	// Retire every pooled physical connection while keeping the logical DB.Stmt.
	// Its next use must prepare in a new physical session, not reuse an old handle.
	db.SetMaxIdleConns(0)
	if n := db.Stats().OpenConnections; n != 0 {
		return fmt.Errorf("idle sessions retained: %d", n)
	}
	db.SetMaxOpenConns(1)
	db.SetMaxIdleConns(1)
	conn, err = db.Conn(ctx)
	if err != nil {
		return err
	}
	var before, after uint64
	if err = conn.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&before); err != nil {
		conn.Close()
		return err
	}
	err = conn.Raw(func(any) error { return driver.ErrBadConn })
	conn.Close()
	if !errors.Is(err, driver.ErrBadConn) {
		return fmt.Errorf("retire connection: %v", err)
	}
	if err = integer(ctx, stmt, 901); err != nil {
		return err
	}
	if err = db.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&after); err != nil {
		return err
	}
	if before == after {
		return errors.New("physical connection did not change")
	}
	r.Checks = append(r.Checks, "DB.Stmt-reprepare-after-idle-retirement-and-ErrBadConn")
	if err = stmt.Close(); err != nil {
		return err
	}
	if err = stmt.Close(); err != nil {
		return err
	}
	if err = integer(ctx, stmt, 1); err == nil {
		return errors.New("closed logical statement executed")
	}
	if err = update.Close(); err != nil {
		return err
	}
	// CLOSE has no reply. Query the same final physical connection immediately;
	// an invented ACK or pending prepared result must fail decoding/count checks.
	if r.PreparedAfter, err = count(ctx, db); err != nil {
		return err
	}
	if r.PreparedAfter != r.PreparedBefore {
		return fmt.Errorf("native statements leaked: before=%d after=%d", r.PreparedBefore, r.PreparedAfter)
	}
	r.Checks = append(r.Checks, "native-statement-counter-restored-and-close-idempotent")
	return nil
}
func main() {
	r := report{Result: "FAIL"}
	if err := exercise(&r); err != nil {
		r.Error = err.Error()
	} else {
		r.Result = "PASS"
	}
	json.NewEncoder(os.Stdout).Encode(r)
	if r.Result != "PASS" {
		os.Exit(1)
	}
}
