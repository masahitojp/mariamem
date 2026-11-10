package store_test

import (
	"context"
	"database/sql"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/masahitojp/mariamem/benchmarks/shoprunner/internal/trace"
	"github.com/shibukawa/pgmem"
)

func backendName() string { return "pgmem" }
func wrap(d *pgmem.Server) *database {
	return &database{open: func() *sql.DB {
		cfg, e := pgx.ParseConfig(d.DSN())
		must(e)
		cfg.DialFunc = d.Dial
		return stdlib.OpenDB(*cfg)
	}, close: d.Close, snapshot: func() (func() (*database, error), func() error, error) {
		ctx, cancel := timeout()
		defer cancel()
		s, e := d.Snapshot(ctx, pgmem.SnapshotOptions{MaxForks: 5})
		if e != nil {
			return nil, nil, e
		}
		return func() (*database, error) {
			ctx, cancel := timeout()
			defer cancel()
			c, e := s.Fork(ctx)
			if e != nil {
				return nil, e
			}
			return wrap(c), nil
		}, s.Close, nil
	}}
}
func startBackend(ctx context.Context) (*database, error) {
	d, e := pgmem.Start(ctx, pgmem.Options{Database: "app"})
	if e != nil {
		return nil, e
	}
	return wrap(d), nil
}
func checkSettings(p *sql.DB, r *trace.Recorder) {
	var v string
	must(p.QueryRow("SHOW server_version").Scan(&v))
	r.Set("server_version", v)
}
func checkCleanup(r *trace.Recorder) {
	r.Set("cleanup", "public Close completed; full-resource retirement not asserted")
}
