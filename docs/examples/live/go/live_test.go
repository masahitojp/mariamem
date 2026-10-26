// Package liveexample shows an application reused across sequential HTTP tests.
package liveexample

import (
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestOrders(t *testing.T) {
	if os.Getenv("MARIAMEM_RUN_LIVE_EXAMPLES") != "1" {
		t.Skip("set MARIAMEM_RUN_LIVE_EXAMPLES=1 for this runnable example")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	// Cancel only after application and database owners have closed.
	t.Cleanup(cancel)
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := source.Close(); err != nil {
			t.Error(err)
		}
	})

	root, err := filepath.Abs("../../../..")
	if err != nil {
		t.Fatal(err)
	}
	pool, err := sql.Open("mysql", source.DSN())
	if err != nil {
		t.Fatal(err)
	}
	// Register early so setup failures also release the preparation pool.
	t.Cleanup(func() {
		if err := pool.Close(); err != nil {
			t.Error(err)
		}
	})
	conn, err := pool.Conn(ctx)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	for _, statement := range []string{
		"CREATE DATABASE e2e_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci",
		"USE e2e_app",
	} {
		if _, err = conn.ExecContext(ctx, statement); err != nil {
			t.Fatal(err)
		}
	}
	schema, err := os.ReadFile(filepath.Join(root, "tests/e2e_native_control/goapp/schema.sql"))
	if err != nil {
		t.Fatal(err)
	}
	// Only this fixed two-statement application fixture; not a dump reader.
	for _, statement := range strings.Split(string(schema), ";") {
		if strings.TrimSpace(statement) != "" {
			if _, err = conn.ExecContext(ctx, statement); err != nil {
				t.Fatal(err)
			}
		}
	}
	if err = conn.Close(); err != nil {
		t.Fatal(err)
	}
	if err = pool.Close(); err != nil {
		t.Fatal(err)
	}
	if err = source.WaitDisconnected(ctx); err != nil {
		t.Fatal(err)
	}
	prepared, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if err := prepared.Close(); err != nil {
			t.Error(err)
		}
	})
	live, err := prepared.Live(ctx)
	if live != nil {
		t.Cleanup(func() {
			if err := live.Close(); err != nil {
				t.Error(err)
			}
		})
	}
	if err != nil {
		t.Fatal(err)
	}
	endpoint := live.ConnectionInfo()
	config, err := mysql.ParseDSN(live.DSN())
	if err != nil {
		t.Fatal(err)
	}
	config.DBName = "e2e_app"
	binary, err := filepath.Abs(os.Getenv("E2E_GO_APP"))
	if err != nil || os.Getenv("E2E_GO_APP") == "" {
		t.Fatal("set E2E_GO_APP to the built orders application")
	}
	app := exec.CommandContext(ctx, binary)
	app.Env = append(os.Environ(), "E2E_MYSQL_DSN="+config.FormatDSN())
	app.Stderr = os.Stderr
	stdout, err := app.StdoutPipe()
	if err != nil {
		t.Fatal(err)
	}
	if err = app.Start(); err != nil {
		t.Fatal(err)
	}
	// LIFO: stop app, close Live, close Snapshot, then close source.
	t.Cleanup(func() {
		if err := app.Process.Signal(os.Interrupt); err != nil {
			t.Error(err)
		}
		done := make(chan error, 1)
		go func() { done <- app.Wait() }()
		select {
		case err := <-done:
			if err != nil {
				t.Error(err)
			}
		case <-time.After(5 * time.Second):
			_ = app.Process.Kill()
			<-done
			t.Error("app needed forced shutdown")
		}
	})
	var address struct {
		Address string `json:"address"`
		PID     int    `json:"pid"`
	}
	ready := make(chan error, 1)
	go func() { ready <- json.NewDecoder(stdout).Decode(&address) }()
	select {
	case err = <-ready:
		if err != nil {
			t.Fatal(err)
		}
	case <-time.After(30 * time.Second):
		t.Fatal("application startup timeout")
	}
	if address.PID != app.Process.Pid {
		t.Fatal("unexpected application PID")
	}
	client := &http.Client{Timeout: 5 * time.Second}
	defer client.CloseIdleConnections()
	baseURL := "http://" + address.Address
	get := func(t *testing.T, path string) string {
		t.Helper()
		response, err := client.Get(baseURL + path)
		if err != nil {
			t.Fatal(err)
		}
		defer response.Body.Close()
		body, err := io.ReadAll(response.Body)
		if err != nil {
			t.Fatal(err)
		}
		if response.StatusCode != http.StatusOK {
			t.Fatalf("HTTP %d: %s", response.StatusCode, body)
		}
		return string(body)
	}
	for _, name := range []string{"first", "second"} {
		t.Run(name, func(t *testing.T) {
			// No t.Parallel: previous requests have finished. The sample app's
			// MaxIdleConns(0) releases physical SQL sessions after requests.
			if err := live.Reset(ctx, mariamem.ResetOptions{}); err != nil {
				t.Fatal(err)
			}
			if live.ConnectionInfo() != endpoint {
				t.Fatal("DB endpoint changed")
			}
			var health struct {
				PID int `json:"pid"`
			}
			if err := json.Unmarshal([]byte(get(t, "/healthz")), &health); err != nil {
				t.Fatal(err)
			}
			if health.PID != address.PID {
				t.Fatal("application restarted")
			}
			before := get(t, "/orders")
			if !strings.Contains(before, "SEED:2:ready") || strings.Contains(before, "NEW:3:ready") {
				t.Fatalf("baseline not restored: %s", before)
			}
			response, err := client.PostForm(baseURL+"/orders", url.Values{"sku": {"NEW"}, "quantity": {"3"}})
			if err != nil {
				t.Fatal(err)
			}
			body, err := io.ReadAll(response.Body)
			response.Body.Close()
			if err != nil {
				t.Fatal(err)
			}
			if response.StatusCode != http.StatusOK || !strings.Contains(string(body), "NEW:3:ready") {
				t.Fatalf("create failed: HTTP %d: %s", response.StatusCode, body)
			}
		})
	}
}
