// Experimental test owner: real Go public Snapshot/Fork API, no application changes.
package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"fmt"
	"github.com/masahitojp/mariamem/internal/diagnostic"
	endpoint "github.com/masahitojp/mariamem/internal/live"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

type request struct {
	Op      string `json:"op"`
	ID      int    `json:"id"`
	DrainMs int    `json:"drain_ms"`
}

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
func run() error {
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		return err
	}
	defer source.Close()
	db, err := sql.Open("mysql", source.DSN())
	if err != nil {
		return err
	}
	if _, err = db.ExecContext(ctx, "CREATE DATABASE e2e_app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"); err != nil {
		db.Close()
		return err
	}
	if _, err = db.ExecContext(ctx, "USE e2e_app"); err != nil {
		db.Close()
		return err
	}
	// Use one physical session for this fixed authored schema, not a dump parser.
	conn, err := db.Conn(ctx)
	if err != nil {
		db.Close()
		return err
	}
	if _, err = conn.ExecContext(ctx, "USE e2e_app"); err != nil {
		conn.Close()
		db.Close()
		return err
	}
	raw, err := os.ReadFile(os.Args[1])
	if err != nil {
		conn.Close()
		db.Close()
		return err
	}
	for _, stmt := range strings.Split(string(raw), ";") {
		if strings.TrimSpace(stmt) != "" {
			if _, err = conn.ExecContext(ctx, stmt); err != nil {
				conn.Close()
				db.Close()
				return err
			}
		}
	}
	conn.Close()
	db.Close()
	if err = source.WaitDisconnected(ctx); err != nil {
		return err
	}
	saved, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer saved.Close()
	out := json.NewEncoder(os.Stdout)
	if err = out.Encode(map[string]any{"ready": true, "source_consumed": source.Closed()}); err != nil {
		return err
	}
	children := map[int]*mariamem.Database{}
	lives := map[int]*mariamem.Live{}
	probes := map[int]*endpoint.Endpoint{}
	failures := map[int]*bool{}
	closedBaseline := false
	originalAddresses := map[int]string{}
	next := 0
	defer func() {
		for _, l := range lives {
			_ = l.Close()
		}
		for _, p := range probes {
			_ = p.FinalCleanup()
		}
		for _, child := range children {
			child.Close()
		}
	}()
	scanner := bufio.NewScanner(os.Stdin)
	for scanner.Scan() {
		var r request
		if err = json.Unmarshal(scanner.Bytes(), &r); err != nil {
			return err
		}
		reply := map[string]any{"ok": true}
		c, stop := context.WithTimeout(context.Background(), 60*time.Second)
		switch r.Op {
		case "live_create":
			var l *mariamem.Live
			l, err = saved.Live(c)
			if err == nil {
				next++
				lives[next] = l
				reply["id"] = next
				reply["info"] = info(l.ConnectionInfo())
				reply["status"] = l.Status()
			}
		case "live_reset":
			l := lives[r.ID]
			if l == nil {
				err = fmt.Errorf("unknown live")
				break
			}
			err = l.Reset(c, mariamem.ResetOptions{DrainTimeout: time.Duration(r.DrainMs) * time.Millisecond})
			reply["status"] = l.Status()
		case "live_status":
			l := lives[r.ID]
			if l == nil {
				err = fmt.Errorf("unknown live")
				break
			}
			reply["status"] = l.Status()
		case "live_close":
			l := lives[r.ID]
			if l == nil {
				err = fmt.Errorf("unknown live")
				break
			}
			err = l.Close()
			reply["closed"] = l.Status().State == "closed"
			reply["status"] = l.Status()
			if err == nil {
				delete(lives, r.ID)
			}
		case "probe_create":
			fail := false
			originalAddress := ""
			factory := endpoint.Factory{Check: func() error {
				if closedBaseline {
					return fmt.Errorf("closed baseline")
				}
				return nil
			}, Start: func(ctx context.Context) (endpoint.Child, error) {
				if fail {
					return nil, fmt.Errorf("E2E_INJECTED_FORK_FAILURE")
				}
				db, e := saved.Fork(ctx)
				if e != nil {
					return nil, e
				}
				if originalAddress == "" {
					i := db.ConnectionInfo()
					originalAddress = net.JoinHostPort(i.Host, strconv.Itoa(i.Port))
				}
				return probeChild{db}, nil
			}}
			var p *endpoint.Endpoint
			p, err = endpoint.New(c, factory, 30*time.Second)
			if err == nil {
				next++
				probes[next] = p
				failures[next] = &fail
				originalAddresses[next] = originalAddress
				reply["original_address"] = originalAddress
				reply["id"] = next
				reply["info"] = map[string]any{"host": "127.0.0.1", "port": p.Port(), "user": "root", "password": "", "database": "e2e_app"}
				reply["status"] = p.Status()
			}
		case "probe_fail":
			p := failures[r.ID]
			if p == nil {
				err = fmt.Errorf("unknown probe")
				break
			}
			*p = true
		case "probe_recover":
			p := failures[r.ID]
			if p == nil {
				err = fmt.Errorf("unknown probe")
				break
			}
			*p = false
		case "probe_reset":
			p := probes[r.ID]
			if p == nil {
				err = fmt.Errorf("unknown probe")
				break
			}
			err = p.Reset(c, time.Second)
			reply["status"] = p.Status()
		case "probe_status":
			p := probes[r.ID]
			if p == nil {
				err = fmt.Errorf("unknown probe")
				break
			}
			reply["status"] = p.Status()
		case "probe_close":
			p := probes[r.ID]
			if p == nil {
				err = fmt.Errorf("unknown probe")
				break
			}
			err = p.Close()
			reply["closed"] = true
			reply["status"] = p.Status()
			if err == nil {
				delete(probes, r.ID)
				delete(failures, r.ID)
			}
		case "baseline_close":
			err = saved.Close()
			closedBaseline = true
		case "fork":
			var child *mariamem.Database
			child, err = saved.Fork(c)
			if err == nil {
				next++
				children[next] = child
				info := child.ConnectionInfo()
				reply["id"] = next
				reply["info"] = map[string]any{"host": info.Host, "port": info.Port, "user": info.User, "password": info.Password, "database": "e2e_app"}
			}
		case "wait", "close":
			child, exists := children[r.ID]
			if !exists {
				err = fmt.Errorf("unknown child %s", strconv.Itoa(r.ID))
				break
			}
			err = child.WaitDisconnected(c)
			if err == nil && r.Op == "close" {
				err = child.Close()
				if err == nil {
					reply["closed"] = child.Closed()
					delete(children, r.ID)
				}
			}
		case "shutdown":
			if len(children) != 0 || len(lives) != 0 || len(probes) != 0 {
				err = fmt.Errorf("children still open")
			} else {
				err = saved.Close()
			}
		default:
			err = fmt.Errorf("unknown owner command")
		}
		stop()
		if err != nil {
			reply["ok"] = false
			reply["error"] = err.Error()
			var h *mariamem.HostError
			if errors.As(err, &h) {
				reply["code"] = h.Code
				reply["stage"] = h.Stage
			}
			var d *diagnostic.Error
			if errors.As(err, &d) {
				reply["code"] = d.Code
				reply["stage"] = d.Stage
			}
		}
		if e := out.Encode(reply); e != nil {
			return e
		}
		if r.Op == "shutdown" && err == nil {
			return nil
		}
		err = nil
	}
	return scanner.Err()
}

func info(i mariamem.ConnectionInfo) map[string]any {
	return map[string]any{"host": i.Host, "port": i.Port, "user": i.User, "password": i.Password, "database": "e2e_app"}
}

type probeChild struct{ *mariamem.Database }

func (p probeChild) Address() string {
	i := p.ConnectionInfo()
	return net.JoinHostPort(i.Host, strconv.Itoa(i.Port))
}

// The probe is test-only and bound to the canonical guest's16 session profile.
func (p probeChild) Capacity() int  { return 16 }
func (p probeChild) Failure() error { return p.Err() }
