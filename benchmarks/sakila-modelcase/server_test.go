package sakila

import (
	"context"
	"crypto/rand"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/docker/go-connections/nat"
	"github.com/go-sql-driver/mysql"
	"github.com/testcontainers/testcontainers-go"
	"github.com/testcontainers/testcontainers-go/wait"
)

func openDB(dsn string) (*sql.DB, error) {
	cfg, err := mysql.ParseDSN(dsn)
	if err != nil {
		return nil, errors.New("invalid MySQL DSN")
	}
	cfg.InterpolateParams = true
	cfg.Timeout = 2 * time.Second
	db, err := mysql.NewConnector(cfg)
	if err != nil {
		return nil, err
	}
	pool := sql.OpenDB(db)
	pool.SetMaxOpenConns(8)
	pool.SetMaxIdleConns(8)
	return pool, nil
}

func nonce() (string, error) {
	var data [16]byte
	_, err := rand.Read(data[:])
	return hex.EncodeToString(data[:]), err
}

func sharedServer(ctx context.Context, mode, image string) (dsn string, stop func() error, err error) {
	if mode == "mysql" {
		dsn := os.Getenv("SAKILA_MYSQL_DSN")
		if dsn == "" {
			return "", nil, errors.New("SAKILA_MYSQL_DSN is required for MySQL mode")
		}
		return dsn, func() error { return nil }, nil
	}
	password, err := nonce()
	if err != nil {
		return "", nil, err
	}
	env := map[string]string{"MYSQL_ROOT_PASSWORD": password}
	cfg := mysql.NewConfig()
	cfg.Net, cfg.User, cfg.Passwd = "tcp", "root", password
	port := nat.Port("3306/tcp")

	switch mode {
	case "testcontainers":
		request := testcontainers.ContainerRequest{
			Image:        image,
			Env:          env,
			ExposedPorts: []string{string(port)},
			WaitingFor:   wait.ForListeningPort(port).SkipInternalCheck(),
		}
		container, err := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{ContainerRequest: request, Started: true})
		if container != nil {
			stop = func() error {
				ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
				defer cancel()
				return container.Terminate(ctx)
			}
		}
		if err != nil {
			return "", stop, err
		}
		host, err := container.Host(ctx)
		if err != nil {
			return "", stop, err
		}
		mapped, err := container.MappedPort(ctx, port)
		if err != nil {
			return "", stop, err
		}
		cfg.Addr = net.JoinHostPort(host, mapped.Port())
	case "docker":
		command := exec.CommandContext(ctx, "docker", "run", "-d",
			"-p", "127.0.0.1::3306", "-e", "MYSQL_ROOT_PASSWORD", image)
		command.Env = append(os.Environ(), "MYSQL_ROOT_PASSWORD="+password)
		output, err := command.Output()
		if err != nil {
			return "", nil, err
		}
		id := strings.TrimSpace(string(output))
		stop = func() error {
			ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			return exec.CommandContext(ctx, "docker", "rm", "-fv", id).Run()
		}
		mapped, err := exec.CommandContext(ctx, "docker", "port", id, string(port)).Output()
		if err != nil {
			return "", stop, err
		}
		cfg.Addr = strings.TrimSpace(string(mapped))
	default:
		return "", nil, fmt.Errorf("unknown backend %q", mode)
	}
	return cfg.FormatDSN(), stop, nil
}

func waitReady(ctx context.Context, db *sql.DB) (string, error) {
	for {
		var version string
		err := db.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version)
		if err == nil {
			return version, nil
		}
		select {
		case <-ctx.Done():
			return "", fmt.Errorf("SQL readiness: %w", errors.Join(ctx.Err(), err))
		case <-time.After(50 * time.Millisecond):
		}
	}
}

func ownedSchema(ctx context.Context, admin *sql.DB, dsn string) (_ *sql.DB, drop func() error, err error) {
	suffix, err := nonce()
	if err != nil {
		return nil, nil, err
	}
	name := "sakila_bench_" + suffix
	if _, err := admin.ExecContext(ctx, "CREATE DATABASE "+name); err != nil {
		return nil, nil, err
	}
	drop = func() error {
		cleanup, cancel := context.WithTimeout(context.Background(), 15*time.Second)
		defer cancel()
		_, err := admin.ExecContext(cleanup, "DROP DATABASE "+name)
		return err
	}
	cfg, err := mysql.ParseDSN(dsn)
	if err != nil {
		return nil, drop, errors.New("invalid MySQL DSN")
	}
	cfg.DBName = name
	db, err := openDB(cfg.FormatDSN())
	return db, drop, err
}

func config(db *sql.DB, ctx context.Context) (map[string]string, error) {
	values := map[string]string{}
	for _, key := range []string{"innodb_flush_log_at_trx_commit", "sync_binlog", "log_bin", "max_connections"} {
		var value string
		if err := db.QueryRowContext(ctx, "SELECT @@"+key).Scan(&value); err != nil {
			return nil, err
		}
		values[key] = value
	}
	if _, err := strconv.Atoi(values["max_connections"]); err != nil {
		return nil, err
	}
	return values, nil
}
