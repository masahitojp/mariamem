package ownedexample

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/mariamemtest"
)

type app struct {
	cmd     *exec.Cmd
	url     string
	stopped bool
	stopErr error
}

func (a *app) BaseURL() string                            { return a.url }
func (a *app) Identity() string                           { return fmt.Sprint(a.cmd.Process.Pid) }
func (a *app) QuiesceAndRetire(ctx context.Context) error { return ctx.Err() } // sole work source; unchanged MaxIdleConns(0) app
func (a *app) StopReap(ctx context.Context) error {
	if a.stopped {
		return a.stopErr
	}
	a.stopped = true
	signalErr := a.cmd.Process.Signal(os.Interrupt)
	done := make(chan error, 1)
	go func() { done <- a.cmd.Wait() }()
	select {
	case err := <-done:
		a.stopErr = errors.Join(signalErr, err)
	case <-ctx.Done():
		_ = a.cmd.Process.Kill()
		err := <-done
		a.stopErr = errors.Join(ctx.Err(), err)
	}
	return a.stopErr
}
func prepare(ctx context.Context, db *mariamem.Database) error {
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer pool.Close()
	pool.SetMaxOpenConns(1)
	conn, err := pool.Conn(ctx)
	if err != nil {
		return err
	}
	defer conn.Close()
	for _, s := range []string{"CREATE DATABASE e2e_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci", "USE e2e_app"} {
		if _, err = conn.ExecContext(ctx, s); err != nil {
			return err
		}
	}
	schema, err := os.ReadFile("../../../../tests/e2e_native_control/goapp/schema.sql")
	if err != nil {
		return err
	}
	for _, s := range strings.Split(string(schema), ";") {
		if strings.TrimSpace(s) != "" {
			if _, err = conn.ExecContext(ctx, s); err != nil {
				return err
			}
		}
	}
	return nil
}
func start(ctx context.Context, target mariamem.ConnectionInfo, register func(mariamemtest.HTTPApp) error) (mariamemtest.HTTPApp, error) {
	config := mysql.NewConfig()
	config.User = target.User
	config.Passwd = target.Password
	config.Net = "tcp"
	config.Addr = fmt.Sprintf("%s:%d", target.Host, target.Port)
	config.DBName = "e2e_app"
	config.ParseTime = true
	binary, err := filepath.Abs(os.Getenv("E2E_GO_APP"))
	if err != nil || os.Getenv("E2E_GO_APP") == "" {
		return nil, errors.New("set E2E_GO_APP")
	}
	cmd := exec.Command(binary)
	cmd.Env = append(os.Environ(), "E2E_MYSQL_DSN="+config.FormatDSN())
	cmd.Stderr = os.Stderr
	out, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}
	if err = cmd.Start(); err != nil {
		_ = out.Close()
		return nil, err
	}
	a := &app{cmd: cmd}
	if err = register(a); err != nil {
		stop := a.StopReap(context.Background())
		return nil, errors.Join(err, stop)
	}
	var ready struct {
		Address string `json:"address"`
		PID     int    `json:"pid"`
	}
	done := make(chan error, 1)
	go func() { done <- json.NewDecoder(out).Decode(&ready) }()
	select {
	case err = <-done:
		if err != nil {
			return nil, err
		}
	case <-ctx.Done():
		return nil, ctx.Err()
	}
	if ready.PID != cmd.Process.Pid {
		return nil, errors.New("wrong PID")
	}
	a.url = "http://" + ready.Address
	return a, nil
}
func TestOwnedOrders(t *testing.T) {
	if os.Getenv("E2E_OWNED_RUNTIME") != "1" {
		t.Skip("set E2E_OWNED_RUNTIME=1")
	}
	owner := mariamemtest.NewHTTP(t, mariamemtest.HTTPConfig{Prepare: prepare, StartReady: start, SoleWorkSource: true})
	for _, name := range []string{"first", "second"} {
		t.Run(name, func(t *testing.T) {
			c := owner.Case(t)
			response, err := c.Client.Get(c.BaseURL + "/orders")
			if err != nil {
				t.Fatal(err)
			}
			body, err := io.ReadAll(response.Body)
			response.Body.Close()
			if err != nil {
				t.Fatal(err)
			}
			if !strings.Contains(string(body), "SEED:2:ready") || strings.Contains(string(body), "NEW:3:ready") {
				t.Fatal("seed not restored", string(body))
			}
			response, err = c.Client.PostForm(c.BaseURL+"/orders", url.Values{"sku": {"NEW"}, "quantity": {"3"}})
			if err != nil {
				t.Fatal(err)
			}
			body, err = io.ReadAll(response.Body)
			response.Body.Close()
			if err != nil || response.StatusCode != 200 || !strings.Contains(string(body), "NEW:3:ready") {
				t.Fatalf("insert: %v HTTP%d %s", err, response.StatusCode, body)
			}
		})
	}
}
