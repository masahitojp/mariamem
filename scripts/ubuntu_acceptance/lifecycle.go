// Copied to an external public-module consumer by Ubuntu product acceptance.
package main

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func run() error {
	native := os.Args[1]
	var invalid *mariamem.HostError
	if _, err := mariamem.Start(context.Background(), mariamem.Options{NativeDir: native + "/missing"}); !errors.As(err, &invalid) || invalid.Code != "native_unavailable" {
		return fmt.Errorf("missing native diagnostic: %v", err)
	}
	for _, cancelled := range []bool{false, true} {
		db, err := mariamem.Start(context.Background(), mariamem.Options{NativeDir: native})
		if err != nil {
			return err
		}
		pool, err := sql.Open("mysql", db.DSN())
		if err != nil {
			db.Close()
			return err
		}
		if _, err = pool.Exec("SELECT definitely_missing_column"); err == nil || db.Err() != nil {
			pool.Close()
			db.Close()
			return fmt.Errorf("ordinary SQL invalidation: %v", err)
		}
		var ctx context.Context
		var cancel context.CancelFunc
		cause := context.DeadlineExceeded
		if cancelled {
			ctx, cancel = context.WithCancel(context.Background())
			cause = context.Canceled
			time.AfterFunc(time.Second, cancel)
		} else {
			ctx, cancel = context.WithTimeout(context.Background(), time.Second)
		}
		_, err = pool.ExecContext(ctx, "SELECT SLEEP(10)")
		cancel()
		if !errors.Is(err, cause) {
			pool.Close()
			db.Close()
			return fmt.Errorf("client cause: %v", err)
		}
		deadline := time.Now().Add(5 * time.Second)
		for db.Err() == nil && time.Now().Before(deadline) {
			time.Sleep(10 * time.Millisecond)
		}
		if !db.Closed() || !errors.Is(db.Err(), mariamem.ErrUnusable) {
			pool.Close()
			db.Close()
			return fmt.Errorf("instance not invalidated: %v", db.Err())
		}
		if _, err = db.Snapshot(context.Background(), mariamem.SnapshotOptions{}); !errors.Is(err, mariamem.ErrUnusable) {
			pool.Close()
			db.Close()
			return fmt.Errorf("snapshot invalidation: %v", err)
		}
		pool.Close()
		if err = db.Close(); err != nil {
			return err
		}
		if err = db.Close(); err != nil {
			return err
		}
	}
	return nil
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("Ubuntu public Go lifecycle: PASS")
}
