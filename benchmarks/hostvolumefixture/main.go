// Prepare the normal canonical 1000-row fixture through the public Go API.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"os"
	"strings"
	"time"
)

func run() error {
	if len(os.Args) != 3 {
		return fmt.Errorf("usage: hostvolumefixture NATIVE_DIR SNAPSHOT_DIR")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	begin := time.Now()
	db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: os.Args[1]})
	if err != nil {
		return err
	}
	defer db.Close()
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer pool.Close()
	if _, err = pool.ExecContext(ctx, "CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB"); err != nil {
		return err
	}
	tx, err := pool.BeginTx(ctx, nil)
	if err != nil {
		return err
	}
	defer tx.Rollback()
	values := make([]string, 1000)
	args := make([]any, 0, 2000)
	for i := range values {
		values[i] = "(?,?)"
		args = append(args, i, strings.Repeat("x", 32))
	}
	if _, err = tx.ExecContext(ctx, "INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...); err != nil {
		return err
	}
	if err = tx.Commit(); err != nil {
		return err
	}
	if err = pool.Close(); err != nil {
		return err
	}
	if err = db.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{Destination: os.Args[2]})
	if err != nil {
		return err
	}
	defer saved.Close()
	fork, err := saved.Fork(ctx)
	if err != nil {
		return err
	}
	defer fork.Close()
	client, err := sql.Open("mysql", fork.DSN())
	if err != nil {
		return err
	}
	defer client.Close()
	var count int
	if err = client.QueryRowContext(ctx, "SELECT COUNT(*) FROM benchmark_rows").Scan(&count); err != nil {
		return err
	}
	if count != 1000 {
		return fmt.Errorf("fixture count %d", count)
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]any{"rows": count, "snapshot": saved.Path(), "setup_and_public_fork_check_seconds": time.Since(begin).Seconds()})
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
