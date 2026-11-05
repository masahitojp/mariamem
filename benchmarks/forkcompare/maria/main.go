package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/forkcompare/probe"
	"github.com/masahitojp/mariamem/internal/timing"
	"os"
	"path/filepath"
)

func wrap(d *mariamem.Database) *probe.Database {
	return &probe.Database{
		Open: func(route string) (*sql.DB, error) {
			if route != "tcp" && route != "pipe" {
				return nil, fmt.Errorf("unsupported route %s", route)
			}
			cfg, e := mysql.ParseDSN(d.DSN())
			if e != nil {
				return nil, e
			}
			if route == "pipe" {
				cfg.DialFunc = d.DialContext
			}
			c, e := mysql.NewConnector(cfg)
			if e != nil {
				return nil, e
			}
			return sql.OpenDB(c), nil
		},
		Wait: d.WaitDisconnected, Close: d.Close,
		Snapshot: func(ctx context.Context, p int) (*probe.Snapshot, error) {
			s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: p})
			if e != nil {
				return nil, e
			}
			return &probe.Snapshot{Close: s.Close, Fork: func(ctx context.Context) (*probe.Database, error) {
				ctx = timing.WithRecorder(ctx, func(trace timing.Trace) {
					id, ok := ctx.Value("forkstages_child").(int)
					if !ok {
						panic("missing child index")
					}
					data, err := json.Marshal(trace)
					if err != nil {
						panic(err)
					}
					if err = os.WriteFile(filepath.Join(os.Getenv("MARIAMEM_TIMING_DIR"), fmt.Sprintf("child-%03d-%s.json", id, trace.Operation)), data, 0600); err != nil {
						panic(err)
					}
				})
				c, e := s.Fork(ctx)
				if e != nil {
					return nil, e
				}
				return wrap(c), nil
			}}, nil
		},
	}
}
func main() {
	probe.Main("mariamem", func(ctx context.Context) (*probe.Database, error) {
		d, e := mariamem.Start(ctx, mariamem.Options{})
		if e != nil {
			return nil, e
		}
		return wrap(d), nil
	})
}
