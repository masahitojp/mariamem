package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"strings"
	"time"
)

type report struct {
	Crash            bool     `json:"crash_fixture"`
	RecoveryBranches []int64  `json:"recovery_branches"`
	Success          bool     `json:"success"`
	Error            string   `json:"error,omitempty"`
	Mode             string   `json:"mode"`
	Fixture          string   `json:"fixture"`
	RecoveryLogs     []string `json:"recovery_logs"`
	PoisonWitnesses  int      `json:"poison_witnesses"`
	VerifiedForks    int      `json:"verified_forks"`
}

func open(d *mariamem.Database) (*sql.DB, error) {
	cfg, e := mysql.ParseDSN(d.DSN())
	if e != nil {
		return nil, e
	}
	cfg.DialFunc = d.DialContext
	c, e := mysql.NewConnector(cfg)
	if e != nil {
		return nil, e
	}
	b := sql.OpenDB(c)
	b.SetMaxOpenConns(1)
	return b, nil
}
func poison(d *mariamem.Database, r *report) error {
	if r.Mode != "poison" {
		return nil
	}
	if !strings.Contains(d.Logs(), "BP_ZERO_WITNESS pool=16777216 descriptor=233856 frames=1008 page=16384 aligned=1") {
		return fmt.Errorf("missing poison witness")
	}
	r.PoisonWitnesses++
	return nil
}
func run(ctx context.Context, r *report) (err error) {
	d, e := mariamem.Start(ctx, mariamem.Options{})
	if e != nil {
		return e
	}
	owned := true
	defer func() {
		if owned {
			err = errors.Join(err, d.Close())
		}
	}()
	if e = poison(d, r); e != nil {
		return e
	}
	b, e := open(d)
	if e != nil {
		return e
	}
	_, e = b.ExecContext(ctx, "SET GLOBAL innodb_flush_log_at_trx_commit=1")
	if e != nil {
		b.Close()
		return e
	}
	_, e = b.ExecContext(ctx, "CREATE TABLE recoveryprobe(id INT PRIMARY KEY,v INT NOT NULL,payload BLOB NOT NULL) ENGINE=InnoDB")
	if e != nil {
		b.Close()
		return e
	}
	tx, e := b.BeginTx(ctx, nil)
	if e != nil {
		b.Close()
		return e
	}
	st, e := tx.PrepareContext(ctx, "INSERT INTO recoveryprobe VALUES(?,?,?)")
	if e != nil {
		tx.Rollback()
		b.Close()
		return e
	}
	for i := 1; i <= 512; i++ {
		if _, e = st.ExecContext(ctx, i, i*17, []byte(strings.Repeat(fmt.Sprintf("%08x", i), 512))); e != nil {
			st.Close()
			tx.Rollback()
			b.Close()
			return e
		}
	}
	e = errors.Join(st.Close(), tx.Commit(), b.Close())
	if e != nil {
		return e
	}
	if e = d.WaitDisconnected(ctx); e != nil {
		return e
	}
	if r.Crash {
		os.Setenv("MARIAMEM_BP_CRASH_FIXTURE_INTERNAL", "1")
	}
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	os.Unsetenv("MARIAMEM_BP_CRASH_FIXTURE_INTERNAL")
	if e != nil {
		return e
	}
	owned = false
	defer func() { err = errors.Join(err, s.Close()) }()
	for k := 0; k < 2; k++ {
		base.ResetBPRecovery()
		c, e := s.Fork(ctx)
		if e != nil {
			return e
		}
		if e = poison(c, r); e != nil {
			c.Close()
			return e
		}
		branches := base.BPRecoveryCount()
		r.RecoveryBranches = append(r.RecoveryBranches, branches)
		if (r.Crash && branches < 1) || (!r.Crash && branches != 0) {
			c.Close()
			return fmt.Errorf("recovery witness mismatch crash=%v branches=%d", r.Crash, branches)
		}
		db, e := open(c)
		if e != nil {
			c.Close()
			return e
		}
		rows, e := db.QueryContext(ctx, "SELECT id,v,HEX(payload) FROM recoveryprobe ORDER BY id")
		if e != nil {
			db.Close()
			c.Close()
			return e
		}
		count := 0
		for rows.Next() {
			var id, v int
			var hex string
			if e = rows.Scan(&id, &v, &hex); e != nil {
				break
			}
			count++
			expected := fmt.Sprintf("%X", []byte(strings.Repeat(fmt.Sprintf("%08x", id), 512)))
			if id != count || v != id*17 || hex != expected {
				e = fmt.Errorf("recovery data mismatch id%d v%d", id, v)
				break
			}
		}
		e = errors.Join(e, rows.Err(), rows.Close())
		if e == nil && count != 512 {
			e = fmt.Errorf("recovery rows=%d", count)
		}
		if e == nil {
			_, e = db.ExecContext(ctx, "UPDATE recoveryprobe SET v=999 WHERE id=1")
		}
		e = errors.Join(e, db.Close(), c.Close())
		if e != nil {
			return e
		}
		r.VerifiedForks++
		fmt.Println("PASS actual_redo_recovery_exact_isolated_fork", k)
	}
	return nil
}
func main() {
	out := flag.String("out", "", "")
	crash := flag.Bool("crash", true, "")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 180*time.Second)
	defer cancel()
	r := report{Crash: *crash, Mode: os.Getenv("MARIAMEM_BP_ZERO_MODE_INTERNAL"), Fixture: "test-only host overlay captures fast_shutdown=2 filesystem; normal Snapshot remains fast_shutdown=1"}
	e := run(ctx, &r)
	r.Success = e == nil
	if e != nil {
		r.Error = e.Error()
	}
	b, _ := json.MarshalIndent(r, "", "  ")
	if *out != "" {
		os.WriteFile(*out, b, 0600)
	}
	fmt.Println(string(b))
	if e != nil {
		os.Exit(1)
	}
}
