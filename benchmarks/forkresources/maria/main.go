package main

import (
	"context"
	"database/sql"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/forkresources/probe"
)

func wrap(d *mariamem.Database) *probe.Database {
	return &probe.Database{
		Open: func(route string) (*sql.DB, error) {
			if route != "tcp" {
				return nil, fmt.Errorf("unsupported route %s", route)
			}
			cfg, e := mysql.ParseDSN(d.DSN())
			if e != nil {
				return nil, e
			}
			c, e := mysql.NewConnector(cfg)
			if e != nil {
				return nil, e
			}
			return sql.OpenDB(c), nil
		},
		Wait: d.WaitDisconnected, Close: d.Close,
		Snapshot: func(ctx context.Context, _ int) (*probe.Snapshot, error) {
			s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{})
			if e != nil {
				return nil, e
			}
			return &probe.Snapshot{Close: s.Close, Fork: func(ctx context.Context) (*probe.Database, error) {
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
