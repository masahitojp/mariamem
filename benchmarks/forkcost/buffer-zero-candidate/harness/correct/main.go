package main

import (
	"bytes"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"os"
	"strings"
	"time"
)

type result struct {
	Success                           bool     `json:"success"`
	Error                             string   `json:"error,omitempty"`
	Mode                              string   `json:"mode"`
	Case                              string   `json:"case"`
	Witnesses                         []string `json:"witnesses"`
	Checks                            []string `json:"checks"`
	ReadMissesBefore, ReadMissesAfter int64
	Started, Closed                   int
	ElapsedSeconds                    float64
}

var r result

func open(d *mariamem.Database) (*sql.DB, error) {
	cfg, e := mysql.ParseDSN(d.DSN())
	if e != nil {
		return nil, e
	}
	cfg.DialFunc = d.DialContext
	cfg.InterpolateParams = true
	cfg.MultiStatements = true
	c, e := mysql.NewConnector(cfg)
	if e != nil {
		return nil, e
	}
	db := sql.OpenDB(c)
	db.SetMaxOpenConns(1)
	return db, nil
}
func start(ctx context.Context) (*mariamem.Database, error) {
	d, e := mariamem.Start(ctx, mariamem.Options{})
	if e == nil {
		r.Started++
		if e = witness(d); e != nil {
			d.Close()
			return nil, e
		}
	}
	return d, e
}
func witness(d *mariamem.Database) error {
	if r.Mode != "poison" {
		return nil
	}
	for _, l := range strings.Split(d.Logs(), "\n") {
		if strings.Contains(l, "BP_ZERO_WITNESS ") {
			if !strings.Contains(l, "pool=16777216 descriptor=233856 frames=1008 page=16384 aligned=1") {
				return fmt.Errorf("bad witness %s", l)
			}
			r.Witnesses = append(r.Witnesses, l)
			return nil
		}
	}
	return fmt.Errorf("missing poison witness: %s", d.Logs())
}
func fork(ctx context.Context, s *mariamem.Snapshot) (*mariamem.Database, error) {
	d, e := s.Fork(ctx)
	if e == nil {
		r.Started++
		if e = witness(d); e != nil {
			d.Close()
			return nil, e
		}
	}
	return d, e
}
func closeDB(d *mariamem.Database) error {
	e := d.Close()
	if e == nil {
		r.Closed++
	}
	return e
}
func check(name string) { r.Checks = append(r.Checks, name); fmt.Println("PASS", name) }
func scalar(ctx context.Context, db *sql.DB, q string) (int64, error) {
	var n int64
	e := db.QueryRowContext(ctx, q).Scan(&n)
	return n, e
}
func payload(id, kind int) []byte {
	b := make([]byte, 4096)
	x := uint64(id)*0x9e3779b97f4a7c15 + uint64(kind) + 1
	for i := range b {
		x ^= x << 13
		x ^= x >> 7
		x ^= x << 17
		b[i] = byte(x)
	}
	return b
}
func seed(ctx context.Context, db *sql.DB, table string, kind, n int) error {
	format := " ROW_FORMAT=DYNAMIC"
	if kind == 2 {
		format = " ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8"
	}
	if _, e := db.ExecContext(ctx, "CREATE TABLE "+table+" (id INT PRIMARY KEY,payload MEDIUMBLOB NOT NULL,val INT NOT NULL DEFAULT 0) ENGINE=InnoDB"+format); e != nil {
		return e
	}
	tx, e := db.BeginTx(ctx, nil)
	if e != nil {
		return e
	}
	defer tx.Rollback()
	st, e := tx.PrepareContext(ctx, "INSERT INTO "+table+"(id,payload) VALUES(?,?)")
	if e != nil {
		return e
	}
	defer st.Close()
	for i := 1; i <= n; i++ {
		if _, e = st.ExecContext(ctx, i, payload(i, kind)); e != nil {
			return fmt.Errorf("seed %s/%d: %w", table, i, e)
		}
	}
	return tx.Commit()
}
func verify(ctx context.Context, db *sql.DB, table string, kind, n int, updated bool, descending bool) error {
	count := 0
	for batch := 0; batch < (n+255)/256; batch++ {
		lower := batch*256 + 1
		if descending {
			lower = ((n-1)/256-batch)*256 + 1
		}
		upper := lower + 255
		if upper > n {
			upper = n
		}
		order := "ASC"
		if descending {
			order = "DESC"
		}
		rows, e := db.QueryContext(ctx, fmt.Sprintf("SELECT id,payload,val FROM %s WHERE id BETWEEN %d AND %d ORDER BY id %s", table, lower, upper, order))
		if e != nil {
			return e
		}
		batchCount := 0
		for rows.Next() {
			var id, v int
			var b []byte
			if e = rows.Scan(&id, &b, &v); e != nil {
				rows.Close()
				return e
			}
			count++
			batchCount++
			want := 0
			if updated && id%7 == 0 {
				want = 1
			}
			if id < lower || id > upper || v != want || !bytes.Equal(b, payload(id, kind)) {
				rows.Close()
				return fmt.Errorf("data mismatch %s id=%d val=%d want=%d", table, id, v, want)
			}
		}
		e = errors.Join(rows.Err(), rows.Close())
		if e != nil {
			return e
		}
		if batchCount != upper-lower+1 {
			return fmt.Errorf("batch count %s %d..%d=%d", table, lower, upper, batchCount)
		}
	}
	if count != n {
		return fmt.Errorf("count %s=%d want%d", table, count, n)
	}
	return nil
}

func misses(ctx context.Context, db *sql.DB) (int64, error) {
	var key string
	var n int64
	e := db.QueryRowContext(ctx, "SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_reads'").Scan(&key, &n)
	return n, e
}
func resize(ctx context.Context, db *sql.DB, mib int) error {
	if _, e := db.ExecContext(ctx, fmt.Sprintf("SET GLOBAL innodb_buffer_pool_size=%d", mib<<20)); e != nil {
		return e
	}
	extent := 2 << 20
	page := 16384
	size := mib << 20
	pagesPer := 126
	want := (size / extent) * pagesPer
	rem := size % extent
	if rem > 0 {
		want += rem/page - 2
	}
	deadline := time.Now().Add(30 * time.Second)
	for {
		var key string
		var n int
		if e := db.QueryRowContext(ctx, "SHOW GLOBAL STATUS LIKE 'Innodb_buffer_pool_pages_total'").Scan(&key, &n); e != nil {
			return e
		}
		if n == want {
			break
		}
		if time.Now().After(deadline) {
			return fmt.Errorf("resize %dMiB pages=%d want=%d", mib, n, want)
		}
		time.Sleep(10 * time.Millisecond)
	}
	check(fmt.Sprintf("resize_%dMiB_pages_%d", mib, want))
	return nil
}
func basic(ctx context.Context) (err error) {
	d, e := start(ctx)
	if e != nil {
		return e
	}
	owned := true
	defer func() {
		if owned {
			err = errors.Join(err, closeDB(d))
		}
	}()
	db, e := open(d)
	if e != nil {
		return e
	}
	if _, e = db.ExecContext(ctx, "CREATE TABLE marker(id INT PRIMARY KEY,v INT NOT NULL) ENGINE=InnoDB; INSERT INTO marker VALUES(1,42)"); e != nil {
		db.Close()
		return e
	}
	if e = db.Close(); e != nil {
		return e
	}
	if e = d.WaitDisconnected(ctx); e != nil {
		return e
	}
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
	if e != nil {
		return e
	}
	owned = false
	r.Closed++
	defer func() { err = errors.Join(err, s.Close()) }()
	for i := 0; i < 4; i++ {
		c, e := fork(ctx, s)
		if e != nil {
			return e
		}
		b, e := open(c)
		if e != nil {
			closeDB(c)
			return e
		}
		func() {
			defer func() { err = errors.Join(err, b.Close(), closeDB(c)) }()
			n, e := scalar(ctx, b, "SELECT v FROM marker WHERE id=1")
			if e != nil {
				err = e
				return
			}
			if n != 42 {
				err = fmt.Errorf("isolation=%d", n)
				return
			}
			tx, e := b.BeginTx(ctx, nil)
			if e != nil {
				err = e
				return
			}
			if _, e = tx.ExecContext(ctx, "UPDATE marker SET v=999"); e != nil {
				tx.Rollback()
				err = e
				return
			}
			if e = tx.Rollback(); e != nil {
				err = e
				return
			}
			if n, e = scalar(ctx, b, "SELECT v FROM marker WHERE id=1"); e != nil || n != 42 {
				err = fmt.Errorf("rollback %d %v", n, e)
				return
			}
			if _, e = b.ExecContext(ctx, "UPDATE marker SET v=v+1"); e != nil {
				err = e
				return
			}
			if _, e = b.ExecContext(ctx, "SELECT * FROM missing_table_for_expected_error"); e == nil {
				err = fmt.Errorf("invalid SQL unexpectedly succeeded")
				return
			}
			if e = b.PingContext(ctx); e != nil {
				err = e
				return
			}
		}()
		if err != nil {
			return err
		}
		check(fmt.Sprintf("fork_%d_pristine_rollback_mutation_error_cleanup", i))
	}
	return nil
}
func large(ctx context.Context) (err error) {
	d, e := start(ctx)
	if e != nil {
		return e
	}
	owned := true
	defer func() {
		if owned {
			err = errors.Join(err, closeDB(d))
		}
	}()
	db, e := open(d)
	if e != nil {
		return e
	}
	dbOpen := true
	defer func() {
		if dbOpen {
			err = errors.Join(err, db.Close())
		}
	}()
	const n = 8192
	for kind, table := range []string{"bigpayload", "zip_payload"} {
		if e = seed(ctx, db, table, kind+1, n); e != nil {
			return e
		}
		check("seed_" + table + "_32MiB")
	}
	r.ReadMissesBefore, e = misses(ctx, db)
	if e != nil {
		return e
	}
	for kind, table := range []string{"bigpayload", "zip_payload"} {
		if e = verify(ctx, db, table, kind+1, n, false, false); e != nil {
			return e
		}
		if _, e = db.ExecContext(ctx, "UPDATE "+table+" SET val=val+1 WHERE MOD(id,7)=0"); e != nil {
			return e
		}
		if e = verify(ctx, db, table, kind+1, n, true, true); e != nil {
			return e
		}
	}
	r.ReadMissesAfter, e = misses(ctx, db)
	if e != nil {
		return e
	}
	if r.ReadMissesAfter <= r.ReadMissesBefore {
		return fmt.Errorf("no buffer read misses observed")
	}
	check("large_dynamic_and_compressed_data_exact_with_read_misses")
	for _, size := range []int{9, 11, 16} {
		if e = resize(ctx, db, size); e != nil {
			return e
		}
		for kind, table := range []string{"bigpayload", "zip_payload"} {
			if e = verify(ctx, db, table, kind+1, n, true, size == 11); e != nil {
				return e
			}
		}
	}
	if e = db.Close(); e != nil {
		return e
	}
	dbOpen = false
	if e = d.WaitDisconnected(ctx); e != nil {
		return e
	}
	s, e := d.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 1})
	if e != nil {
		return e
	}
	owned = false
	r.Closed++
	defer func() { err = errors.Join(err, s.Close()) }()
	for i := 0; i < 2; i++ {
		c, e := fork(ctx, s)
		if e != nil {
			return e
		}
		b, e := open(c)
		if e != nil {
			closeDB(c)
			return e
		}
		func() {
			defer func() { err = errors.Join(err, b.Close(), closeDB(c)) }()
			for kind, table := range []string{"bigpayload", "zip_payload"} {
				if e = verify(ctx, b, table, kind+1, n, true, i == 1); e != nil {
					err = e
					return
				}
			}
			if _, e = b.ExecContext(ctx, "UPDATE bigpayload SET val=99 WHERE id=1"); e != nil {
				err = e
			}
		}()
		if err != nil {
			return err
		}
		check(fmt.Sprintf("large_snapshot_restore_fork_%d_exact_and_isolated", i))
	}
	return nil
}
func main() {
	which := flag.String("case", "basic", "")
	out := flag.String("out", "", "")
	flag.Parse()
	r.Mode = os.Getenv("MARIAMEM_BP_ZERO_MODE_INTERNAL")
	r.Case = *which
	ctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
	defer cancel()
	at := time.Now()
	var e error
	if *which == "basic" {
		e = basic(ctx)
	} else if *which == "large" {
		e = large(ctx)
	} else {
		e = fmt.Errorf("unknown case")
	}
	r.ElapsedSeconds = time.Since(at).Seconds()
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
