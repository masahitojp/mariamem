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
	"github.com/masahitojp/mariamem/internal/generatedgo"
	"os"
	"strings"
	"time"
)

type observation struct {
	Path           string `json:"path"`
	Hits           int64  `json:"hits"`
	Error          string `json:"error,omitempty"`
	Outcome        string `json:"outcome"`
	PoisonWitness  bool   `json:"poison_witness"`
	HealthySibling bool   `json:"healthy_sibling"`
}
type report struct {
	Success bool          `json:"success"`
	Error   string        `json:"error,omitempty"`
	Cases   []observation `json:"cases"`
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
func sum(ctx context.Context, d *mariamem.Database) (n int64, err error) {
	b, e := open(d)
	if e != nil {
		return 0, e
	}
	defer func() { err = errors.Join(err, b.Close()) }()
	err = b.QueryRowContext(ctx, "SELECT SUM(OCTET_LENGTH(payload)) FROM faultprobe").Scan(&n)
	return
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
	b, e := open(d)
	if e != nil {
		return e
	}
	if _, e = b.ExecContext(ctx, "CREATE TABLE faultprobe(id INT PRIMARY KEY,payload BLOB NOT NULL) ENGINE=InnoDB"); e != nil {
		b.Close()
		return e
	}
	tx, e := b.BeginTx(ctx, nil)
	if e != nil {
		b.Close()
		return e
	}
	st, e := tx.PrepareContext(ctx, "INSERT INTO faultprobe VALUES(?,?)")
	if e != nil {
		tx.Rollback()
		b.Close()
		return e
	}
	for i := 1; i <= 512; i++ {
		if _, e = st.ExecContext(ctx, i, []byte(strings.Repeat("test", 1024))); e != nil {
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
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if e != nil {
		return e
	}
	owned = false
	defer func() { generatedgo.SetBufferFault(""); err = errors.Join(err, s.Close()) }()
	for _, path := range []string{"/faultprobe.ibd", "/ibdata1"} {
		o := observation{Path: path}
		if path == "/ibdata1" {
			generatedgo.SetBufferFault(path)
		}
		c, e := s.Fork(ctx)
		if e != nil {
			o.Hits = generatedgo.BufferFaultHits()
			o.Error = e.Error()
			o.Outcome = "startup_error"
		} else {
			o.PoisonWitness = strings.Contains(c.Logs(), "BP_ZERO_WITNESS pool=16777216 descriptor=233856 frames=1008 page=16384 aligned=1")
			if os.Getenv("MARIAMEM_BP_ZERO_MODE_INTERNAL") == "poison" && !o.PoisonWitness {
				c.Close()
				return fmt.Errorf("missing poison witness")
			}
			if path != "/ibdata1" {
				generatedgo.SetBufferFault(path)
			}
			n, qerr := sum(ctx, c)
			o.Hits = generatedgo.BufferFaultHits()
			if qerr != nil {
				o.Error = qerr.Error()
				o.Outcome = "query_error"
			} else if n == 512*4096 {
				o.Outcome = "recovered_correct"
			} else {
				c.Close()
				return fmt.Errorf("wrong result under fault %d", n)
			}
			if e = c.Close(); e != nil {
				return fmt.Errorf("fault child close: %w", e)
			}
		}
		generatedgo.SetBufferFault("")
		if o.Hits != 1 {
			return fmt.Errorf("fault path not exercised %s hits%d", path, o.Hits)
		}
		healthy, e := s.Fork(ctx)
		if e != nil {
			return e
		}
		n, e := sum(ctx, healthy)
		e = errors.Join(e, healthy.Close())
		if e != nil {
			return e
		}
		if n != 512*4096 {
			return fmt.Errorf("healthy sibling data %d", n)
		}
		o.HealthySibling = true
		r.Cases = append(r.Cases, o)
		fmt.Printf("PASS fault %s %s healthy_sibling\n", path, o.Outcome)
	}
	return nil
}
func main() {
	out := flag.String("out", "", "")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	r := report{}
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
