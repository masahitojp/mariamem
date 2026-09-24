// Standalone public API consumer, copied into a fresh external module by the harness.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func event(step, status string, err error, details any) {
	v := map[string]any{"step": step, "status": status}
	if err != nil {
		v["error"] = err.Error()
	}
	if details != nil {
		v["details"] = details
	}
	_ = json.NewEncoder(os.Stdout).Encode(v)
}
func step(name string, fn func() error) error {
	event(name, "RUNNING", nil, nil)
	err := fn()
	if err != nil {
		event(name, "FAIL", err, nil)
	} else {
		event(name, "PASS", nil, nil)
	}
	return err
}
func run(native string) (result error) {
	parent, stop := signal.NotifyContext(context.Background(), os.Interrupt)
	defer stop()
	ctx, cancel := context.WithTimeout(parent, 5*time.Minute)
	defer cancel()
	var dbs []*mariamem.Database
	var pools []*sql.DB
	var snap *mariamem.Snapshot
	defer func() {
		err := step("close_cleanup", func() error {
			var errs []error
			for _, p := range pools {
				errs = append(errs, p.Close())
			}
			for _, db := range dbs {
				errs = append(errs, db.Close(), db.Close())
				if !db.Closed() {
					errs = append(errs, errors.New("database remains open"))
				}
			}
			if snap != nil {
				errs = append(errs, snap.Close(), snap.Close())
				if _, e := os.Stat(filepath.Dir(snap.Path())); !os.IsNotExist(e) {
					errs = append(errs, fmt.Errorf("temporary snapshot still present: %v", e))
				}
			}
			entries, e := os.ReadDir(os.TempDir())
			errs = append(errs, e)
			for _, f := range entries {
				if strings.HasPrefix(f.Name(), "mariamem-") {
					errs = append(errs, fmt.Errorf("runtime temporary directory remains: %s", f.Name()))
				}
			}
			return errors.Join(errs...)
		})
		result = errors.Join(result, err)
	}()
	if err := step("NativeDir", func() error {
		if !filepath.IsAbs(native) {
			return errors.New("explicit absolute NativeDir required")
		}
		return nil
	}); err != nil {
		return err
	}
	var source *mariamem.Database
	if err := step("Start", func() (err error) {
		source, err = mariamem.Start(ctx, mariamem.Options{NativeDir: native})
		if source != nil {
			dbs = append(dbs, source)
		}
		return err
	}); err != nil {
		return err
	}
	open := func(db *mariamem.Database) (*sql.DB, error) {
		config, err := mysql.ParseDSN(db.DSN())
		if err != nil {
			return nil, err
		}
		// Interpolation is text-protocol compatibility, not prepared statement support.
		if !config.InterpolateParams {
			return nil, errors.New("DSN lacks interpolateParams")
		}
		p, err := sql.Open("mysql", db.DSN())
		if err != nil {
			return nil, err
		}
		pools = append(pools, p)
		p.SetMaxOpenConns(1)
		return p, p.PingContext(ctx)
	}
	var pool *sql.DB
	if err := step("database_sql_connection", func() (err error) { pool, err = open(source); return err }); err != nil {
		return err
	}
	if err := step("SELECT_1", func() error {
		var n int
		if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&n); err != nil {
			return err
		}
		if n != 1 {
			return fmt.Errorf("got %d", n)
		}
		return nil
	}); err != nil {
		return err
	}
	if err := step("MariaDB_version", func() error {
		var version string
		if err := pool.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version); err != nil {
			return err
		}
		event("MariaDB_version", "INFO", nil, map[string]string{"version": version})
		if !strings.Contains(version, "MariaDB") {
			return fmt.Errorf("unexpected version: %s", version)
		}
		return nil
	}); err != nil {
		return err
	}
	count := func(p *sql.DB, want int) error {
		var n int
		if err := p.QueryRowContext(ctx, "SELECT COUNT(*) FROM items").Scan(&n); err != nil {
			return err
		}
		if n != want {
			return fmt.Errorf("count=%d want=%d", n, want)
		}
		return nil
	}
	if err := step("InnoDB_transaction", func() error {
		if _, err := pool.ExecContext(ctx, "CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
			return err
		}
		var engine string
		if err := pool.QueryRowContext(ctx, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='items'").Scan(&engine); err != nil {
			return err
		}
		if engine != "InnoDB" {
			return fmt.Errorf("engine=%s", engine)
		}
		tx, err := pool.BeginTx(ctx, nil)
		if err != nil {
			return err
		}
		defer tx.Rollback()
		if _, err = tx.ExecContext(ctx, "INSERT INTO items VALUES (?)", 1); err != nil {
			return err
		}
		if err = tx.Commit(); err != nil {
			return err
		}
		return count(pool, 1)
	}); err != nil {
		return err
	}
	if err := step("WaitDisconnected", func() error {
		if err := pool.Close(); err != nil {
			return err
		}
		return source.WaitDisconnected(ctx)
	}); err != nil {
		return err
	}
	if err := step("Snapshot", func() (err error) { snap, err = source.Snapshot(ctx, mariamem.SnapshotOptions{}); return err }); err != nil {
		return err
	}
	if err := step("source_closed", func() error {
		if !source.Closed() {
			return errors.New("snapshot did not close source")
		}
		return source.Close()
	}); err != nil {
		return err
	}
	var a, b *mariamem.Database
	for _, item := range []struct {
		name string
		dest **mariamem.Database
	}{{"Fork_A", &a}, {"Fork_B", &b}} {
		if err := step(item.name, func() error {
			db, err := snap.Fork(ctx)
			if db != nil {
				dbs = append(dbs, db)
			}
			*item.dest = db
			return err
		}); err != nil {
			return err
		}
	}
	return step("fork_isolation", func() error {
		ap, err := open(a)
		if err != nil {
			return err
		}
		bp, err := open(b)
		if err != nil {
			return err
		}
		if err = count(ap, 1); err != nil {
			return err
		}
		if err = count(bp, 1); err != nil {
			return err
		}
		if _, err = ap.ExecContext(ctx, "INSERT INTO items VALUES (?)", 2); err != nil {
			return err
		}
		if err = count(ap, 2); err != nil {
			return err
		}
		return count(bp, 1)
	})
}
func main() {
	if len(os.Args) != 2 {
		event("NativeDir", "FAIL", errors.New("usage: consumer /absolute/native"), nil)
		os.Exit(1)
	}
	err := run(os.Args[1])
	if err != nil {
		event("consumer", "FAIL", err, nil)
		os.Exit(1)
	}
	event("consumer", "PASS", nil, nil)
}
