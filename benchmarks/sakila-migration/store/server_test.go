package store

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"strconv"
	"time"

	"github.com/go-sql-driver/mysql"
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
