package store_test

import (
	"context"
	"database/sql"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/issue88modelcase/internal/trace"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime/pprof"
	"strconv"
	"sync/atomic"
)

var dbSequence atomic.Int32

func backendName() string { return "mariamem-" + os.Getenv("ISSUE88_POOL_MIB") }
func labeledStart(ctx context.Context, f func(context.Context) (*mariamem.Database, error)) (*database, error) {
	id := fmt.Sprintf("issue68-db-%d", dbSequence.Add(1))
	var d *mariamem.Database
	var err error
	pprof.Do(ctx, pprof.Labels("db_id", id), func(ctx context.Context) { d, err = f(ctx) })
	if err != nil {
		return nil, err
	}
	return wrap(d, id), nil
}
func wrap(d *mariamem.Database, id string) *database {
	return &database{id: id, open: func() *sql.DB {
		cfg, e := mysql.ParseDSN(d.DSN())
		must(e)
		cfg.DialFunc = d.DialContext
		cfg.ClientFoundRows = true
		connector, e := mysql.NewConnector(cfg)
		must(e)
		return sql.OpenDB(connector)
	}, close: d.Close, wait: func() error { ctx, cancel := timeout(); defer cancel(); return d.WaitDisconnected(ctx) }, snapshot: func() (func() (*database, error), func() error, error) {
		ctx, cancel := timeout()
		defer cancel()
		s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 9})
		if e != nil {
			return nil, nil, e
		}
		return func() (*database, error) { ctx, cancel := timeout(); defer cancel(); return labeledStart(ctx, s.Fork) }, s.Close, nil
	}}
}
func startBackend(ctx context.Context) (*database, error) {
	base.InitReadObservation(fx.rec.OffsetUS)
	return labeledStart(ctx, func(ctx context.Context) (*mariamem.Database, error) { return mariamem.Start(ctx, mariamem.Options{}) })
}
func checkSettings(p *sql.DB, r *trace.Recorder) {
	for _, key := range []string{"innodb_buffer_pool_size", "innodb_buffer_pool_size_max"} {
		var name string
		var n int64
		must(p.QueryRow("SHOW VARIABLES LIKE ?", key).Scan(&name, &n))
		m, e := strconv.Atoi(os.Getenv("ISSUE88_POOL_MIB"))
		must(e)
		if n != int64(m)<<20 {
			panic(fmt.Sprint(key, n))
		}
		r.Set(key, fmt.Sprint(n))
	}
	var v string
	must(p.QueryRow("SELECT VERSION()").Scan(&v))
	r.Set("server_version", v)
}
func checkCleanup(r *trace.Recorder) {
	n := base.MemoryMappingStats()["active_mappings"]
	r.Set("active_mappings_after", fmt.Sprint(n))
	if n != 0 {
		panic("mapping leak")
	}
}
