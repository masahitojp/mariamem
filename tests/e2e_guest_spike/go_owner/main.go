// Experimental test owner: real Go public Snapshot/Fork API, no application changes.
package main

import (
	"bufio"
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

type request struct {
	Op string `json:"op"`
	ID int    `json:"id"`
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
	next := 0
	defer func() {
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
			if len(children) != 0 {
				err = fmt.Errorf("children still open")
			} else {
				err = saved.Close()
			}
		default:
			err = fmt.Errorf("unknown owner command")
		}
		stop()
		if err != nil {
			reply = map[string]any{"ok": false, "error": err.Error()}
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
