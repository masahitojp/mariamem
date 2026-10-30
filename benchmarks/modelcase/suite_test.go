package modelcase

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"strconv"
	"strings"
	"sync"
	"testing"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/mariamemtest"
	tc "github.com/testcontainers/testcontainers-go/modules/mariadb"
)

type span struct {
	Stage    string  `json:"stage"`
	Case     string  `json:"case"`
	Slot     int     `json:"slot"`
	Start    float64 `json:"start_ms"`
	Duration float64 `json:"duration_ms"`
}
type worker struct {
	DB    *sql.DB
	Dirty bool
	Index int
}

var origin time.Time
var traceMu sync.Mutex
var spans []span
var report map[string]any
var owner *mariamemtest.Fixture
var shared *sql.DB
var workers chan *worker
var lanes chan int
var mode string
var parallel int
var ctx context.Context
var resultMu sync.Mutex
var observed map[string]bool

func event(stage, cas string, slot int, begin time.Time) {
	traceMu.Lock()
	defer traceMu.Unlock()
	spans = append(spans, span{stage, cas, slot, float64(begin.Sub(origin)) / 1e6, float64(time.Since(begin)) / 1e6})
}
func timed(stage, cas string, slot int, fn func() error) error {
	at := time.Now()
	defer event(stage, cas, slot, at)
	return fn()
}
func open(dsn string) (*sql.DB, error) {
	c, err := mysql.ParseDSN(dsn)
	if err != nil {
		return nil, err
	}
	c.InterpolateParams = false
	c.ParseTime = true
	connector, err := mysql.NewConnector(c)
	if err != nil {
		return nil, err
	}
	p := sql.OpenDB(connector)
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	return p, nil
}
func settings(db *sql.DB) error {
	var version string
	if err := db.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version); err != nil {
		return err
	}
	if !strings.HasPrefix(version, "12.3.3") {
		return fmt.Errorf("unexpected server %s", version)
	}
	report["server_version"] = version
	values := map[string]string{}
	for _, q := range []string{"innodb_buffer_pool_size", "innodb_flush_log_at_trx_commit", "sync_binlog", "max_connections"} {
		var name, value string
		if err := db.QueryRowContext(ctx, "SHOW VARIABLES LIKE ?", q).Scan(&name, &value); err != nil {
			return err
		}
		values[name] = value
	}
	report["server_settings"] = values
	return nil
}
func seed(db *sql.DB) error {
	if err := prepare(ctx, db); err != nil {
		return err
	}
	if os.Getenv("MODELCASE_CORRUPT_SEED") == "1" {
		_, err := db.ExecContext(ctx, "UPDATE products SET price=9999 WHERE id=1")
		return err
	}
	return nil
}
func TestMain(m *testing.M) {
	flag.Parse()
	origin = time.Now()
	mode = os.Getenv("MODELCASE_MODE")
	parallel, _ = strconv.Atoi(flag.Lookup("test.parallel").Value.String())
	observed = map[string]bool{}
	info, _ := debug.ReadBuildInfo()
	report = map[string]any{"completed": false, "mode": mode, "parallelism": parallel, "read_cases": 50, "write_cases": 20, "go": runtime.Version(), "gomaxprocs": runtime.GOMAXPROCS(0), "build_info": info, "container_ids": []string{}}
	var cancel context.CancelFunc
	ctx, cancel = context.WithTimeout(context.Background(), 220*time.Second)
	defer cancel()
	lanes = make(chan int, parallel)
	for i := 0; i < parallel; i++ {
		lanes <- i
	}
	var container *tc.MariaDBContainer
	allPools := []*sql.DB{}
	closeOwners := func() error {
		var err error
		for _, db := range allPools {
			err = errors.Join(err, db.Close())
		}
		if owner != nil {
			err = errors.Join(err, owner.Close())
		}
		if container != nil {
			cleanup, c := context.WithTimeout(context.Background(), 30*time.Second)
			defer c()
			err = errors.Join(err, container.Terminate(cleanup))
		}
		return err
	}
	setup := func() error {
		if mode == "mariamem" {
			begin := time.Now()
			prepareEnd := begin
			var err error
			owner, err = mariamemtest.New(ctx, mariamemtest.Options{MaxForks: parallel, Prepare: func(_ context.Context, db *sql.DB, _ string) error {
				event("boot", "", -1, begin)
				e := timed("schema-master-sample", "", -1, func() error { return seed(db) })
				if e != nil {
					return e
				}
				if e = settings(db); e != nil {
					return e
				}
				prepareEnd = time.Now()
				return nil
			}})
			event("capture-disconnect", "", -1, prepareEnd)
			return err
		}
		if mode != "shared" && mode != "workers" {
			return fmt.Errorf("unknown mode %q", mode)
		}
		err := timed("boot-container-ryuk", "", -1, func() error {
			var e error
			container, e = tc.Run(ctx, os.Getenv("MODELCASE_IMAGE"), tc.WithDatabase("test"), tc.WithUsername("root"), tc.WithPassword("benchmark-test-only"))
			if container != nil {
				report["container_ids"] = []string{container.GetContainerID()}
			}
			return e
		})
		if err != nil {
			return err
		}
		dsn, err := container.ConnectionString(ctx, "parseTime=true")
		if err != nil {
			return err
		}
		admin, err := open(dsn)
		if err != nil {
			return err
		}
		allPools = append(allPools, admin)
		if err = settings(admin); err != nil {
			return err
		}
		if mode == "shared" {
			shared = admin
			shared.SetMaxOpenConns(parallel)
			shared.SetMaxIdleConns(parallel)
			return timed("schema-master-sample", "", -1, func() error { return seed(shared) })
		}
		workers = make(chan *worker, parallel)
		return timed("schema-master-sample", "", -1, func() error {
			for i := 0; i < parallel; i++ {
				name := fmt.Sprintf("worker_%d", i)
				if _, err = admin.ExecContext(ctx, "CREATE DATABASE "+name+" CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"); err != nil {
					return err
				}
				c, e := mysql.ParseDSN(dsn)
				if e != nil {
					return e
				}
				c.DBName = name
				p, e := open(c.FormatDSN())
				if e != nil {
					return e
				}
				allPools = append(allPools, p)
				if e = seed(p); e != nil {
					return e
				}
				workers <- &worker{DB: p, Index: i}
			}
			return nil
		})
	}
	setupErr := setup()
	code := 1
	if setupErr == nil {
		code = m.Run()
	} else {
		report["setup_error"] = setupErr.Error()
		fmt.Fprintln(os.Stderr, setupErr)
	}
	err := timed("owner-cleanup", "", -1, closeOwners)
	if err != nil {
		report["cleanup_error"] = err.Error()
		fmt.Fprintln(os.Stderr, err)
		code = 1
	}
	report["cleanup_complete"] = err == nil
	report["completed"] = code == 0
	report["exit_code"] = code
	report["suite_ms"] = float64(time.Since(origin)) / 1e6
	report["spans"] = spans
	report["cases"] = observed
	raw, e := json.MarshalIndent(report, "", "  ")
	if e == nil {
		e = os.WriteFile(os.Getenv("MODELCASE_OUTPUT"), append(raw, '\n'), 0600)
	}
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		code = 1
	}
	os.Exit(code)
}
func execute(t *testing.T, c appCase) {
	slot := <-lanes
	t.Cleanup(func() { lanes <- slot })
	started := time.Now()
	var db *sql.DB
	var w *worker
	if mode == "mariamem" {
		var cleanupAt time.Time
		t.Cleanup(func() { event("case-cleanup", c.Name, slot, cleanupAt) })
		at := time.Now()
		db = owner.DB(t)
		event("fork", c.Name, slot, at)
		t.Cleanup(func() { cleanupAt = time.Now() })
		db.SetMaxOpenConns(1)
		db.SetMaxIdleConns(1)
	} else if mode == "workers" {
		at := time.Now()
		w = <-workers
		db = w.DB
		event("worker-acquire", c.Name, slot, at)
		t.Cleanup(func() {
			if c.Write {
				w.Dirty = true
			}
			workers <- w
		})
		if w.Dirty {
			if err := timed("reset-sample", c.Name, slot, func() error { return reset(ctx, db) }); err != nil {
				t.Fatal(err)
			}
			w.Dirty = false
		}
	} else {
		db = shared
		if c.Write && report["shared_dirty"] == true {
			if err := timed("reset-sample", c.Name, slot, func() error { return reset(ctx, db) }); err != nil {
				t.Fatal(err)
			}
		}
	}
	if err := timed("input-oracle", c.Name, slot, func() error { return pristine(ctx, db) }); err != nil {
		t.Fatal(err)
	}
	stage := "read"
	if c.Write {
		stage = "write"
	}
	if err := timed(stage, c.Name, slot, func() error { return runCase(ctx, db, c) }); err != nil {
		t.Fatal(err)
	}
	if mode == "shared" && c.Write {
		report["shared_dirty"] = true
	}
	resultMu.Lock()
	observed[c.Name] = true
	resultMu.Unlock()
	event("case-body", c.Name, slot, started)
}
func TestModelcase(t *testing.T) {
	if mode == "shared" {
		t.Run("reads", func(t *testing.T) {
			for _, c := range cases() {
				if !c.Write {
					t.Run(c.Name, func(t *testing.T) { t.Parallel(); execute(t, c) })
				}
			}
		})
		t.Run("writes", func(t *testing.T) {
			for _, c := range cases() {
				if c.Write {
					t.Run(c.Name, func(t *testing.T) { execute(t, c) })
				}
			}
		})
		return
	}
	for _, c := range cases() {
		t.Run(c.Name, func(t *testing.T) { t.Parallel(); execute(t, c) })
	}
}
