package mariamemtest

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

// These are real embedded DB/Live/physical sessions with a controlled app hook,
// not a claim about arbitrary application pools or delayed background jobs.
type httpPhysicalApp struct {
	pool            *sql.DB
	release         bool
	quiesces, stops int
}

func (a *httpPhysicalApp) BaseURL() string  { return "http://127.0.0.1:1" }
func (a *httpPhysicalApp) Identity() string { return "controlled-pool-owner" }
func (a *httpPhysicalApp) QuiesceAndRetire(ctx context.Context) error {
	a.quiesces++
	if err := ctx.Err(); err != nil {
		return err
	}
	if a.release && a.pool != nil {
		err := a.pool.Close()
		a.pool = nil
		return err
	}
	return nil // deliberately lying nil in the negative control
}
func (a *httpPhysicalApp) StopReap(ctx context.Context) error {
	a.stops++
	if a.pool != nil {
		err := a.pool.Close()
		a.pool = nil
		return err
	}
	return nil
}
func httpPhysicalPool(info mariamem.ConnectionInfo) (*sql.DB, error) {
	cfg := mysql.NewConfig()
	cfg.User = info.User
	cfg.Passwd = info.Password
	cfg.Net = "tcp"
	cfg.Addr = net.JoinHostPort(info.Host, strconv.Itoa(info.Port))
	cfg.DBName = info.Database
	pool, err := sql.Open("mysql", cfg.FormatDSN())
	if err != nil {
		return nil, err
	}
	pool.SetMaxOpenConns(1)
	pool.SetMaxIdleConns(1)
	return pool, nil
}
func httpPhysicalFixture(t *testing.T, release bool) (*HTTPFixture, *httpPhysicalApp) {
	t.Helper()
	if os.Getenv("E2E_OWNED_RUNTIME") != "1" {
		t.Skip("set E2E_OWNED_RUNTIME=1 for physical hook controls")
	}
	app := &httpPhysicalApp{release: release}
	config := HTTPConfig{SoleWorkSource: true, DrainTimeout: 100 * time.Millisecond,
		Prepare: func(ctx context.Context, source *mariamem.Database) error {
			pool, err := httpPhysicalPool(source.ConnectionInfo())
			if err != nil {
				return err
			}
			defer pool.Close()
			for _, stmt := range []string{"CREATE TABLE e2e_guard(v INT PRIMARY KEY)", "INSERT INTO e2e_guard VALUES(1)"} {
				if _, err = pool.ExecContext(ctx, stmt); err != nil {
					return err
				}
			}
			return nil
		},
		StartReady: func(ctx context.Context, target mariamem.ConnectionInfo, register func(HTTPApp) error) (HTTPApp, error) {
			pool, err := httpPhysicalPool(target)
			if err != nil {
				return nil, err
			}
			app.pool = pool
			if err = register(app); err != nil {
				return nil, errors.Join(err, pool.Close())
			}
			if err = pool.PingContext(ctx); err != nil {
				return nil, err
			}
			return app, nil
		},
	}
	f, err := newHTTP(config, startHTTP)
	if f != nil {
		t.Cleanup(func() {
			if err := f.close(); err != nil {
				t.Error(err)
			}
			if app.stops != 1 {
				t.Errorf("app stop count %d", app.stops)
			}
		})
	}
	if err != nil {
		t.Fatal(err)
	}
	if f.owners.live.Status().ActiveConnections != 1 {
		t.Fatalf("idle physical session missing: %+v", f.owners.live.Status())
	}
	return f, app
}
func TestHTTPPhysicalIdlePoolCannotBypassDrain(t *testing.T) {
	f, app := httpPhysicalFixture(t, false)
	before := f.owners.live.Status()
	c, err := f.reserve()
	if err != nil {
		t.Fatal(err)
	}
	err = c.setup(context.Background())
	var diagnostic *HTTPEntryError
	if !errors.Is(err, mariamem.ErrBusy) || !errors.As(err, &diagnostic) || diagnostic.Stage != "reset" {
		t.Fatalf("idle physical connection not rejected at Reset: %v", err)
	}
	if err = c.finish(); err != nil {
		t.Fatal(err)
	}
	after := f.owners.live.Status()
	if after.State != "ready" || after.Generation != before.Generation || after.ActiveConnections != 1 {
		t.Fatalf("busy Reset changed backend: before=%+v after=%+v", before, after)
	}
	if _, err = f.reserve(); err == nil {
		t.Fatal("body could be admitted after failed Reset")
	}
	if app.quiesces != 1 {
		t.Fatal("failed setup implicitly retried hook")
	}
}
func TestHTTPPhysicalRetirementRestoresSeed(t *testing.T) {
	f, app := httpPhysicalFixture(t, true)
	// First case must also quiesce: the app starts with an idle physical session.
	// Its correct retirement permits Reset; case-owned pools close before next case.
	for _, name := range []string{"first", "next"} {
		t.Run(name, func(t *testing.T) {
			c := f.Case(t)
			pool, err := httpPhysicalPool(f.target)
			if err != nil {
				t.Fatal(err)
			}
			if err = c.Register(pool); err != nil {
				_ = pool.Close()
				t.Fatal(err)
			}
			var count int
			if err = pool.QueryRowContext(t.Context(), "SELECT COUNT(*) FROM e2e_guard").Scan(&count); err != nil || count != 1 {
				t.Fatalf("seed not restored: count=%d error=%v", count, err)
			}
			if _, err = pool.ExecContext(t.Context(), "INSERT INTO e2e_guard VALUES(2)"); err != nil {
				t.Fatal(err)
			}
		})
	}
	if app.quiesces != 2 || f.owners.live.Status().Generation != 2 {
		t.Fatal("missing per-case quiescence/reset")
	}
}

func TestHTTPPhysicalBusyPublicChild(t *testing.T) {
	if os.Getenv("E2E_BUSY_PUBLIC_CHILD") != "1" {
		return
	}
	f, app := httpPhysicalFixture(t, false)
	for _, name := range []string{"blocked", "later"} {
		t.Run(name, func(t *testing.T) {
			f.Case(t)
			fmt.Println("BODY_ADMITTED")
		})
	}
	if app.quiesces != 1 {
		t.Fatal("hook retried")
	}
	if err := f.close(); err != nil {
		t.Fatal(err)
	}
	if app.stops != 1 {
		t.Fatal("app cleanup missing")
	}
	fmt.Println("BUSY_PUBLIC_NO_BODY_AND_CLOSE_OK")
}
func TestHTTPPhysicalPublicAdmission(t *testing.T) {
	if os.Getenv("E2E_OWNED_RUNTIME") != "1" {
		t.Skip("set E2E_OWNED_RUNTIME=1")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestHTTPPhysicalBusyPublicChild$", "-test.v")
	cmd.Env = append(os.Environ(), "E2E_BUSY_PUBLIC_CHILD=1")
	output, err := cmd.CombinedOutput()
	text := string(output)
	if err == nil || ctx.Err() != nil {
		t.Fatalf("missing deliberate setup failures: %v %s", err, text)
	}
	if strings.Contains(text, "BODY_ADMITTED") || strings.Contains(text, "DATA RACE") || !strings.Contains(text, "BUSY_PUBLIC_NO_BODY_AND_CLOSE_OK") {
		t.Fatal(text)
	}
	if strings.Count(text, "--- FAIL: TestHTTPPhysicalBusyPublicChild/") != 2 || strings.Count(text, "--- FAIL: TestHTTPPhysicalBusyPublicChild (") != 1 {
		t.Fatal("unexpected failure census", text)
	}
	if !strings.Contains(text, "E2E reset; admission=stopped") || !strings.Contains(text, "E2E admission; admission=stopped") {
		t.Fatal("missing setup/latch diagnostic", text)
	}
	t.Log("public Case rejected initial busy setup and later admission; confirmed app close")
}
