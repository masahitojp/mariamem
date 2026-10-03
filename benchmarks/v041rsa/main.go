// Disposable v0.4.0 RSA/startup diagnostic. No production runtime changes.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"os"
	"syscall"
	"time"
)

func cpu() float64 {
	var r syscall.Rusage
	if e := syscall.Getrusage(syscall.RUSAGE_SELF, &r); e != nil {
		panic(e)
	}
	return float64(r.Utime.Sec+r.Stime.Sec) + float64(r.Utime.Usec+r.Stime.Usec)/1e6
}
func one(ctx context.Context, p *sql.DB) {
	var n int
	if e := p.QueryRowContext(ctx, "SELECT 1").Scan(&n); e != nil || n != 1 {
		panic(fmt.Sprint(n, e))
	}
}
func main() {
	if len(os.Args) > 1 && os.Args[1] == "auth-check" {
		generatedgo.Run([]string{"probe", "auth-check"})
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	c := cpu()
	t := time.Now()
	db, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		panic(e)
	}
	ready := time.Since(t).Seconds()
	readyCPU := cpu() - c
	p, e := sql.Open("mysql", db.DSN())
	if e != nil {
		panic(e)
	}
	one(ctx, p)
	first := time.Since(t).Seconds()
	firstCPU := cpu() - c
	// Separate functional smoke from measured first-SQL boundary.
	q, e := sql.Open("mysql", db.DSN())
	if e != nil {
		panic(e)
	}
	one(ctx, q)
	if e = q.Close(); e != nil {
		panic(e)
	}
	cfg, e := mysql.ParseDSN(db.DSN())
	if e != nil {
		panic(e)
	}
	cfg.Passwd = "invalid-rsa-probe-password"
	bad, e := sql.Open("mysql", cfg.FormatDSN())
	if e != nil {
		panic(e)
	}
	if e = bad.PingContext(ctx); e == nil {
		panic("bad credentials accepted")
	}
	bad.Close()
	p.Close()
	if e = db.WaitDisconnected(ctx); e != nil {
		panic(e)
	}
	p, e = sql.Open("mysql", db.DSN())
	if e != nil {
		panic(e)
	}
	one(ctx, p)
	p.Close()
	if e = db.Close(); e != nil {
		panic(e)
	}
	if e = db.Close(); e != nil {
		panic(e)
	}
	json.NewEncoder(os.Stdout).Encode(map[string]any{"ready_seconds": ready, "first_sql_seconds": first, "ready_cpu_seconds": readyCPU, "first_sql_cpu_seconds": firstCPU, "auth_reconnect_two_sessions": "PASS", "rsa_option": "OFF (released baseline)", "runtime": "direct-linked generated-Go"})
}
