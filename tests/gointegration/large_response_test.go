//go:build integration && (darwin || linux)

package gointegration_test

import (
	"bytes"
	"context"
	"database/sql"
	"fmt"
	"sync"
	"syscall"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// One operation is 96 checked 256 KiB SQL results on eight live sessions.
// Use -benchtime=1x to compare independent processes with the same workload.
func BenchmarkLargeResponseBatch(b *testing.B) {
	const clients = 8
	ctx := b.Context()
	db, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		b.Fatal(err)
	}
	b.Cleanup(func() {
		if err := db.Close(); err != nil {
			b.Error(err)
		}
	})
	cfg, err := mysql.ParseDSN(db.DSN())
	if err != nil {
		b.Fatal(err)
	}
	cfg.ClientFoundRows = true
	cfg.DialFunc = db.DialContext
	connector, err := mysql.NewConnector(cfg)
	if err != nil {
		b.Fatal(err)
	}
	pool := sql.OpenDB(connector)
	b.Cleanup(func() {
		if err := pool.Close(); err != nil {
			b.Error(err)
		}
	})
	var sessions [clients]*sql.Conn
	for i := range sessions {
		conn, err := pool.Conn(ctx)
		if err != nil {
			b.Fatal(err)
		}
		sessions[i] = conn
		b.Cleanup(func() {
			if err := conn.Close(); err != nil {
				b.Error(err)
			}
		})
	}
	cpuTime := func() int64 {
		var usage syscall.Rusage
		if err := syscall.Getrusage(syscall.RUSAGE_SELF, &usage); err != nil {
			b.Fatal(err)
		}
		return usage.Utime.Nano() + usage.Stime.Nano()
	}
	var ready, done sync.WaitGroup
	ready.Add(clients)
	done.Add(clients)
	start := make(chan struct{})
	for i, conn := range sessions {
		go func() {
			defer done.Done()
			tag := fmt.Sprintf("%02d", i)
			payload := bytes.Repeat([]byte(tag), 131072)
			ready.Done()
			<-start
			for range b.N {
				if err := checkLargeResponses(ctx, conn, i, tag, payload); err != nil {
					b.Error(err)
					return
				}
			}
		}()
	}
	ready.Wait()
	before := cpuTime()
	b.ResetTimer()
	close(start)
	done.Wait()
	b.StopTimer()
	b.ReportMetric(float64(cpuTime()-before)/float64(b.N), "cpu-ns/op")
}

func checkLargeResponses(ctx context.Context, conn *sql.Conn, session int, tag string, payload []byte) error {
	for j := range 12 {
		prefix := fmt.Sprintf("%d/%d/", session, j)
		var got []byte
		if err := conn.QueryRowContext(ctx, "SELECT CONCAT(?, REPEAT(?,131072))", prefix, tag).Scan(&got); err != nil {
			return err
		}
		if len(got) != len(prefix)+len(payload) || string(got[:len(prefix)]) != prefix || !bytes.Equal(got[len(prefix):], payload) {
			return fmt.Errorf("wrong response for %s (%d bytes)", prefix, len(got))
		}
	}
	return nil
}
