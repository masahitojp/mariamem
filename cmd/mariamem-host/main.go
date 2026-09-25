package main

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/masahitojp/mariamem/internal/host"
)

type request struct {
	ID          json.RawMessage `json:"id"`
	Op          string          `json:"op"`
	Destination string          `json:"destination"`
	Rollback    bool            `json:"rollback"`
	Timeout     string          `json:"timeout"`
}
type incoming struct {
	req      request
	err      error
	terminal bool
}

func run() error {
	runtime := flag.String("runtime", "", "path to wasmer-headless")
	module := flag.String("module", "", "path to multi-session AOT artifact")
	wasmerDir := flag.String("wasmer-dir", "", "Wasmer configuration/cache directory")
	restore := flag.String("snapshot", "", "validated cold snapshot to restore")
	queryTimeout := flag.Duration("query-timeout", 30*time.Second, "query/session timeout")
	startupTimeout := flag.Duration("startup-timeout", 120*time.Second, "startup timeout")
	shutdownTimeout := flag.Duration("shutdown-timeout", 30*time.Second, "shutdown timeout")
	flag.Parse()
	if *runtime == "" || *module == "" {
		return errors.New("--runtime and --module are required")
	}
	if *queryTimeout <= 0 || *startupTimeout <= 0 || *shutdownTimeout <= 0 {
		return errors.New("timeouts must be positive")
	}
	signals, stopSignals := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stopSignals()
	owner, cancelOwner := context.WithCancel(signals)
	defer cancelOwner()
	ctx, cancel := context.WithTimeout(owner, *startupTimeout)
	s, err := host.Start(ctx, *runtime, *module, *wasmerDir, *restore, *queryTimeout, os.Stderr)
	cancel()
	if err != nil {
		return err
	}
	closed := false
	shutdown := func() error {
		if closed {
			return nil
		}
		closed = true
		ctx, cancel := context.WithTimeout(context.Background(), *shutdownTimeout)
		defer cancel()
		return s.Close(ctx)
	}
	defer shutdown()
	enc := json.NewEncoder(os.Stdout)
	token := make([]byte, 16)
	if _, err = rand.Read(token); err != nil {
		return err
	}
	caps := []string{"status", "close", "text-query", "reconnect"}
	if s.SnapshotCapable() {
		caps = append(caps, "snapshot", "fork")
	}
	if err = enc.Encode(map[string]any{"event": "ready", "protocol": 1, "id": hex.EncodeToString(token), "pid": os.Getpid(), "runtime_pid": s.Guest.PID(), "host": "127.0.0.1", "port": s.Port(), "user": "root", "password": "", "database": "test", "capabilities": caps, "max_connections": 1}); err != nil {
		return err
	}
	messages := make(chan incoming, 1)
	go func() {
		scanner := bufio.NewScanner(os.Stdin)
		scanner.Buffer(make([]byte, 4096), 65536)
		for scanner.Scan() {
			var req request
			err := json.Unmarshal(scanner.Bytes(), &req)
			messages <- incoming{req: req, err: err}
		}
		err := scanner.Err()
		if err == nil {
			err = io.EOF
		}
		messages <- incoming{err: err, terminal: true}
		cancelOwner()
	}()
	for {
		select {
		case <-owner.Done():
			return shutdown()
		case <-s.Guest.Done():
			_ = shutdown()
			return fmt.Errorf("database runtime exited: %w", s.Failure())
		case msg := <-messages:
			if msg.terminal {
				err := shutdown()
				if !errors.Is(msg.err, io.EOF) {
					return errors.Join(msg.err, err)
				}
				return err
			}
			id := msg.req.ID
			if len(id) == 0 {
				id = json.RawMessage("null")
			}
			reply := map[string]any{"id": id, "ok": false}
			if msg.err != nil {
				reply["error"] = map[string]string{"code": "protocol", "message": msg.err.Error()}
			} else {
				switch msg.req.Op {
				case "status":
					if failure := s.Failure(); failure != nil {
						reply["closed"] = true
						reply["error"] = map[string]string{"code": "unusable", "message": "database instance terminated: " + failure.Error()}
					} else {
						reply["ok"] = true
						reply["state"] = "ready"
						reply["active_connections"] = s.Active()
						reply["busy"] = s.Busy()
					}
				case "snapshot":
					timeout := 120 * time.Second
					if msg.req.Timeout != "" {
						var e error
						timeout, e = time.ParseDuration(msg.req.Timeout)
						if e != nil || timeout <= 0 {
							reply["error"] = map[string]string{"code": "protocol", "message": "invalid snapshot timeout"}
							break
						}
					}
					ctx, cancel := context.WithTimeout(owner, timeout)
					accepted, e := s.Snapshot(ctx, msg.req.Destination, msg.req.Rollback)
					cancel()
					closed = accepted
					reply["ok"] = e == nil
					reply["closed"] = accepted
					if e != nil {
						code := "snapshot_failed"
						var rejected *host.Rejected
						if errors.As(e, &rejected) {
							code = rejected.Code
						}
						reply["error"] = map[string]string{"code": code, "message": e.Error()}
					} else {
						reply["path"] = msg.req.Destination
					}
					if accepted {
						if err := enc.Encode(reply); err != nil {
							return err
						}
						return e
					}
				case "close":
					err := shutdown()
					reply["ok"] = err == nil
					if err != nil {
						reply["error"] = map[string]string{"code": "shutdown_failed", "message": err.Error()}
					}
					if e := enc.Encode(reply); e != nil {
						return e
					}
					return err
				default:
					reply["error"] = map[string]string{"code": "unsupported", "message": "operation is not implemented"}
				}
			}
			if err := enc.Encode(reply); err != nil {
				return err
			}
		}
	}
}
func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, "mariamem:", err)
		os.Exit(1)
	}
}
