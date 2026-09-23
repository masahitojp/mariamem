// Package mariamem provides disposable MariaDB instances for tests.
// The Go host runs in the caller; the Wasmer/MariaDB guest remains a subprocess.
package mariamem

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"mariamem/internal/artifacts"
	"mariamem/internal/host"
)

type Options struct {
	NativeDir       string
	StartupTimeout  time.Duration // Zero defaults to 120 seconds.
	ShutdownTimeout time.Duration // Zero defaults to 30 seconds.
	QueryTimeout    time.Duration // Zero defaults to 30 seconds; expiry is instance-fatal.
}

func (o Options) defaults() (Options, error) {
	if o.NativeDir == "" {
		return o, fmt.Errorf("NativeDir is required")
	}
	for _, field := range []struct {
		p        *time.Duration
		fallback time.Duration
	}{{&o.StartupTimeout, 120 * time.Second}, {&o.ShutdownTimeout, 30 * time.Second}, {&o.QueryTimeout, 30 * time.Second}} {
		if *field.p < 0 {
			return o, fmt.Errorf("timeouts must not be negative")
		}
		if *field.p == 0 {
			*field.p = field.fallback
		}
	}
	return o, nil
}

type backend interface {
	Close(context.Context) error
	Snapshot(context.Context, string, bool) (bool, error)
	Active() int
}

// Database owns one guest process and its temporary runtime directory.
// Do not copy a Database; construct it with Start.
type Database struct {
	mu               sync.Mutex
	server           backend
	opts             Options
	info             ConnectionInfo
	build, temporary string
	closed           bool
	closeErr         error
	logs             logTail
}

// Start's context governs startup, not the lifetime of a successfully started DB.
func Start(ctx context.Context, opts Options) (*Database, error) { return start(ctx, opts, "") }
func start(ctx context.Context, opts Options, restore string) (*Database, error) {
	opts, err := opts.defaults()
	if err != nil {
		return nil, err
	}
	if err = ctx.Err(); err != nil {
		return nil, err
	}
	bundle, err := artifacts.Resolve(opts.NativeDir)
	if err != nil {
		return nil, hostError(err, "artifacts", false)
	}
	opts.NativeDir = bundle.Dir
	temp, err := os.MkdirTemp("", "mariamem-go-")
	if err != nil {
		return nil, err
	}
	db := &Database{opts: opts, build: bundle.Build, temporary: temp}
	runtimeDir := filepath.Join(temp, "runtime")
	if err = os.Mkdir(runtimeDir, 0700); err != nil {
		return nil, errors.Join(err, os.RemoveAll(temp))
	}
	startup, cancel := context.WithTimeout(ctx, opts.StartupTimeout)
	defer cancel()
	s, err := host.Start(startup, bundle.Runtime, bundle.Module, runtimeDir, restore, opts.QueryTimeout, &db.logs)
	if err != nil {
		return nil, hostError(errors.Join(err, os.RemoveAll(temp)), "start", true)
	}
	db.server = s
	db.info = ConnectionInfo{Host: "127.0.0.1", Port: s.Port(), User: "root", Database: "test"}
	go db.watch(s.Guest.Done())
	return db, nil
}
func (db *Database) watch(done <-chan struct{}) {
	<-done
	db.mu.Lock()
	defer db.mu.Unlock()
	if !db.closed {
		db.closeErr = errors.Join(hostError(errors.New("runtime exited"), "runtime_exited", true), db.closeLocked())
	}
}

func (db *Database) Closed() bool {
	db.mu.Lock()
	defer db.mu.Unlock()
	return db.closed || db.server == nil
}

// Close is idempotent; repeated calls return the stored cleanup result.
func (db *Database) Close() error { db.mu.Lock(); defer db.mu.Unlock(); return db.closeLocked() }
func (db *Database) closeLocked() error {
	if db.closed {
		return db.closeErr
	}
	db.closed = true
	var err error
	if db.server != nil {
		ctx, cancel := context.WithTimeout(context.Background(), db.opts.ShutdownTimeout)
		err = db.server.Close(ctx)
		cancel()
	}
	db.closeErr = hostError(errors.Join(err, db.removeTemporary()), "close", true)
	return db.closeErr
}
func (db *Database) removeTemporary() error {
	if db.temporary == "" {
		return nil
	}
	err := os.RemoveAll(db.temporary)
	if err == nil {
		db.temporary = ""
	}
	return err
}

// WaitDisconnected waits for driver disconnect and host session cleanup.
// Close the database/sql pool first. No implicit deadline is added.
func (db *Database) WaitDisconnected(ctx context.Context) error {
	for {
		if err := ctx.Err(); err != nil {
			return err
		}
		db.mu.Lock()
		if db.closed || db.server == nil {
			db.mu.Unlock()
			return hostError(ErrClosed, "closed", true)
		}
		active := db.server.Active()
		db.mu.Unlock()
		if active == 0 {
			return nil
		}
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(5 * time.Millisecond):
		}
	}
}

// Logs returns at most the last 16 KiB of guest diagnostics, including after Close.
func (db *Database) Logs() string {
	db.logs.mu.Lock()
	defer db.logs.mu.Unlock()
	return string(db.logs.data)
}

type logTail struct {
	mu   sync.Mutex
	data []byte
}

func (l *logTail) Write(p []byte) (int, error) {
	l.mu.Lock()
	defer l.mu.Unlock()
	const limit = 16 * 1024
	n := len(p)
	if n >= limit {
		l.data = append(l.data[:0], p[n-limit:]...)
	} else {
		if len(l.data)+n > limit {
			l.data = l.data[len(l.data)+n-limit:]
		}
		l.data = append(l.data, p...)
	}
	return n, nil
}
