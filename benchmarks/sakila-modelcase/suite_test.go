package sakila

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

var backend = flag.String("sakila.backend", "", "mariamem, testcontainers, mysql, or docker")
var image = flag.String("sakila.image", "", "pinned MySQL image for managed containers")
var metricsPath = flag.String("sakila.metrics", "", "path for a JSON timing report")
var sourceCommit string

type phase struct {
	Name string  `json:"name"`
	Case string  `json:"case,omitempty"`
	From float64 `json:"from_ms"`
	To   float64 `json:"to_ms"`
}

type suiteMetrics struct {
	Backend      string            `json:"backend"`
	SourceCommit string            `json:"source_commit"`
	Version      string            `json:"version"`
	Image        string            `json:"image,omitempty"`
	Parallel     int               `json:"parallel"`
	Reads        int               `json:"reads"`
	Writes       int               `json:"writes"`
	Settings     map[string]string `json:"settings"`
	TotalMS      float64           `json:"total_ms"`
	Phases       []phase           `json:"phases"`
}

type suite struct {
	reader *sql.DB
	snap   *mariamem.Snapshot
	start  time.Time
	report suiteMetrics
	mu     sync.Mutex
}

func ms(d time.Duration) float64 {
	return float64(d) / float64(time.Millisecond)
}

func (s *suite) record(phaseName, name string, f func() error) error {
	start := time.Now()
	err := f()
	end := time.Now()
	s.mu.Lock()
	s.report.Phases = append(s.report.Phases, phase{phaseName, name, ms(start.Sub(s.start)), ms(end.Sub(s.start))})
	s.mu.Unlock()
	return err
}

func TestSakila(t *testing.T) {
	if *backend == "" {
		t.Skip("select a benchmark backend with -sakila.backend")
	}
	if (*backend == "testcontainers" || *backend == "docker") && *image == "" {
		t.Fatal("managed container requires -sakila.image")
	}
	ctx, cancel := context.WithTimeout(t.Context(), 3*time.Minute)
	defer cancel()
	s := suite{start: time.Now(), report: suiteMetrics{Backend: *backend, SourceCommit: sourceCommit, Image: *image}}
	if _, err := fmt.Sscan(flag.Lookup("test.parallel").Value.String(), &s.report.Parallel); err != nil {
		t.Fatal(err)
	}
	var stop func() error
	var err error
	if *backend == "mariamem" {
		stop, err = s.embedded(ctx)
	} else {
		stop, err = s.shared(ctx)
	}
	if stop != nil {
		defer func() {
			if err := s.record("cleanup", "", stop); err != nil {
				t.Error(err)
			}
			if t.Failed() {
				return
			}
			s.report.TotalMS = ms(time.Since(s.start))
			if *metricsPath == "" {
				return
			}
			data, err := json.Marshal(s.report)
			if err == nil {
				err = os.WriteFile(*metricsPath, append(data, '\n'), 0644)
			}
			if err != nil {
				t.Error(err)
			}
		}()
	}
	if err != nil {
		t.Fatal(err)
	}
	if err := baseline(ctx, s.reader); err != nil {
		t.Fatal(err)
	}
	reads := makeCases(readScenarios, 10, false)
	writes := makeCases(writeScenarios, 10, true)
	if s.snap != nil {
		t.Run("parallel", func(t *testing.T) {
			interleaved := make([]suiteCase, 0, len(reads)+len(writes))
			nextWrite := 0
			for index, read := range reads {
				interleaved = append(interleaved, read)
				for nextWrite < len(writes) && index == nextWrite*len(reads)/len(writes) {
					interleaved = append(interleaved, writes[nextWrite])
					nextWrite++
				}
			}
			s.runCases(t, ctx, interleaved, true)
		})
		if err := baseline(ctx, s.reader); err != nil {
			t.Errorf("shared reader after writers: %v", err)
		}
	} else {
		t.Run("read", func(t *testing.T) { s.runCases(t, ctx, reads, true) })
		t.Run("write", func(t *testing.T) { s.runCases(t, ctx, writes, false) })
	}
	if s.report.Reads != 50 || s.report.Writes != 50 {
		t.Errorf("completed %d reads and %d writes, want 50 and 50", s.report.Reads, s.report.Writes)
	}
}

type suiteCase struct {
	scenario scenario
	id       int
	write    bool
}

func makeCases(scenarios []scenario, count int, write bool) []suiteCase {
	cases := make([]suiteCase, 0, len(scenarios)*count)
	for _, scenario := range scenarios {
		for id := 1; id <= count; id++ {
			cases = append(cases, suiteCase{scenario, id, write})
		}
	}
	return cases
}

func (s *suite) runCases(t *testing.T, ctx context.Context, cases []suiteCase, parallel bool) {
	for _, item := range cases {
		name := fmt.Sprintf("%s/%02d", item.scenario.name, item.id)
		t.Run(name, func(t *testing.T) {
			if parallel {
				t.Parallel()
			}
			db := s.reader
			if item.write {
				if s.snap == nil {
					if err := s.record("reset", name, func() error { return reset(ctx, db) }); err != nil {
						t.Fatal(err)
					}
				} else {
					var child *mariamem.Database
					err := s.record("fork", name, func() (err error) {
						child, err = s.snap.Fork(ctx)
						return err
					})
					if err != nil {
						t.Fatal(err)
					}
					defer func() {
						if err := s.record("child_close", name, child.Close); err != nil {
							t.Error(err)
						}
					}()
					db, err = openDB(child.DSN())
					if err != nil {
						t.Fatal(err)
					}
					defer db.Close()
				}
				if err := baseline(ctx, db); err != nil {
					t.Fatal(err)
				}
			}
			stage := "read"
			if item.write {
				stage = "write"
			}
			if err := s.record(stage, name, func() error { return item.scenario.run(ctx, db, item.id) }); err != nil {
				t.Fatal(err)
			}
			s.mu.Lock()
			if item.write {
				s.report.Writes++
			} else {
				s.report.Reads++
			}
			s.mu.Unlock()
		})
	}
}

func (s *suite) embedded(ctx context.Context) (stop func() error, err error) {
	var parent, reader *mariamem.Database
	stop = func() error {
		var cleanup error
		if s.reader != nil {
			cleanup = s.reader.Close()
		}
		if reader != nil {
			cleanup = errors.Join(cleanup, reader.Close())
		}
		if s.snap != nil {
			cleanup = errors.Join(cleanup, s.snap.Close())
		}
		if parent != nil {
			cleanup = errors.Join(cleanup, parent.Close())
		}
		return cleanup
	}
	var pool *sql.DB
	if err := s.record("ready", "", func() (err error) {
		parent, err = mariamem.Start(ctx, mariamem.Options{})
		if err != nil {
			return err
		}
		pool, err = openDB(parent.DSN())
		if err != nil {
			return err
		}
		s.report.Version, err = waitReady(ctx, pool)
		return err
	}); err != nil {
		if pool != nil {
			pool.Close()
		}
		return stop, err
	}
	defer pool.Close()
	s.report.Settings, err = config(pool, ctx)
	if err != nil {
		return stop, err
	}
	if err := s.record("fixture", "", func() error { return fixture(ctx, pool) }); err != nil {
		return stop, err
	}
	if err := s.record("snapshot", "", func() error {
		if err := pool.Close(); err != nil {
			return err
		}
		if err := parent.WaitDisconnected(ctx); err != nil {
			return err
		}
		var err error
		s.snap, err = parent.Snapshot(ctx, mariamem.SnapshotOptions{})
		return err
	}); err != nil {
		return stop, err
	}
	err = s.record("fork", "reader", func() error {
		var err error
		reader, err = s.snap.Fork(ctx)
		if err != nil {
			return err
		}
		s.reader, err = openDB(reader.DSN())
		return err
	})
	return stop, err
}

func (s *suite) shared(ctx context.Context) (stop func() error, err error) {
	var admin *sql.DB
	var dsn string
	var serverStop, drop func() error
	stop = func() error {
		var cleanup error
		if s.reader != nil {
			cleanup = s.reader.Close()
		}
		if drop != nil {
			cleanup = errors.Join(cleanup, drop())
		}
		if admin != nil {
			cleanup = errors.Join(cleanup, admin.Close())
		}
		if serverStop != nil {
			cleanup = errors.Join(cleanup, serverStop())
		}
		return cleanup
	}
	if err := s.record("ready", "", func() (err error) {
		startup, cancel := context.WithTimeout(ctx, 90*time.Second)
		defer cancel()
		dsn, serverStop, err = sharedServer(startup, *backend, *image)
		if err != nil {
			return err
		}
		admin, err = openDB(dsn)
		if err != nil {
			return err
		}
		s.report.Version, err = waitReady(startup, admin)
		return err
	}); err != nil {
		return stop, err
	}
	s.report.Settings, err = config(admin, ctx)
	if err != nil {
		return stop, err
	}
	err = s.record("fixture", "", func() error {
		var err error
		s.reader, drop, err = ownedSchema(ctx, admin, dsn)
		if err != nil {
			return err
		}
		return fixture(ctx, s.reader)
	})
	return stop, err
}
