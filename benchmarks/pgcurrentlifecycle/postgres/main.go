package main

import (
	"context"
	"database/sql"
	"fmt"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/masahitojp/mariamem/benchmarks/pgcurrentlifecycle/probe"
	"github.com/shibukawa/pgmem"
)

func wrap(d *pgmem.Server) *probe.Database {
	return &probe.Database{
		Open: func(route string) (*sql.DB, error) {
			cfg, e := pgx.ParseConfig(d.DSN())
			if e != nil {
				return nil, e
			}
			switch route {
			case "pipe":
				cfg.DialFunc = d.Dial
			case "tcp":
			default:
				return nil, fmt.Errorf("unsupported route %s", route)
			}
			return stdlib.OpenDB(*cfg), nil
		},
		Close: d.Close,
		Snapshot: func(ctx context.Context, p int) (*probe.Snapshot, error) {
			s, e := d.Snapshot(ctx, pgmem.SnapshotOptions{MaxForks: p})
			if e != nil {
				return nil, e
			}
			return &probe.Snapshot{MaxForks: s.MaxForks(), Close: s.Close, Fork: func(ctx context.Context) (*probe.Database, error) {
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
	probe.Main("pgmem", func(ctx context.Context) (*probe.Database, error) {
		d, e := pgmem.Start(ctx, pgmem.Options{Database: "test"})
		if e != nil {
			return nil, e
		}
		return wrap(d), nil
	})
}
