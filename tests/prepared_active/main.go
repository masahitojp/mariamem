// P4 active EXECUTE cancellation consumer; the controller must observe the SQL
// marker before cancelling. This uses the fixed public database/sql driver.
package main

import (
	"bufio"
	"context"
	"database/sql"
	"database/sql/driver"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"os"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
)

type event struct {
	Phase           string   `json:"phase"`
	ConnectionID    uint64   `json:"connection_id,omitempty"`
	Kind            string   `json:"kind,omitempty"`
	Result          string   `json:"result,omitempty"`
	Error           string   `json:"error,omitempty"`
	OpenAfter       int      `json:"open_after"`
	ExecuteError    string   `json:"execute_error,omitempty"`
	CleanupErrors   []string `json:"cleanup_errors,omitempty"`
	TransportFailed bool     `json:"transport_failed,omitempty"`
}

func emit(e event) {
	if err := json.NewEncoder(os.Stdout).Encode(e); err != nil {
		panic(err)
	}
}
func run(report *event) (err error) {
	cfg, err := mysql.ParseDSN(os.Getenv("MARIAMEM_P4_ACTIVE_DSN"))
	if err != nil {
		return err
	}
	var resetConn *net.TCPConn
	if os.Getenv("MARIAMEM_P4_ACTIVE_KIND") == "reset" {
		mysql.RegisterDialContext("p4-reset", func(ctx context.Context, addr string) (net.Conn, error) {
			c, e := (&net.Dialer{}).DialContext(ctx, "tcp", addr)
			if e != nil {
				return nil, e
			}
			resetConn = c.(*net.TCPConn)
			return c, nil
		})
		cfg.Net = "p4-reset"
	}
	cfg.InterpolateParams = true // Explicit Prepare must not turn into text SQL.
	pool, err := sql.Open("mysql", cfg.FormatDSN())
	if err != nil {
		return err
	}
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
	defer func() {
		err = errors.Join(err, pool.Close())
		report.OpenAfter = pool.Stats().OpenConnections
		if report.OpenAfter != 0 {
			err = errors.Join(err, fmt.Errorf("pool retains %d connections", report.OpenAfter))
		}
	}()
	outer, cancelOuter := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancelOuter()
	conn, err := pool.Conn(outer)
	if err != nil {
		return err
	}
	defer func() {
		e := conn.Close()
		if e != nil {
			report.CleanupErrors = append(report.CleanupErrors, e.Error())
		}
		if !errors.Is(e, sql.ErrConnDone) && !(os.Getenv("MARIAMEM_P4_ACTIVE_KIND") == "reset" && errors.Is(e, mysql.ErrInvalidConn)) {
			err = errors.Join(err, e)
		}
	}()
	var id uint64
	if err = conn.QueryRowContext(outer, "SELECT CONNECTION_ID()").Scan(&id); err != nil {
		return err
	}
	tx, err := conn.BeginTx(outer, nil)
	if err != nil {
		return err
	}
	defer func() {
		e := tx.Rollback()
		if e != nil {
			report.CleanupErrors = append(report.CleanupErrors, e.Error())
		}
		if e != nil && !(os.Getenv("MARIAMEM_P4_ACTIVE_KIND") == "reset" && errors.Is(e, mysql.ErrInvalidConn)) && !errors.Is(e, sql.ErrTxDone) && !errors.Is(e, driver.ErrBadConn) && !errors.Is(e, context.Canceled) && !errors.Is(e, context.DeadlineExceeded) {
			err = errors.Join(err, e)
		}
	}()
	stmt, err := tx.PrepareContext(outer, "CALL test.p4_active(?)")
	if err != nil {
		return err
	}
	defer func() {
		e := stmt.Close()
		if e != nil {
			report.CleanupErrors = append(report.CleanupErrors, e.Error())
		}
		if !errors.Is(e, driver.ErrBadConn) && !(os.Getenv("MARIAMEM_P4_ACTIVE_KIND") == "reset" && errors.Is(e, mysql.ErrInvalidConn)) {
			err = errors.Join(err, e)
		}
	}()
	kind := os.Getenv("MARIAMEM_P4_ACTIVE_KIND")
	report.Kind = kind
	var ctx context.Context
	var cancel context.CancelFunc
	if kind == "deadline" {
		ctx, cancel = context.WithTimeout(outer, 3*time.Second)
	} else if kind == "cancel" || kind == "reset" {
		ctx, cancel = context.WithCancel(outer)
	} else {
		return fmt.Errorf("unknown kind %q", kind)
	}
	defer cancel()
	completed := make(chan error, 1)
	emit(event{Phase: "prepared", ConnectionID: id, Kind: kind})
	go func() { _, e := stmt.ExecContext(ctx, 5); completed <- e }()
	emit(event{Phase: "submitted", ConnectionID: id, Kind: kind})
	line, e := bufio.NewReader(os.Stdin).ReadString('\n')
	if e != nil {
		cancel()
		<-completed
		return e
	}
	want := "observe"
	if kind == "cancel" || kind == "reset" {
		want = kind
	}
	if strings.TrimSpace(line) != want {
		cancel()
		<-completed
		return fmt.Errorf("controller did not witness running SQL: %q", line)
	}
	if kind == "cancel" {
		cancel()
	} else if kind == "reset" {
		if resetConn == nil {
			return errors.New("missing owned TCP transport")
		}
		if e = resetConn.SetLinger(0); e != nil {
			return e
		}
		if e = resetConn.Close(); e != nil {
			return e
		}
	}
	select {
	case e = <-completed:
	case <-outer.Done():
		return outer.Err()
	}
	if e == nil {
		return errors.New("cancelled EXECUTE returned success")
	}
	report.ExecuteError = e.Error()
	if kind == "reset" {
		report.TransportFailed = errors.Is(e, mysql.ErrInvalidConn) || errors.Is(e, driver.ErrBadConn)
		if !report.TransportFailed {
			return fmt.Errorf("unexpected reset outcome: %w", e)
		}
	}
	expected := context.Canceled
	if kind == "deadline" {
		expected = context.DeadlineExceeded
	}
	if kind != "reset" && !errors.Is(e, expected) {
		return fmt.Errorf("expected %v, got %w", expected, e)
	}
	return nil
}
func main() {
	r := event{Phase: "finished", Result: "PASS"}
	if err := run(&r); err != nil {
		r.Result = "FAIL"
		r.Error = err.Error()
	}
	emit(r)
	if r.Result != "PASS" {
		os.Exit(1)
	}
}
