package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"github.com/masahitojp/mariamem/internal/generatedgo/code/base"
	"os"
	"runtime"
	"strings"
	"time"
)

type Sample struct {
	Kind   string
	Index  int
	API_NS int64
	Rows   []base.LexerRow
}
type Report struct {
	Mode            string
	Samples         []Sample
	Success         bool
	Error           string
	Cleanup         map[string]uint64
	TimerNS         int64
	TimerIterations int
}

func check(e error) {
	if e != nil {
		panic(e)
	}
}
func connect(d *mariamem.Database) *sql.DB {
	cfg, e := mysql.ParseDSN(d.DSN())
	check(e)
	cfg.DialFunc = d.DialContext
	c, e := mysql.NewConnector(cfg)
	check(e)
	return sql.OpenDB(c)
}
func retire(ctx context.Context, d *mariamem.Database, db *sql.DB) {
	check(db.Close())
	check(d.WaitDisconnected(ctx))
}
func oracle(db *sql.DB, sum int) {
	var n, total int
	check(db.QueryRow("SELECT COUNT(*), SUM(v) FROM lexer_seed").Scan(&n, &total))
	if n != 1000 || total != sum {
		panic(fmt.Sprintf("pristine oracle: %d %d", n, total))
	}
	var text string
	var calc int
	check(db.QueryRow("SELECT '日本語', 1 + 2 /* lexer smoke */").Scan(&text, &calc))
	if text != "日本語" || calc != 3 {
		panic("lexer smoke mismatch")
	}
}
func main() {
	mode := flag.String("mode", "off", "off/timed/inventory")
	out := flag.String("out", "", "result")
	flag.Parse()
	switch *mode {
	case "off":
		base.LexerMode = 0
	case "timed":
		base.LexerMode = 1
	case "inventory":
		base.LexerMode = 2
	default:
		panic("unknown mode")
	}
	if runtime.GOMAXPROCS(0) != 8 {
		panic("GOMAXPROCS")
	}
	r := Report{Mode: *mode}
	defer func() {
		if e := recover(); e != nil {
			r.Error = fmt.Sprint(e)
		}
		r.Cleanup = base.MemoryMappingStats()
		data, e := json.MarshalIndent(r, "", "  ")
		check(e)
		check(os.WriteFile(*out, append(data, '\n'), 0600))
		if !r.Success {
			os.Exit(1)
		}
	}()
	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Second)
	defer cancel()
	var timer int64
	for i := 0; i < 100000; i++ {
		t := base.LexerNow()
		timer += base.LexerElapsed(t)
	}
	r.TimerNS = timer
	r.TimerIterations = 100000
	t := time.Now()
	d, e := mariamem.Start(ctx, mariamem.Options{})
	check(e)
	r.Samples = append(r.Samples, Sample{"fresh", 0, time.Since(t).Nanoseconds(), base.LexerDrain()})
	db := connect(d)
	_, e = db.Exec("CREATE TABLE lexer_seed(id INT PRIMARY KEY, v INT NOT NULL)")
	check(e)
	rows := make([]string, 1000)
	for i := 1; i <= 1000; i++ {
		rows[i-1] = fmt.Sprintf("(%d,%d)", i, i)
	}
	_, e = db.Exec("INSERT INTO lexer_seed VALUES " + strings.Join(rows, ","))
	check(e)
	oracle(db, 500500)
	retire(ctx, d, db)
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	check(e)
	if s.MaxForks() != 1 {
		panic("cap")
	}
	for i := 0; i < 4; i++ {
		t = time.Now()
		c, e := s.Fork(ctx)
		check(e)
		r.Samples = append(r.Samples, Sample{"fork", i, time.Since(t).Nanoseconds(), base.LexerDrain()})
		db = connect(c)
		oracle(db, 500500)
		_, e = db.Exec("UPDATE lexer_seed SET v=v+10 WHERE id=1")
		check(e)
		oracle(db, 500510)
		retire(ctx, c, db)
		check(c.Close())
		if len(base.LexerDrain()) != 0 {
			panic("unexpected SQL-time map generation")
		}
	}
	check(s.Close())
	check(d.Close())
	for _, k := range []string{"active_mappings", "active_rw_bytes", "active_reserved_bytes", "release_failures"} {
		if base.MemoryMappingStats()[k] != 0 {
			panic("cleanup " + k)
		}
	}
	for _, x := range r.Samples {
		if (*mode == "off") != (len(x.Rows) == 0) {
			panic("observer coverage")
		}
		for _, row := range x.Rows {
			if row.Result != 0 || row.Exception != 0 {
				panic("map failure")
			}
		}
	}
	r.Success = true
}
