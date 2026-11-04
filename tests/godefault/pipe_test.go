//go:build integration

package godefault

import (
	"context"
	"database/sql"
	"errors"
	"net"
	"strconv"
	"sync"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/mariamemtest"
)

func pipePool(t *testing.T, db *mariamem.Database) *sql.DB {
	t.Helper()
	cfg, e := mysql.ParseDSN(db.DSN())
	if e != nil {
		t.Fatal(e)
	}
	cfg.InterpolateParams = false
	cfg.DialFunc = db.DialContext
	c, e := mysql.NewConnector(cfg)
	if e != nil {
		t.Fatal(e)
	}
	p := sql.OpenDB(c)
	t.Cleanup(func() { p.Close() })
	return p
}
func endpoint(db *mariamem.Database) string {
	i := db.ConnectionInfo()
	return net.JoinHostPort(i.Host, strconv.Itoa(i.Port))
}
func TestInProcessConnectionLifecycle(t *testing.T) {
	ctx := t.Context()
	db, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	tcp, e := sql.Open("mysql", db.DSN())
	if e != nil {
		t.Fatal(e)
	}
	defer tcp.Close()
	if _, e = tcp.Exec("CREATE TABLE pipe_seed(id INT PRIMARY KEY)"); e != nil {
		t.Fatal(e)
	}
	if _, e = tcp.Exec("INSERT INTO pipe_seed VALUES(1)"); e != nil {
		t.Fatal(e)
	}
	p := pipePool(t, db)
	st, e := p.Prepare("SELECT id + ? FROM pipe_seed")
	if e != nil {
		t.Fatal(e)
	}
	var n int
	if e = st.QueryRow(41).Scan(&n); e != nil || n != 42 {
		t.Fatal(n, e)
	}
	st.Close()
	tx, e := p.Begin()
	if e != nil {
		t.Fatal(e)
	}
	defer tx.Rollback()
	if _, e = tx.Exec("INSERT INTO pipe_seed VALUES(?)", 2); e != nil {
		t.Fatal(e)
	}
	if e = tx.Rollback(); e != nil {
		t.Fatal(e)
	}
	if e = p.QueryRow("SELECT COUNT(*) FROM pipe_seed").Scan(&n); e != nil || n != 1 {
		t.Fatal(n, e)
	}
	if _, e = p.Exec("INSERT INTO pipe_seed VALUES(?)", 3); e != nil {
		t.Fatal(e)
	}
	p.Close()
	tcp.Close()
	if e = db.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	// A returned raw pipe is already registered, so capture cannot race its handshake.
	raw, e := db.DialContext(ctx, "tcp", endpoint(db))
	if e != nil {
		t.Fatal(e)
	}
	if _, e = db.Snapshot(ctx, mariamem.SnapshotOptions{}); !errors.Is(e, mariamem.ErrBusy) {
		t.Fatal(e)
	}
	raw.Close()
	if e = db.WaitDisconnected(ctx); e != nil {
		t.Fatal(e)
	}
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
	if e != nil {
		t.Fatal(e)
	}
	defer snap.Close()
	if _, e = db.DialContext(ctx, "tcp", endpoint(db)); !errors.Is(e, mariamem.ErrClosed) {
		t.Fatal(e)
	}
	a, e := snap.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer a.Close()
	b, e := snap.Fork(ctx)
	if e != nil {
		t.Fatal(e)
	}
	defer b.Close()
	pa, pb := pipePool(t, a), pipePool(t, b)
	if _, e = pa.Exec("DELETE FROM pipe_seed"); e != nil {
		t.Fatal(e)
	}
	if e = pb.QueryRow("SELECT COUNT(*) FROM pipe_seed").Scan(&n); e != nil || n != 2 {
		t.Fatal(n, e)
	}
	if e = a.Close(); e != nil {
		t.Fatal(e)
	}
	if _, e = a.DialContext(ctx, "tcp", endpoint(a)); !errors.Is(e, mariamem.ErrClosed) {
		t.Fatal(e)
	}
	if e = pb.QueryRow("SELECT 1").Scan(&n); e != nil || n != 1 {
		t.Fatal(n, e)
	}
}
func TestInProcessCapacityAndClose(t *testing.T) {
	db, e := mariamem.Start(t.Context(), mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	p := pipePool(t, db)
	p.SetMaxOpenConns(16)
	p.SetMaxIdleConns(16)
	conns := []*sql.Conn{}
	defer func() {
		for _, c := range conns {
			c.Close()
		}
	}()
	for range 16 {
		c, e := p.Conn(t.Context())
		if e != nil {
			t.Fatal(e)
		}
		conns = append(conns, c)
	}
	for range 1000 {
		if c, e := db.DialContext(t.Context(), "tcp", endpoint(db)); c != nil || !errors.Is(e, mariamem.ErrCapacity) {
			if c != nil {
				c.Close()
			}
			t.Fatal(c, e)
		}
	}
	// TCP still exposes its existing protocol-level capacity error.
	tcp, e := sql.Open("mysql", db.DSN())
	if e != nil {
		t.Fatal(e)
	}
	defer tcp.Close()
	e = tcp.Ping()
	var me *mysql.MySQLError
	if !errors.As(e, &me) || me.Number != 1040 {
		t.Fatal(e)
	}
	for _, c := range conns {
		c.Close()
	}
	conns = nil
	p.Close()
	if e = db.WaitDisconnected(t.Context()); e != nil {
		t.Fatal(e)
	}
	ready := make(chan struct{})
	var wg sync.WaitGroup
	for range 32 {
		wg.Go(func() {
			<-ready
			c, e := db.DialContext(context.Background(), "tcp", endpoint(db))
			if e == nil {
				c.Close()
			} else if !errors.Is(e, mariamem.ErrClosed) && !errors.Is(e, mariamem.ErrCapacity) {
				t.Error(e)
			}
		})
	}
	// This unread handshake must be retired by Close, not by a client read.
	raw, e := db.DialContext(t.Context(), "tcp", endpoint(db))
	if e != nil {
		t.Fatal(e)
	}
	defer raw.Close()
	close(ready)
	if e = db.Close(); e != nil {
		t.Fatal(e)
	}
	wg.Wait()
	if _, e = db.DialContext(t.Context(), "tcp", endpoint(db)); !errors.Is(e, mariamem.ErrClosed) {
		t.Fatal(e)
	}
}
func TestInProcessCancellation(t *testing.T) {
	db, e := mariamem.Start(t.Context(), mariamem.Options{})
	if e != nil {
		t.Fatal(e)
	}
	defer db.Close()
	p := pipePool(t, db)
	if e = p.Ping(); e != nil {
		t.Fatal(e)
	}
	ctx, cancel := context.WithTimeout(t.Context(), 50*time.Millisecond)
	defer cancel()
	var n int
	e = p.QueryRowContext(ctx, "SELECT SLEEP(1)").Scan(&n)
	if !errors.Is(e, context.DeadlineExceeded) {
		t.Fatal(e)
	}
	deadline := time.Now().Add(3 * time.Second)
	for db.Err() == nil && time.Now().Before(deadline) {
		time.Sleep(time.Millisecond)
	}
	if _, e = db.DialContext(t.Context(), "tcp", endpoint(db)); !errors.Is(e, mariamem.ErrUnusable) {
		t.Fatal(e)
	}
}
func TestInProcessFixture(t *testing.T) {
	f, e := mariamemtest.New(t.Context(), mariamemtest.Options{InProcess: true, Prepare: func(ctx context.Context, p *sql.DB, _ string) error {
		_, e := p.ExecContext(ctx, "CREATE TABLE owned_pipe(id INT PRIMARY KEY)")
		if e != nil {
			return e
		}
		_, e = p.ExecContext(ctx, "INSERT INTO owned_pipe VALUES(1)")
		return e
	}})
	if e != nil {
		t.Fatal(e)
	}
	defer f.Close()
	t.Run("mutate", func(t *testing.T) {
		if _, e := f.DB(t).Exec("DELETE FROM owned_pipe"); e != nil {
			t.Fatal(e)
		}
	})
	t.Run("isolated", func(t *testing.T) {
		var n int
		if e := f.DB(t).QueryRow("SELECT COUNT(*) FROM owned_pipe").Scan(&n); e != nil || n != 1 {
			t.Fatal(n, e)
		}
	})
}
