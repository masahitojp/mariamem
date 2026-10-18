package main

import (
	"context"
	"database/sql"
	"encoding/binary"
	"encoding/hex"
	"encoding/json"
	"flag"
	"fmt"
	"github.com/go-sql-driver/mysql"
	mariamem "github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/guest"
	"os"
	"strings"
	"time"
)

type record struct {
	Case   string `json:"case"`
	Result string `json:"result"`
	Detail any    `json:"detail,omitempty"`
}

var records []record

func check(e error) {
	if e != nil {
		panic(e)
	}
}
func expect(b bool, s string) {
	if !b {
		panic(s)
	}
}
func stage(name string, fn func() any) {
	defer func() {
		if p := recover(); p != nil {
			records = append(records, record{name, "FAIL", fmt.Sprint(p)})
		}
	}()
	d := fn()
	records = append(records, record{name, "PASS", d})
}
func u32(n uint32) []byte { b := make([]byte, 4); binary.LittleEndian.PutUint32(b, n); return b }
func main() {
	out := flag.String("output", "", "json output")
	ref := flag.String("dsn", "", "native reference DSN (skip direct guest)")
	flag.Parse()
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()
	if *ref == "" {
		stage("embedded-api-direct", func() any {
			p, e := guest.StartGenerated(ctx, "", nil, os.Stderr)
			check(e)
			defer func() { check(p.Shutdown(ctx)) }()
			call := func(op byte, slot uint32, b []byte) guest.Result {
				r, e := p.Call(ctx, op, slot, b)
				check(e)
				return r
			}
			expect(call(1, 0, nil).OK, "open0")
			expect(call(1, 1, nil).OK, "open1")
			r := call(4, 0, append([]byte{22}, []byte("SELECT ?, ?, ?")...))
			expect(r.OK && r.ParamCount == 3 && r.StmtID != 0 && r.ParamMetadataNull, fmt.Sprintf("prepare %+v", r))
			meta := r
			invalid := call(4, 0, []byte{23})
			expect(!invalid.OK && invalid.Errno == 1235, "short command boundary")
			cursor := append([]byte{23}, u32(meta.StmtID)...)
			cursor = append(cursor, 1, 1, 0, 0, 0)
			unsupported := call(4, 0, cursor)
			expect(!unsupported.OK && unsupported.Errno == 1235, "cursor boundary")
			exec := append([]byte{23}, u32(r.StmtID)...)
			exec = append(exec, 0, 1, 0, 0, 0, 4, 1, 8, 0, 253, 0, 6, 0)
			var number [8]byte
			binary.LittleEndian.PutUint64(number[:], ^uint64(76))
			exec = append(exec, number[:]...)
			exec = append(exec, 5)
			exec = append(exec, []byte("hello")...)
			got := call(4, 0, exec)
			expect(got.OK && len(got.Rows) == 1 && len(got.Rows[0]) == 3, fmt.Sprintf("execute %+v", got))
			a, e := hex.DecodeString(got.Rows[0][0].Hex)
			check(e)
			b, e := hex.DecodeString(got.Rows[0][1].Hex)
			check(e)
			expect(string(a) == "-77" && string(b) == "hello" && got.Rows[0][2] == nil, fmt.Sprintf("values %+v", got))
			foreign := call(4, 1, exec)
			expect(!foreign.OK && foreign.Errno == 1243, "foreign handle")
			expect(call(4, 0, append([]byte{26}, u32(meta.StmtID)...)).OK, "reset")
			again := call(4, 0, exec)
			expect(again.OK, "repeat")
			expect(call(4, 0, append([]byte{25}, u32(meta.StmtID)...)).OK, "close")
			stale := call(4, 0, exec)
			expect(!stale.OK && stale.Errno == 1243, "stale handle")
			syntax := call(4, 0, append([]byte{22}, []byte("SELEC broken ?")...))
			expect(!syntax.OK && syntax.Errno == 1064, "prepare syntax")
			expect(call(3, 1, nil).Closed, "close1")
			expect(call(3, 0, nil).Closed, "close0")
			expect(call(1, 0, nil).OK, "reopen")
			old := call(4, 0, exec)
			expect(!old.OK && old.Errno == 1243, "slot reuse handle")
			expect(call(3, 0, nil).Closed, "reclose")
			return map[string]any{"prepare": meta, "execute": got, "syntax_errno": syntax.Errno, "foreign_errno": foreign.Errno, "stale_errno": old.Errno}
		})
	}
	stage("go-explicit-implicit-and-lifecycle", func() any {
		dsn := *ref
		if dsn == "" {
			db, e := mariamem.Start(ctx, mariamem.Options{})
			check(e)
			defer func() { check(db.Close()) }()
			dsn = db.DSN()
		}
		cfg, e := mysql.ParseDSN(dsn)
		check(e)
		cfg.InterpolateParams = false
		c, e := sql.Open("mysql", cfg.FormatDSN())
		check(e)
		defer c.Close()
		c.SetMaxOpenConns(3)
		s, e := c.PrepareContext(ctx, "SELECT ?, ?, ?")
		check(e)
		var n int64
		var word string
		var empty any
		check(s.QueryRowContext(ctx, int64(-77), "hello", nil).Scan(&n, &word, &empty))
		expect(n == -77 && word == "hello" && empty == nil, "explicit values")
		check(s.QueryRowContext(ctx, int64(91), "again", nil).Scan(&n, &word, &empty))
		expect(n == 91 && word == "again" && empty == nil, "repeat values")
		check(s.Close())
		_, e = c.ExecContext(ctx, "CREATE TABLE IF NOT EXISTS go_prepared(id BIGINT PRIMARY KEY, value VARBINARY(100)) ENGINE=InnoDB")
		check(e)
		_, e = c.ExecContext(ctx, "DELETE FROM go_prepared")
		check(e)
		tx, e := c.BeginTx(ctx, nil)
		check(e)
		ts, e := tx.PrepareContext(ctx, "INSERT INTO go_prepared VALUES(?, ?)")
		check(e)
		_, e = ts.ExecContext(ctx, 1, []byte{'a', 0, 'b'})
		check(e)
		check(ts.Close())
		check(tx.Rollback())
		var count int
		check(c.QueryRowContext(ctx, "SELECT COUNT(*) FROM go_prepared").Scan(&count))
		expect(count == 0, "rollback")
		_, e = c.ExecContext(ctx, "INSERT INTO go_prepared VALUES(?, ?)", 2, []byte("committed"))
		check(e)
		var value []byte
		check(c.QueryRowContext(ctx, "SELECT value FROM go_prepared WHERE id=?", 2).Scan(&value))
		expect(string(value) == "committed", "implicit prepare")
		conn, e := c.Conn(ctx)
		check(e)
		cs, e := conn.PrepareContext(ctx, "SELECT ?")
		check(e)
		check(cs.QueryRowContext(ctx, int64(42)).Scan(&n))
		expect(n == 42, "reserved conn")
		check(cs.Close())
		check(conn.Close())
		cfg.InterpolateParams = true
		c2, e := sql.Open("mysql", cfg.FormatDSN())
		check(e)
		defer c2.Close()
		es, e := c2.PrepareContext(ctx, "SELECT ?")
		check(e)
		check(es.QueryRowContext(ctx, 55).Scan(&n))
		expect(n == 55, "explicit with interpolation enabled")
		check(es.Close())
		return map[string]any{"driver": "v1.9.3", "explicit": true, "implicit": true, "DB_Tx_Conn": true, "interpolation_enabled_explicit": true}
	})
	b, e := json.MarshalIndent(records, "", "  ")
	check(e)
	check(os.WriteFile(*out, append(b, '\n'), 0644))
	fmt.Println(string(b))
	for _, r := range records {
		if strings.EqualFold(r.Result, "FAIL") {
			os.Exit(1)
		}
	}
}
