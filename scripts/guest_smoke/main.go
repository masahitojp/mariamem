// Generated-Go guest smoke; no external bundle or runtime selector.
package main

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		panic(err)
	}
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		panic(err)
	}
	var one int
	if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil {
		panic(err)
	}
	if one != 1 {
		panic(fmt.Sprintf("SELECT 1 returned %d", one))
	}
	if err := pool.Close(); err != nil {
		panic(err)
	}
	// Client Close returns before the server necessarily finishes COM_QUIT cleanup.
	if err := db.WaitDisconnected(ctx); err != nil {
		panic(err)
	}
	baseline, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		panic(err)
	}
	defer baseline.Close()
	child, err := baseline.Fork(ctx)
	if err != nil {
		panic(err)
	}
	pool, err = sql.Open("mysql", child.DSN())
	if err != nil {
		panic(err)
	}
	if err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil {
		panic(err)
	}
	if one != 1 {
		panic("child SELECT 1 failed")
	}
	if err := pool.Close(); err != nil {
		panic(err)
	}
	if err := child.Close(); err != nil {
		panic(err)
	}
	fmt.Println("Start, SELECT 1, Snapshot, Fork, SELECT 1, Close: PASS")
}
