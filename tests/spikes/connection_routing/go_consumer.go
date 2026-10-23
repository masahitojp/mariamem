// Experiment-only child-owned pools; accepts only the local fixture endpoints.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"os"
	"sync"
	"time"
)

func main() {
	if len(os.Args) != 5 {
		panic("two DSN/marker pairs required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	var wg sync.WaitGroup
	out := make([]map[string]any, 2)
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func(i int) {
			defer wg.Done()
			cfg, err := mysql.ParseDSN(os.Args[1+i*2])
			must(err)
			cfg.InterpolateParams = false
			c, err := mysql.NewConnector(cfg)
			must(err)
			db := sql.OpenDB(c)
			defer db.Close()
			db.SetMaxOpenConns(2)
			stmt, err := db.PrepareContext(ctx, "SELECT value FROM marker WHERE id=?")
			must(err)
			defer stmt.Close()
			var explicit, implicit string
			must(stmt.QueryRowContext(ctx, 1).Scan(&explicit))
			must(db.QueryRowContext(ctx, "SELECT value FROM marker WHERE id=?", 1).Scan(&implicit))
			if explicit != os.Args[2+i*2] || implicit != explicit {
				panic("wrong target")
			}
			tx, err := db.BeginTx(ctx, nil)
			must(err)
			ts, err := tx.PrepareContext(ctx, "INSERT INTO writes(value) VALUES (?)")
			must(err)
			_, err = ts.ExecContext(ctx, "rollback-go")
			must(err)
			must(ts.Close())
			must(tx.Rollback())
			var n int
			must(db.QueryRowContext(ctx, "SELECT COUNT(*) FROM writes WHERE value=?", "rollback-go").Scan(&n))
			if n != 0 {
				panic("rollback failed")
			}
			_, err = db.ExecContext(ctx, "INSERT INTO writes(value) VALUES (?)", "commit-go-"+explicit)
			must(err)
			conn, err := db.Conn(ctx)
			must(err)
			cs, err := conn.PrepareContext(ctx, "SELECT DATABASE()")
			must(err)
			var schema string
			must(cs.QueryRowContext(ctx).Scan(&schema))
			must(cs.Close())
			must(conn.Close())
			if schema != "app" {
				panic("schema changed")
			}
			out[i] = map[string]any{"marker": explicit, "implicit": implicit, "schema": schema, "rollback_rows": n, "owned_pool": true, "interpolate": false}
		}(i)
	}
	wg.Wait()
	b, err := json.Marshal(out)
	must(err)
	fmt.Println(string(b))
}
func must(err error) {
	if err != nil {
		panic(err)
	}
}
