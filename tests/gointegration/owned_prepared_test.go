//go:build integration

package gointegration_test

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"os"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

func ownedFDs(t *testing.T) int {
	t.Helper()
	if runtime.GOOS == "linux" {
		entries, e := os.ReadDir("/proc/self/fd")
		if e != nil {
			t.Fatal(e)
		}
		return len(entries)
	}
	var l syscall.Rlimit
	if e := syscall.Getrlimit(syscall.RLIMIT_NOFILE, &l); e != nil {
		t.Fatal(e)
	}
	n := 0
	for fd := uint64(0); fd < l.Cur; fd++ {
		if _, _, e := syscall.Syscall(syscall.SYS_FCNTL, uintptr(fd), syscall.F_GETFD, 0); e == 0 {
			n++
		}
	}
	return n
}

// SQL state checks deliberately include values and schema, rather than only
// successful startup or a row count. Every worker starts from the same template.
func ownedWork(ctx context.Context, s *mariamem.Snapshot, kind int) (err error) {
	db, err := s.Fork(ctx)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, db.Close()) }()
	p, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	p.SetMaxOpenConns(1)
	defer p.Close()
	var n, sum, bytes int
	if err = p.QueryRowContext(ctx, "SELECT COUNT(*),SUM(id),SUM(OCTET_LENGTH(payload)) FROM owned_items").Scan(&n, &sum, &bytes); err != nil {
		return err
	}
	if n != 3 || sum != 6 || bytes != 3072 {
		return fmt.Errorf("initial data changed: %d/%d/%d", n, sum, bytes)
	}
	var label string
	if err = p.QueryRowContext(ctx, "SELECT label FROM owned_items WHERE id=1").Scan(&label); err != nil || label != "seed" {
		return fmt.Errorf("initial value: %s %v", label, err)
	}
	if err = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='owned_items'").Scan(&n); err != nil || n != 3 {
		return fmt.Errorf("initial schema: %d %v", n, err)
	}
	exec := func(q string, args ...any) error { _, e := p.ExecContext(ctx, q, args...); return e }
	switch kind % 3 {
	case 0:
		// 8 MiB expansion forces private mapped storage to grow into child memory.
		data := strings.Repeat("x", 4096)
		for first := 100; first < 2148; first += 128 {
			values := []string{}
			args := []any{}
			for id := first; id < first+128; id++ {
				values = append(values, "(?, 'child', ?)")
				args = append(args, id, data)
			}
			if err = exec("INSERT INTO owned_items VALUES "+strings.Join(values, ","), args...); err != nil {
				return err
			}
		}
		if err = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM owned_items").Scan(&n); err != nil || n != 2051 {
			return fmt.Errorf("growth: %d %v", n, err)
		}
	case 1:
		tx, e := p.BeginTx(ctx, nil)
		if e != nil {
			return e
		}
		if _, e = tx.ExecContext(ctx, "UPDATE owned_items SET label='rollback' WHERE id=1"); e != nil {
			tx.Rollback()
			return e
		}
		if _, e = tx.ExecContext(ctx, "DELETE FROM owned_items WHERE id=2"); e != nil {
			tx.Rollback()
			return e
		}
		if e = tx.Rollback(); e != nil {
			return e
		}
		if e = p.QueryRowContext(ctx, "SELECT label FROM owned_items WHERE id=1").Scan(&label); e != nil || label != "seed" {
			return fmt.Errorf("rollback: %s %v", label, e)
		}
		tx, e = p.BeginTx(ctx, nil)
		if e != nil {
			return e
		}
		if _, e = tx.ExecContext(ctx, "UPDATE owned_items SET label='commit' WHERE id=1"); e != nil {
			tx.Rollback()
			return e
		}
		if _, e = tx.ExecContext(ctx, "DELETE FROM owned_items WHERE id=2"); e != nil {
			tx.Rollback()
			return e
		}
		if e = tx.Commit(); e != nil {
			return e
		}
		if e = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM owned_items").Scan(&n); e != nil || n != 2 {
			return fmt.Errorf("commit: %d %v", n, e)
		}
	case 2:
		for _, q := range []string{"ALTER TABLE owned_items ADD COLUMN child INT DEFAULT 7", "CREATE TABLE child_only(id INT) ENGINE=InnoDB", "DROP TABLE child_only"} {
			if err = exec(q); err != nil {
				return err
			}
		}
		if err = p.QueryRowContext(ctx, "SELECT child FROM owned_items WHERE id=1").Scan(&n); err != nil || n != 7 {
			return fmt.Errorf("schema mutation: %d %v", n, err)
		}
	}
	if err = p.Close(); err != nil {
		return err
	}
	return db.WaitDisconnected(ctx)
}

func TestOwnedManyOrderParallelAndClose(t *testing.T) {
	if os.Getenv("MARIAMEM_TEST_DEFAULT") != "1" {
		t.Skip("real generated-Go gate")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	warm, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	if e = warm.Close(); e != nil {
		t.Fatal(e)
	}
	beforeFD, beforeG := ownedFDs(t), runtime.NumGoroutine()
	source, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer source.Close()
	p, e := sql.Open("mysql", source.DSN())
	if e != nil {
		t.Fatal(e)
	}
	for _, q := range []string{"CREATE TABLE owned_items(id INT PRIMARY KEY,label VARCHAR(32),payload LONGBLOB) ENGINE=InnoDB", "INSERT INTO owned_items VALUES(1,'seed',REPEAT('a',1024)),(2,'seed',REPEAT('b',1024)),(3,'seed',REPEAT('c',1024))"} {
		if _, e = p.ExecContext(ctx, q); e != nil {
			t.Fatal(e)
		}
	}
	p.Close()
	if e = source.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	s, e := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if e != nil {
		t.Fatal(e)
	}
	defer s.Close()
	// Three full permutations, then ten further generations. Each workload
	// includes a fresh logical-state assertion before it modifies its child.
	for _, kind := range []int{0, 1, 2, 2, 0, 1, 1, 2, 0, 0, 1, 2, 0, 1, 2, 0, 1, 2, 0} {
		if e = ownedWork(ctx, s, kind); e != nil {
			t.Fatal(e)
		}
	}
	for round := 0; round < 4; round++ {
		var wg sync.WaitGroup
		errs := make(chan error, 4)
		for worker := 0; worker < 4; worker++ {
			wg.Go(func() { errs <- ownedWork(ctx, s, worker) })
		}
		wg.Wait()
		close(errs)
		for e := range errs {
			if e != nil {
				t.Fatal(e)
			}
		}
	}
	child, e := s.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	if e = s.Close(); e != nil {
		t.Fatal(e)
	}
	if e = s.Close(); e != nil {
		t.Fatal(e)
	}
	// Successfully started children retain their own mappings after owner Close.
	p, e = sql.Open("mysql", child.DSN())
	if e != nil {
		t.Fatal(e)
	}
	var n int
	if e = p.QueryRowContext(ctx, "SELECT COUNT(*) FROM owned_items").Scan(&n); e != nil || n != 3 {
		t.Fatalf("after owner Close: %d %v", n, e)
	}
	p.Close()
	if e = child.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	if e = child.Close(); e != nil {
		t.Fatal(e)
	}
	source.Close()
	runtime.GC()
	time.Sleep(100 * time.Millisecond)
	afterFD, afterG := ownedFDs(t), runtime.NumGoroutine()
	t.Logf("35 mutating children + live-after-Close: fd %d -> %d; goroutines %d -> %d", beforeFD, afterFD, beforeG, afterG)
	if afterFD > beforeFD || afterG > beforeG {
		t.Fatalf("lifecycle accumulation: FD %d/%d goroutines %d/%d", beforeFD, afterFD, beforeG, afterG)
	}
}

func TestOwnedForkCloseRace(t *testing.T) {
	if os.Getenv("MARIAMEM_TEST_DEFAULT") != "1" {
		t.Skip("real generated-Go gate")
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	for round := 0; round < 6; round++ {
		source, e := mariamem.Start(ctx, mariamem.Options{})
		if e != nil {
			t.Fatal(e)
		}
		s, e := source.Snapshot(ctx, mariamem.SnapshotOptions{})
		if e != nil {
			t.Fatal(e)
		}
		gate := make(chan struct{})
		errs := make(chan error, 4)
		var wg sync.WaitGroup
		for worker := 0; worker < 3; worker++ {
			wg.Go(func() {
				<-gate
				child, e := s.Fork(ctx)
				if errors.Is(e, mariamem.ErrClosed) {
					errs <- nil
					return
				}
				if e != nil {
					errs <- e
					return
				}
				p, e := sql.Open("mysql", child.DSN())
				if e == nil {
					var one int
					e = p.QueryRowContext(ctx, "SELECT 1").Scan(&one)
					p.Close()
					if e == nil && one != 1 {
						e = errors.New("child SQL changed")
					}
				}
				errs <- errors.Join(e, child.Close())
			})
		}
		wg.Go(func() { <-gate; errs <- s.Close() })
		close(gate)
		wg.Wait()
		close(errs)
		for e := range errs {
			if e != nil {
				t.Fatal(e)
			}
		}
		source.Close()
		s.Close()
	}
}

func TestOwnedModifiedChildCreatesNewBaseline(t *testing.T) {
	if os.Getenv("MARIAMEM_TEST_DEFAULT") != "1" {
		t.Skip("real generated-Go gate")
	}
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer source.Close()
	prepare, err := sql.Open("mysql", source.DSN())
	if err != nil {
		t.Fatal(err)
	}
	for _, query := range []string{"CREATE TABLE lineage(id INT PRIMARY KEY) ENGINE=InnoDB", "INSERT INTO lineage VALUES(1)"} {
		if _, err = prepare.ExecContext(ctx, query); err != nil {
			t.Fatal(err)
		}
	}
	prepare.Close()
	if err = source.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	a, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	defer a.Close()
	b, err := a.Fork(ctx)
	if err != nil {
		t.Fatal(err)
	}
	defer b.Close()
	mutate, err := sql.Open("mysql", b.DSN())
	if err != nil {
		t.Fatal(err)
	}
	if _, err = mutate.ExecContext(ctx, "INSERT INTO lineage VALUES(2)"); err != nil {
		t.Fatal(err)
	}
	mutate.Close()
	if err = b.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	c, err := b.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	defer c.Close()
	if !b.Closed() {
		t.Fatal("snapshot did not consume child")
	}
	for _, item := range []struct {
		baseline *mariamem.Snapshot
		want     int
	}{{a, 1}, {c, 2}, {a, 1}} {
		child, err := item.baseline.Fork(ctx)
		if err != nil {
			t.Fatal(err)
		}
		pool, err := sql.Open("mysql", child.DSN())
		if err != nil {
			child.Close()
			t.Fatal(err)
		}
		var count int
		err = pool.QueryRowContext(ctx, "SELECT COUNT(*) FROM lineage").Scan(&count)
		pool.Close()
		closeErr := child.Close()
		if err != nil || closeErr != nil || count != item.want {
			t.Fatalf("lineage count=%d want=%d errors=%v/%v", count, item.want, err, closeErr)
		}
	}
}
