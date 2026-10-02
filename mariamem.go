// Package mariamem starts disposable, isolated instances of real MariaDB for tests.
// The Go host and generated-Go MariaDB run in the caller's process.
// Clients use the ordinary MySQL wire protocol through a local
// endpoint, including database/sql with go-sql-driver/mysql.
//
// Zero options require no native bundle, runtime download or pre-populated cache.
// Options.NativeDir or MARIAMEM_NATIVE_DIR retains explicit legacy bundle support.
// Supported platforms are macOS 15+ arm64 and Ubuntu 24.04 x86_64.
//
// A Database owns its runtime and should be closed after use. Multiple SQL
// clients can connect up to the guest-advertised session capacity.
// Close the SQL pool and call Database.WaitDisconnected before taking a snapshot.
// Database.Snapshot creates a cold snapshot and closes its source database on
// success. Snapshot.Fork starts independent databases from the saved state.
// Closing a temporary snapshot removes its files; explicit destinations remain.
//
// A host query timeout or client cancellation during a query terminates that
// database instance. Database.Err reports the reason and ErrUnusable; close it
// and start or fork another instance. DSN enables client parameter interpolation
// for the text protocol, not server-side prepared statements.
package mariamem

import (
	"context"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sync"
	"time"

	"github.com/masahitojp/mariamem/internal/artifacts"
	"github.com/masahitojp/mariamem/internal/host"
	"github.com/masahitojp/mariamem/internal/runtimekind"
	"github.com/masahitojp/mariamem/internal/timing"
)

// Options configures a database instance. Zero timeouts use documented defaults.
type Options struct {
	NativeDir       string        // Compatibility bundle override; empty uses generated-Go unless MARIAMEM_NATIVE_DIR is set.
	StartupTimeout  time.Duration // Zero defaults to 120 seconds.
	ShutdownTimeout time.Duration // Zero defaults to 30 seconds.
	QueryTimeout    time.Duration // Zero defaults to 30 seconds; expiry terminates this instance.
}

func (o Options) defaults() (Options, error) {
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
	Failure() error
}

// Database owns one isolated guest instance and its temporary directory.
// Do not copy a Database; construct it with Start.
type Database struct {
	mu               sync.Mutex
	server           backend
	opts             Options
	info             ConnectionInfo
	build, temporary string
	closed           bool
	closeErr         error
	failure          error
	logs             logTail
}

// Start creates one database. Its context governs startup, not the lifetime of a
// successfully started database; call Close to dispose of it.
func Start(ctx context.Context, opts Options) (*Database, error) { return start(ctx, opts, "") }
func start(ctx context.Context, opts Options, restore string) (*Database, error) {
	ctx, finishTiming := timing.Begin(ctx, "api_startup")
	defer finishTiming()
	opts, err := opts.defaults()
	if err != nil {
		return nil, err
	}
	if err = ctx.Err(); err != nil {
		return nil, err
	}
	timing.Mark(ctx, "options_ready")
	var bundle artifacts.Bundle
	if kind := os.Getenv("MARIAMEM_RUNTIME"); kind != "" && kind != "generated-go" && kind != "wasmer" {
		return nil, fmt.Errorf("unsupported development runtime kind: %q", kind)
	}
	legacy := configuredRuntime(opts.NativeDir) == runtimekind.Wasmer
	if legacy {
		bundle, err = artifacts.ResolveStartup(ctx, opts.NativeDir, nativeInputHash())
		if err != nil {
			return nil, hostError(err, "artifacts", false)
		}
		opts.NativeDir = bundle.Dir
	} else {
		if err = artifacts.ValidatePlatform(ctx); err != nil {
			return nil, hostError(err, "platform", false)
		}
		bundle.Build = runtimekind.GuestSHA256
	}
	temp, err := os.MkdirTemp("", "mariamem-go-")
	if err != nil {
		return nil, err
	}
	db := &Database{opts: opts, build: bundle.Build, temporary: temp}
	runtimeDir := filepath.Join(temp, "runtime")
	if err = os.Mkdir(runtimeDir, 0700); err != nil {
		return nil, errors.Join(err, os.RemoveAll(temp))
	}
	timing.Mark(ctx, "runtime_directory_ready")
	startup, cancel := context.WithTimeout(ctx, opts.StartupTimeout)
	defer cancel()
	var s *host.Server
	if legacy {
		s, err = host.StartVerified(startup, bundle, runtimeDir, restore, opts.QueryTimeout, &db.logs)
	} else {
		s, err = host.StartGenerated(startup, "", restore, opts.QueryTimeout, &db.logs)
	}
	if err != nil {
		return nil, hostError(errors.Join(err, os.RemoveAll(temp)), "start", true)
	}
	timing.Mark(ctx, "host_returned")
	db.server = s
	db.info = ConnectionInfo{Host: "127.0.0.1", Port: s.Port(), User: "root", Database: "test"}
	go db.watch(s.Guest.Done())
	timing.Mark(ctx, "database_ready")
	return db, nil
}

// Explicit bundle overrides preserve legacy/offline compatibility; empty selects
// compiled generated-Go without consulting release discovery or native caches.
func configuredRuntime(dir string) runtimekind.Kind {
	if dir != "" || os.Getenv("MARIAMEM_NATIVE_DIR") != "" || os.Getenv("MARIAMEM_RUNTIME") == "wasmer" {
		return runtimekind.Wasmer
	}
	return runtimekind.GeneratedGo
}

func (db *Database) watch(done <-chan struct{}) {
	<-done
	db.mu.Lock()
	defer db.mu.Unlock()
	if !db.closed {
		db.failure = db.invalidLocked()
		_ = db.closeLocked()
	}
}

// Err reports why a running instance became unusable. It retains the underlying
// guest/host cause; a clean Close or successful Snapshot does not set Err.
func (db *Database) Err() error {
	db.mu.Lock()
	defer db.mu.Unlock()
	return db.invalidLocked()
}
func (db *Database) invalidLocked() error {
	if db.failure != nil {
		return db.failure
	}
	if db.closed {
		return nil
	}
	if db.server == nil {
		return nil
	}
	if cause := db.server.Failure(); cause != nil {
		return hostError(errors.Join(ErrUnusable, cause), "unusable", true)
	}
	return nil
}

// Closed reports whether the database has been disposed of or invalidated.
func (db *Database) Closed() bool {
	db.mu.Lock()
	defer db.mu.Unlock()
	return db.closed || db.server == nil || db.invalidLocked() != nil
}

// Close is idempotent; repeated calls return the stored cleanup result.
func (db *Database) Close() error { db.mu.Lock(); defer db.mu.Unlock(); return db.closeLocked() }
func (db *Database) closeLocked() error {
	if db.closed {
		return db.closeErr
	}
	if failure := db.invalidLocked(); failure != nil {
		db.failure = failure
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
		if err := db.invalidLocked(); err != nil {
			db.mu.Unlock()
			return err
		}
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
