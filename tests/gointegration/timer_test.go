//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"encoding/json"
	"math"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestAnalyzeTimerFreshAndFork(t *testing.T) {
	for _, pipe := range []bool{false, true} {
		name := "TCP"
		if pipe {
			name = "Pipe"
		}
		t.Run(name, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(t.Context(), time.Minute)
			defer cancel()
			root, err := mariamem.Start(ctx, mariamem.Options{})
			if err != nil {
				t.Fatal(err)
			}
			defer root.Close()
			open := func(d *mariamem.Database) *sql.DB {
				cfg, err := mysql.ParseDSN(d.DSN())
				if err != nil {
					t.Fatal(err)
				}
				if pipe {
					cfg.DialFunc = d.DialContext
				}
				connector, err := mysql.NewConnector(cfg)
				if err != nil {
					t.Fatal(err)
				}
				p := sql.OpenDB(connector)
				p.SetMaxOpenConns(1)
				return p
			}
			disconnect := func(p *sql.DB, d *mariamem.Database) {
				if err := p.Close(); err != nil {
					t.Fatal(err)
				}
				if err := d.WaitDisconnected(ctx); err != nil {
					t.Fatal(err)
				}
			}
			measure := func(d *mariamem.Database, mutate bool) {
				p := open(d)
				defer p.Close()
				for pair := 0; pair < 3; pair++ {
					for _, delayed := range []bool{false, true} {
						query := "ANALYZE FORMAT=JSON SELECT SUM(id) FROM timer_probe"
						if delayed {
							query = "ANALYZE FORMAT=JSON SELECT SUM(id + SLEEP(0.01)) FROM timer_probe"
						}
						start := time.Now()
						var raw string
						if err := p.QueryRowContext(ctx, query).Scan(&raw); err != nil {
							t.Fatal(err)
						}
						wall := float64(time.Since(start)) / float64(time.Millisecond)
						var result struct {
							Block struct {
								Total  *float64 `json:"r_total_time_ms"`
								Nested []struct {
									Table struct {
										Rows  float64 `json:"r_rows"`
										Loops float64 `json:"r_loops"`
									} `json:"table"`
								} `json:"nested_loop"`
							} `json:"query_block"`
						}
						if err := json.Unmarshal([]byte(raw), &result); err != nil {
							t.Fatal(err)
						}
						b := result.Block
						if len(b.Nested) != 1 || b.Nested[0].Table.Rows != 2 || b.Nested[0].Table.Loops != 1 {
							t.Fatalf("ANALYZE rows/loops: %s", raw)
						}
						if delayed && (b.Total == nil || math.IsNaN(*b.Total) || math.IsInf(*b.Total, 0) || *b.Total < 18 || *b.Total > wall+5) {
							t.Fatalf("ANALYZE timing outside [18, wall+5]ms; wall=%f report=%s", wall, raw)
						}
						var sum int
						if err := p.QueryRowContext(ctx, "SELECT SUM(id) FROM timer_probe").Scan(&sum); err != nil || sum != 3 {
							t.Fatalf("following SELECT: sum=%d error=%v", sum, err)
						}
					}
				}
				if mutate {
					if _, err := p.ExecContext(ctx, "INSERT INTO timer_probe VALUES(10)"); err != nil {
						t.Fatal(err)
					}
				}
				disconnect(p, d)
			}
			p := open(root)
			for _, q := range []string{"CREATE TABLE timer_probe(id INT PRIMARY KEY) ENGINE=InnoDB", "INSERT INTO timer_probe VALUES(1),(2)"} {
				if _, err := p.ExecContext(ctx, q); err != nil {
					p.Close()
					t.Fatal(err)
				}
			}
			disconnect(p, root)
			measure(root, false)
			snapshot, err := root.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
			if err != nil {
				t.Fatal(err)
			}
			defer snapshot.Close()
			for i := 0; i < 2; i++ {
				child, err := snapshot.Fork(ctx)
				if err != nil {
					t.Fatal(err)
				}
				func() {
					defer child.Close()
					measure(child, true)
					if err := child.Close(); err != nil {
						t.Fatal(err)
					}
				}()
			}
			if err := snapshot.Close(); err != nil {
				t.Fatal(err)
			}
			if err := root.Close(); err != nil {
				t.Fatal(err)
			}
		})
	}
}
