package main

import (
	"bytes"
	"context"
	"database/sql"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"path/filepath"
	"syscall"
	"time"

	"github.com/masahitojp/mariamem/benchmarks/sakila-migration/internal/trace"

	"github.com/go-sql-driver/mysql"
)

type sample struct {
	startedMonoNS    int64
	started, stopped time.Time
	Mode             string            `json:"mode"`
	Trial            int               `json:"trial"`
	ReadyMS          float64           `json:"ready_ms"`
	StartCallMS      float64           `json:"start_call_ms"`
	Attempts         int               `json:"query_attempts"`
	Version          string            `json:"version"`
	Settings         map[string]string `json:"settings"`
}

func open(cfg *mysql.Config) (*sql.DB, error) {
	cfg.Timeout = 50 * time.Millisecond
	connector, err := mysql.NewConnector(cfg)
	if err != nil {
		return nil, err
	}
	pool := sql.OpenDB(connector)
	pool.SetMaxOpenConns(1)
	return pool, nil
}

func waitSQL(ctx context.Context, pool *sql.DB, started time.Time, r *sample) error {
	ticker := time.NewTicker(time.Millisecond)
	defer ticker.Stop()
	for {
		var one int
		r.Attempts++
		err := pool.QueryRowContext(ctx, "SELECT 1").Scan(&one)
		if err == nil {
			if one != 1 {
				return fmt.Errorf("SELECT 1 returned %d", one)
			}
			r.ReadyMS = float64(time.Since(started)) / float64(time.Millisecond)
			return nil
		}
		select {
		case <-ctx.Done():
			return errors.Join(ctx.Err(), err)
		case <-ticker.C:
		}
	}
}

func inspect(ctx context.Context, pool *sql.DB, r *sample) error {
	if err := pool.QueryRowContext(ctx, "SELECT VERSION()").Scan(&r.Version); err != nil {
		return err
	}
	r.Settings = make(map[string]string)
	for _, key := range []string{"innodb_buffer_pool_size", "innodb_log_file_size", "innodb_flush_log_at_trx_commit", "log_bin", "max_connections"} {
		var value string
		if err := pool.QueryRowContext(ctx, "SELECT @@"+key).Scan(&value); err != nil {
			return err
		}
		r.Settings[key] = value
	}
	return nil
}

func native(ctx context.Context, r *sample, template, root, bufferPool string, run func(string) error) (err error) {
	path, err := os.MkdirTemp(root, "native-ready-")
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, os.RemoveAll(path)) }()
	data := filepath.Join(path, "data")
	if output, err := exec.CommandContext(ctx, "cp", "-a", template, data).CombinedOutput(); err != nil {
		return fmt.Errorf("copy initialized directory: %w: %s", err, output)
	}

	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return err
	}
	address := listener.Addr().(*net.TCPAddr)
	if err := listener.Close(); err != nil {
		return err
	}
	cfg := mysql.NewConfig()
	cfg.Net, cfg.Addr, cfg.User, cfg.DBName = "tcp", address.String(), "root", "test"
	pool, err := open(cfg)
	if err != nil {
		return err
	}
	defer pool.Close()

	cmd := exec.CommandContext(ctx, "mariadbd", "--no-defaults",
		"--datadir="+data, "--pid-file="+filepath.Join(path, "pid"),
		"--socket="+filepath.Join(path, "s"), "--bind-address=127.0.0.1",
		fmt.Sprintf("--port=%d", address.Port), "--user=root", "--skip-log-bin",
		"--innodb-buffer-pool-size="+bufferPool)
	if os.Getenv("NATIVE_READY_NO_SSL") != "" {
		cmd.Args = append(cmd.Args, "--skip-ssl")
	} else if os.Getenv("NATIVE_READY_PREBUILT_TLS") != "" {
		cmd.Args = append(cmd.Args, "--ssl-cert=/control/cert.pem", "--ssl-key=/control/key.pem")
	}
	var output bytes.Buffer
	cmd.Stdout, cmd.Stderr = &output, &output
	start := time.Now()
	r.started = start
	r.startedMonoNS = trace.MonotonicNS()
	if err := cmd.Start(); err != nil {
		return err
	}
	r.StartCallMS = float64(time.Since(start)) / float64(time.Millisecond)
	defer func() {
		signalErr := cmd.Process.Signal(syscall.SIGTERM)
		if errors.Is(signalErr, os.ErrProcessDone) {
			signalErr = nil
		}
		err = errors.Join(err, signalErr, cmd.Wait())
		r.stopped = time.Now()
		if err != nil {
			err = fmt.Errorf("%w\n%s", err, output.Bytes())
		}
	}()
	if err := waitSQL(ctx, pool, start, r); err != nil {
		return err
	}
	if err := inspect(ctx, pool, r); err != nil {
		return err
	}
	return run(cfg.FormatDSN())
}

func prepareApp(ctx context.Context, dsn string) (string, func(), error) {
	cfg, err := mysql.ParseDSN(dsn)
	if err != nil {
		return "", nil, err
	}
	admin, err := open(cfg)
	if err != nil {
		return "", nil, err
	}
	if _, err := admin.ExecContext(ctx, "CREATE DATABASE sakila_app"); err != nil {
		admin.Close()
		return "", nil, err
	}
	drop := func() {
		defer admin.Close()
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if _, err := admin.ExecContext(ctx, "DROP DATABASE sakila_app"); err != nil {
			log.Printf("drop benchmark database: %v", err)
		}
	}
	cfg.DBName = "sakila_app"
	app, err := open(cfg)
	if err != nil {
		drop()
		return "", nil, err
	}
	defer app.Close()
	var one int
	if err := app.QueryRowContext(ctx, "SELECT 1").Scan(&one); err != nil {
		drop()
		return "", nil, err
	}
	if one != 1 {
		drop()
		return "", nil, fmt.Errorf("unexpected app readiness value %d", one)
	}
	return cfg.FormatDSN(), drop, nil
}
