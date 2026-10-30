// Copied to an external module to verify the candidate through ordinary imports.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"os"
	"time"
)

var sourceSmoke = flag.Bool("source-smoke", false, "run within source checkout instead of installed acceptance")

func main() {
	flag.Parse()
	if err := run(); err != nil {
		panic(err)
	}
}
func run() error {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		return err
	}
	defer source.Close()
	db, err := sql.Open("mysql", source.DSN())
	if err != nil {
		return err
	}
	if _, err = db.ExecContext(ctx, "CREATE TABLE live_user(n INT)"); err != nil {
		db.Close()
		return err
	}
	if _, err = db.ExecContext(ctx, "INSERT INTO live_user VALUES(1)"); err != nil {
		db.Close()
		return err
	}
	db.Close()
	if err = source.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer saved.Close()
	live, err := saved.Live(ctx)
	if live != nil {
		defer live.Close()
	}
	if err != nil {
		return err
	}
	info := live.ConnectionInfo()
	db, err = sql.Open("mysql", live.DSN())
	if err != nil {
		return err
	}
	if _, err = db.ExecContext(ctx, "INSERT INTO live_user VALUES(2)"); err != nil {
		db.Close()
		return err
	}
	db.Close()
	if err = live.Reset(ctx, mariamem.ResetOptions{}); err != nil {
		return err
	}
	db, err = sql.Open("mysql", live.DSN())
	if err != nil {
		return err
	}
	defer db.Close()
	conn, err := db.Conn(ctx)
	if err != nil {
		return err
	}
	defer conn.Close()
	var sum int
	if err = conn.QueryRowContext(ctx, "SELECT SUM(n) FROM live_user").Scan(&sum); err != nil {
		return err
	}
	if sum != 1 {
		panic("committed row leaked")
	}
	err = live.Reset(ctx, mariamem.ResetOptions{DrainTimeout: 5 * time.Millisecond})
	if !errors.Is(err, mariamem.ErrBusy) {
		panic("held connection did not refuse reset")
	}
	conn.Close()
	db.Close()
	if err = live.Reset(ctx, mariamem.ResetOptions{}); err != nil {
		return err
	}
	if live.ConnectionInfo() != info || live.Status().Generation != 2 {
		panic("endpoint or generation changed incorrectly")
	}
	if err = saved.Close(); err != nil {
		return err
	}
	if err = live.Reset(ctx, mariamem.ResetOptions{}); !errors.Is(err, mariamem.ErrClosed) {
		panic("closed parent accepted reset")
	}
	if err = live.Close(); err != nil {
		return err
	}
	result := "PASS_EXTERNAL_GO_LIVE"
	if *sourceSmoke {
		result = "PASS_SOURCE_GO_LIVE"
	}
	return json.NewEncoder(os.Stdout).Encode(map[string]any{"result": result, "sum_after_reset": sum, "busy_refused": true, "closed_parent_refused": true, "source_consumed": source.Closed()})
}
