package main

import (
	"context"
	"database/sql"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/issue123baseline/probe"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
)

func wrap(d *mariamem.Database, ctx context.Context) *probe.Database {
	return &probe.Database{
		Open: func(route string) (*sql.DB, error) {
			if route != "pipe" {
				return nil, fmt.Errorf("unsupported route %s", route)
			}
			cfg, e := mysql.ParseDSN(d.DSN())
			if e != nil {
				return nil, e
			}
			cfg.DialFunc = d.DialContext
			c, e := mysql.NewConnector(cfg)
			if e != nil {
				return nil, e
			}
			return sql.OpenDB(c), nil
		},
		Wait: d.WaitDisconnected, Close: func() error { return observeClose(d, ctx) },
		Snapshot: func(ctx context.Context, p int) (*probe.Snapshot, error) {
			s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: p})
			if e != nil {
				return nil, e
			}
			return &probe.Snapshot{MaxForks: s.MaxForks(), Close: s.Close, Fork: func(ctx context.Context) (*probe.Database, error) {
				c, e := s.Fork(ctx)
				if e != nil {
					return nil, e
				}
				return wrap(c, ctx), nil
			}}, nil
		},
	}
}
func main() {
	probe.CleanupStats = base.MemoryMappingStats
	probe.Main("mariamem", func(ctx context.Context) (*probe.Database, error) {
		d, e := mariamem.Start(ctx, mariamem.Options{})
		if e != nil {
			return nil, e
		}
		return wrap(d, ctx), nil
	})
}
