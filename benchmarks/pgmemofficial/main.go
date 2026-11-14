// Adapted measurement method from shibukawa/pgmem bench/alternatives,
// source a61005d37d01e6671f814fe8ca828222e8147df4. Not a cross-engine comparison.
package main

import (
	"context"
	"crypto/md5"
	"database/sql"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"runtime/debug"
	"strconv"
	"strings"
	"time"

	mysql "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

var sourceCommit, harnessCommit string

func must(e error) {
	if e != nil {
		panic(e)
	}
}
func require(ok bool, why string) {
	if !ok {
		panic(why)
	}
}
func ms(t time.Time) float64 { return float64(time.Since(t)) / float64(time.Millisecond) }
func rss() int {
	b, e := exec.Command("ps", "-o", "rss=", "-p", strconv.Itoa(os.Getpid())).Output()
	must(e)
	n, e := strconv.Atoi(strings.TrimSpace(string(b)))
	must(e)
	return n
}
func pool(db *mariamem.Database, pipe bool) *sql.DB {
	cfg, e := mysql.ParseDSN(db.DSN())
	must(e)
	cfg.InterpolateParams = false
	cfg.MultiStatements = true
	if pipe {
		cfg.DialFunc = db.DialContext
	}
	c, e := mysql.NewConnector(cfg)
	must(e)
	p := sql.OpenDB(c)
	p.SetMaxOpenConns(1)
	p.SetMaxIdleConns(1)
	return p
}
func scalar(ctx context.Context, p *sql.DB, q string, want int64) {
	var n int64
	must(p.QueryRowContext(ctx, q).Scan(&n))
	require(n == want, fmt.Sprintf("%s: got %d want %d", q, n, want))
}

const digits = "(SELECT 0 d UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3 UNION ALL SELECT 4 UNION ALL SELECT 5 UNION ALL SELECT 6 UNION ALL SELECT 7 UNION ALL SELECT 8 UNION ALL SELECT 9)"

// Exact 1..10^width, with one optional 0/1 digit yielding 200000 rows.
func series(width int, two bool) string {
	terms := []string{"1"}
	from := []string{}
	factor := 1
	for i := 0; i < width; i++ {
		a := fmt.Sprintf("d%d", i)
		terms = append(terms, fmt.Sprintf("%d*%s.d", factor, a))
		from = append(from, digits+" "+a)
		factor *= 10
	}
	if two {
		terms = append(terms, fmt.Sprintf("%d*last.d", factor))
		from = append(from, "(SELECT 0 d UNION ALL SELECT 1) last")
	}
	return "(SELECT " + strings.Join(terms, "+") + " n FROM " + strings.Join(from, " CROSS JOIN ") + ") numbers"
}
func simple(ctx context.Context, p *sql.DB, n, warm int) float64 {
	st, e := p.PrepareContext(ctx, "SELECT v FROM bench WHERE id = ?")
	must(e)
	defer st.Close()
	expected := func(i int) {
		id := i%1000 + 1
		var v string
		must(st.QueryRowContext(ctx, id).Scan(&v))
		require(v == fmt.Sprintf("%x", md5.Sum([]byte(strconv.Itoa(id)))), "indexed SELECT value mismatch")
	}
	for i := 0; i < warm; i++ {
		expected(i)
	}
	// Same timed execute+scan loop as upstream; expected md5 checks are untimed below.
	t := time.Now()
	for i := 0; i < n; i++ {
		var v string
		must(st.QueryRowContext(ctx, i%1000+1).Scan(&v))
		require(len(v) == 32, "indexed value width")
	}
	elapsed := float64(time.Since(t).Microseconds()) / float64(n)
	expected(0)
	expected(999)
	return elapsed
}
func insertion(ctx context.Context, p *sql.DB, kind string, n int) map[string]any {
	table := "writes_" + kind
	_, e := p.ExecContext(ctx, "CREATE TABLE "+table+"(id INT PRIMARY KEY,v VARCHAR(32) NOT NULL) ENGINE=InnoDB")
	must(e)
	// Initialize one row/page outside the measured window, then remove the row.
	_, e = p.ExecContext(ctx, "INSERT INTO "+table+" VALUES(0,'warmup')")
	must(e)
	_, e = p.ExecContext(ctx, "DELETE FROM "+table+" WHERE id=0")
	must(e)
	var elapsed float64
	if kind == "text" {
		queries := make([]string, n)
		for i := range queries {
			queries[i] = fmt.Sprintf("INSERT INTO %s VALUES(%d,'value')", table, i+1)
		}
		t := time.Now()
		for _, q := range queries {
			res, e := p.ExecContext(ctx, q)
			must(e)
			count, e := res.RowsAffected()
			must(e)
			require(count == 1, "text affected")
		}
		elapsed = ms(t)
	} else {
		st, e := p.PrepareContext(ctx, "INSERT INTO "+table+" VALUES(?,?)")
		must(e)
		if kind == "transaction" {
			t := time.Now()
			tx, e := p.BeginTx(ctx, nil)
			must(e)
			inside := tx.StmtContext(ctx, st)
			for i := 1; i <= n; i++ {
				res, e := inside.ExecContext(ctx, i, "value")
				must(e)
				count, e := res.RowsAffected()
				must(e)
				require(count == 1, "transaction affected")
			}
			must(inside.Close())
			must(tx.Commit())
			elapsed = ms(t)
		} else {
			t := time.Now()
			for i := 1; i <= n; i++ {
				res, e := st.ExecContext(ctx, i, "value")
				must(e)
				count, e := res.RowsAffected()
				must(e)
				require(count == 1, "prepared affected")
			}
			elapsed = ms(t)
		}
		must(st.Close())
	}
	scalar(ctx, p, "SELECT COUNT(*) FROM "+table, int64(n))
	scalar(ctx, p, "SELECT SUM(id) FROM "+table, int64(n*(n+1)/2))
	scalar(ctx, p, "SELECT SUM(CHAR_LENGTH(v)) FROM "+table, int64(5*n))
	return map[string]any{"rows": n, "total_ms": elapsed, "us_per_row": elapsed * 1000 / float64(n), "verified": true}
}
func measure(output string, simpleN, warm, heavyN, forks, insertN int) (err error) {
	r := map[string]any{"source_commit": sourceCommit, "harness_source_commit": harnessCommit, "go": runtime.Version(), "platform": runtime.GOOS + "/" + runtime.GOARCH, "completed": false, "settings": map[string]int{"simple": simpleN, "simple_warmup": warm, "heavy": heavyN, "heavy_warmup": 1, "isolate": forks, "insert_per_mode": insertN, "heavy_rows": 200000}}
	var cleanupErrors []string
	defer func() {
		if p := recover(); p != nil {
			err = fmt.Errorf("%v", p)
		}
		if len(cleanupErrors) > 0 {
			r["cleanup_errors"] = cleanupErrors
			if err == nil {
				err = fmt.Errorf("resource cleanup failed")
			}
		}
		if err != nil {
			r["error"] = err.Error()
		} else {
			r["completed"] = true
		}
		b, e := json.MarshalIndent(r, "", "  ")
		if e == nil {
			e = os.WriteFile(output, append(b, '\n'), 0600)
		}
		if err == nil {
			err = e
		}
	}()
	closeDB := func(d *mariamem.Database) {
		if e := d.Close(); e != nil {
			cleanupErrors = append(cleanupErrors, e.Error())
		}
	}
	info, _ := debug.ReadBuildInfo()
	r["build_info"] = info
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()
	r["rss_before_kib"] = rss()
	t := time.Now()
	db, e := mariamem.Start(ctx, mariamem.Options{})
	must(e)
	defer closeDB(db)
	p := pool(db, false)
	defer p.Close()
	scalar(ctx, p, "SELECT 1", 1)
	r["startup_ms"] = ms(t)
	var version string
	must(p.QueryRowContext(ctx, "SELECT VERSION()").Scan(&version))
	require(strings.HasPrefix(version, "12.3.3"), "unexpected engine")
	r["engine_version"] = version
	s1000 := series(3, false)
	s10000 := series(4, false)
	schema := "CREATE TABLE bench(id INT PRIMARY KEY,v TEXT NOT NULL) ENGINE=InnoDB;" +
		"INSERT INTO bench SELECT n,MD5(CAST(n AS CHAR)) FROM " + s1000 + ";" +
		"CREATE TABLE users(id BIGINT AUTO_INCREMENT PRIMARY KEY,name TEXT NOT NULL,email VARCHAR(255) UNIQUE) ENGINE=InnoDB;" +
		"CREATE TABLE orders(id BIGINT AUTO_INCREMENT PRIMARY KEY,user_id BIGINT NOT NULL,amount INT NOT NULL,created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(user_id) REFERENCES users(id)) ENGINE=InnoDB;" +
		"CREATE INDEX orders_user_id ON orders(user_id);" +
		"INSERT INTO users(name,email) SELECT CONCAT('user',n),CONCAT('user',n,'@example.com') FROM " + s1000 + ";" +
		"INSERT INTO orders(user_id,amount) SELECT 1+(n%1000),n%997 FROM " + s10000
	r["schema_sql"] = schema
	t = time.Now()
	_, e = p.ExecContext(ctx, schema)
	must(e)
	r["setup_ms"] = ms(t)
	scalar(ctx, p, "SELECT COUNT(*) FROM bench", 1000)
	scalar(ctx, p, "SELECT COUNT(*) FROM users", 1000)
	scalar(ctx, p, "SELECT COUNT(*) FROM orders", 10000)
	r["rss_idle_kib"] = rss()
	r["simple_query_us"] = simple(ctx, p, simpleN, warm)
	direct := pool(db, true)
	r["dial_query_us"] = simple(ctx, direct, simpleN, warm)
	must(direct.Close())
	heavySQL := "SELECT COUNT(*) FROM (SELECT MD5(CAST(n AS CHAR)) h FROM " + series(5, true) + " ORDER BY h LIMIT 200000) sorted"
	var plan string
	must(p.QueryRowContext(ctx, "EXPLAIN FORMAT=JSON "+heavySQL).Scan(&plan))
	require(strings.Contains(strings.ToLower(plan), "filesort"), "heavy query did not perform filesort")
	r["heavy_plan"] = json.RawMessage(plan)
	r["heavy_sql"] = heavySQL
	st, e := p.PrepareContext(ctx, heavySQL)
	must(e)
	var heavy []float64
	for i := 0; i <= heavyN; i++ {
		t = time.Now()
		var n int64
		must(st.QueryRowContext(ctx).Scan(&n))
		require(n == 200000, "heavy cardinality")
		if i > 0 {
			heavy = append(heavy, ms(t))
		}
	}
	must(st.Close())
	r["heavy_ms"] = heavy
	inserts := map[string]any{}
	for _, kind := range []string{"text", "prepared", "transaction"} {
		inserts[kind] = insertion(ctx, p, kind, insertN)
	}
	r["insert"] = inserts
	must(p.Close())
	must(db.WaitDisconnected(ctx))
	t = time.Now()
	snap, e := db.Snapshot(ctx, mariamem.SnapshotOptions{})
	must(e)
	r["snapshot_ms"] = ms(t)
	defer func() {
		if e := snap.Close(); e != nil {
			cleanupErrors = append(cleanupErrors, e.Error())
		}
	}()
	var iso, firstQuery, closeTimes []float64
	for i := 0; i < forks; i++ {
		t = time.Now()
		child, e := snap.Fork(ctx)
		must(e)
		cp := pool(child, false)
		scalar(ctx, cp, "SELECT COUNT(*) FROM orders JOIN users ON users.id=orders.user_id", 10000)
		firstQuery = append(firstQuery, ms(t))
		must(cp.Close())
		must(child.WaitDisconnected(ctx))
		c := time.Now()
		must(child.Close())
		closeTimes = append(closeTimes, ms(c))
		iso = append(iso, ms(t))
	}
	r["isolate_ms"] = iso
	r["fork_first_query_ms"] = firstQuery
	r["fork_close_ms"] = closeTimes
	r["rss_after_kib"] = rss()
	return nil
}
func main() {
	out := flag.String("output", "", "JSON output")
	n := flag.Int("simple", 3000, "indexed queries")
	warm := flag.Int("warm", 300, "indexed warmup")
	h := flag.Int("heavy", 3, "heavy repeats after warmup")
	f := flag.Int("forks", 20, "serial isolation cycles including Close")
	ins := flag.Int("insert", 1000, "single inserts per mode")
	flag.Parse()
	if *out == "" {
		panic("output required")
	}
	if e := measure(*out, *n, *warm, *h, *f, *ins); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
