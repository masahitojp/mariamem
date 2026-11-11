package store_test

import (
	"context"
	"database/sql"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/benchmarks/shopforkstagerunner/internal/trace"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"strconv"
)

func backendName() string { return "mariamem-" + os.Getenv("ISSUE88_POOL_MIB") }
func wrap(d *mariamem.Database) *database {
	return &database{open: func() *sql.DB {
		cfg, e := mysql.ParseDSN(d.DSN())
		must(e)
		cfg.DialFunc = d.DialContext
		cfg.ClientFoundRows = true
		connector, e := mysql.NewConnector(cfg)
		must(e)
		return sql.OpenDB(connector)
	}, close: d.Close, wait: func() error { ctx, cancel := timeout(); defer cancel(); return d.WaitDisconnected(ctx) }, snapshot: func() (func(string) (*database, error), func() error, error) {
		ctx, cancel := timeout()
		defer cancel()
		s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: parallelism() + 1})
		if e != nil {
			return nil, nil, e
		}
		return func(lane string) (*database, error) {
			ctx, cancel := timeout()
			defer cancel()
			c, e := s.Fork(observeContext(ctx, lane))
			if e != nil {
				return nil, e
			}
			return wrap(c), nil
		}, s.Close, nil
	}}
}
func startBackend(ctx context.Context) (*database, error) {
	d, e := mariamem.Start(observeContext(ctx, "root"), mariamem.Options{})
	if e != nil {
		return nil, e
	}
	return wrap(d), nil
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
	var name string
	var readThreads int
	must(p.QueryRow("SHOW VARIABLES LIKE 'innodb_read_io_threads'").Scan(&name, &readThreads))
	if readThreads != 1 {
		panic("unexpected read IO threads")
	}
	r.Set("innodb_read_io_threads", strconv.Itoa(readThreads))
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
