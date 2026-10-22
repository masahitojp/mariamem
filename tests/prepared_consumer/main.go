// Fixed-driver P5 consumer. Uses ordinary database/sql APIs against either engine.
package main

import (
	"context"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"time"

	mysql "github.com/go-sql-driver/mysql"
)

func counter(ctx context.Context, db *sql.DB, name string) (int, error) {
	var key string
	var n int
	e := db.QueryRowContext(ctx, "SHOW GLOBAL STATUS LIKE '"+name+"'").Scan(&key, &n)
	return n, e
}
func mode(ctx context.Context, interpolate bool) (out map[string]any, err error) {
	out = map[string]any{"interpolate_params": interpolate}
	cfg, e := mysql.ParseDSN(os.Getenv("MARIAMEM_P5_DSN"))
	if e != nil {
		return out, e
	}
	cfg.InterpolateParams = interpolate
	db, e := sql.Open("mysql", cfg.FormatDSN())
	if e != nil {
		return out, e
	}
	db.SetMaxOpenConns(1)
	defer func() { err = errors.Join(err, db.Close()); out["open_after"] = db.Stats().OpenConnections }()
	for _, q := range []string{"DROP TABLE IF EXISTS test.p5_consumer", "CREATE TABLE test.p5_consumer(id INT PRIMARY KEY,v VARBINARY(30)) ENGINE=InnoDB", "DROP PROCEDURE IF EXISTS test.p5_consumer_call", "CREATE PROCEDURE test.p5_consumer_call(IN x INT) BEGIN SELECT x; SELECT x+1; END"} {
		if _, e = db.ExecContext(ctx, q); e != nil {
			return out, e
		}
	}
	before, e := counter(ctx, db, "Com_stmt_prepare")
	if e != nil {
		return out, e
	}
	stmt, e := db.PrepareContext(ctx, "SELECT ?")
	if e != nil {
		return out, e
	}
	for _, v := range []any{nil, int64(-17), int64(9223372036854775807), "雪", []byte{'A', 0, 'B'}} {
		var got any
		if e = stmt.QueryRowContext(ctx, v).Scan(&got); e != nil {
			stmt.Close()
			return out, e
		}
		switch want := v.(type) {
		case nil:
			if got != nil {
				e = fmt.Errorf("NULL: %v", got)
			}
		case []byte:
			b, ok := got.([]byte)
			if !ok || hex.EncodeToString(b) != hex.EncodeToString(want) {
				e = fmt.Errorf("binary: %v", got)
			}
		default:
			if b, ok := got.([]byte); ok {
				got = string(b)
			}
			if fmt.Sprint(got) != fmt.Sprint(want) {
				e = fmt.Errorf("value: %v != %v", got, want)
			}
		}
		if e != nil {
			stmt.Close()
			return out, e
		}
	}
	if e = stmt.Close(); e != nil {
		return out, e
	}
	after, e := counter(ctx, db, "Com_stmt_prepare")
	if e != nil || after <= before {
		return out, fmt.Errorf("explicit prepare not observed: %d %d %v", before, after, e)
	}
	out["explicit_prepare_observed"] = true
	before, e = counter(ctx, db, "Com_stmt_prepare")
	if e != nil {
		return out, e
	}
	var implicit int
	if e = db.QueryRowContext(ctx, "SELECT ?", 23).Scan(&implicit); e != nil || implicit != 23 {
		return out, fmt.Errorf("parameterized Query: %d %v", implicit, e)
	}
	after, e = counter(ctx, db, "Com_stmt_prepare")
	if e != nil {
		return out, e
	}
	if !interpolate && after <= before {
		return out, errors.New("implicit prepare not observed")
	}
	out["parameterized_query_prepare_observed"] = after > before
	tx, e := db.BeginTx(ctx, nil)
	if e != nil {
		return out, e
	}
	if _, e = tx.ExecContext(ctx, "INSERT INTO test.p5_consumer VALUES(?,?)", 1, []byte{'A', 0, 'B'}); e != nil {
		tx.Rollback()
		return out, e
	}
	if e = tx.Rollback(); e != nil {
		return out, e
	}
	var n int
	if e = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM test.p5_consumer").Scan(&n); e != nil || n != 0 {
		return out, fmt.Errorf("rollback: %d %v", n, e)
	}
	tx, e = db.BeginTx(ctx, nil)
	if e != nil {
		return out, e
	}
	if _, e = tx.ExecContext(ctx, "INSERT INTO test.p5_consumer VALUES(?,?)", 1, []byte{'A', 0, 'B'}); e != nil {
		tx.Rollback()
		return out, e
	}
	if e = tx.Commit(); e != nil {
		return out, e
	}
	var b []byte
	if e = db.QueryRowContext(ctx, "SELECT v FROM test.p5_consumer WHERE id=?", 1).Scan(&b); e != nil || hex.EncodeToString(b) != "410042" {
		return out, fmt.Errorf("commit/binary: %x %v", b, e)
	}
	_, e = db.ExecContext(ctx, "INSERT INTO test.p5_consumer VALUES(?,?)", 1, []byte{})
	var me *mysql.MySQLError
	if !errors.As(e, &me) || me.Number != 1062 {
		return out, fmt.Errorf("duplicate: %v", e)
	}
	out["duplicate_errno"] = me.Number
	call, e := db.PrepareContext(ctx, "CALL test.p5_consumer_call(?)")
	if e != nil {
		return out, e
	}
	rows, e := call.QueryContext(ctx, 7)
	if e != nil {
		call.Close()
		return out, e
	}
	var sets [][]int
	for {
		var values []int
		for rows.Next() {
			var value int
			if e = rows.Scan(&value); e != nil {
				rows.Close()
				call.Close()
				return out, e
			}
			values = append(values, value)
		}
		if e = rows.Err(); e != nil {
			rows.Close()
			call.Close()
			return out, e
		}
		if len(values) > 0 {
			sets = append(sets, values)
		}
		if !rows.NextResultSet() {
			break
		}
	}
	e = errors.Join(rows.Err(), rows.Close(), call.Close())
	if e != nil {
		return out, e
	}
	if len(sets) != 2 || len(sets[0]) != 1 || sets[0][0] != 7 || len(sets[1]) != 1 || sets[1][0] != 8 {
		return out, fmt.Errorf("CALL results: %v", sets)
	}
	out["call_results"] = sets
	bad, e := db.PrepareContext(ctx, "SELEC invalid")
	if bad != nil {
		bad.Close()
	}
	if !errors.As(e, &me) || me.Number != 1064 {
		return out, fmt.Errorf("syntax: %v", e)
	}
	out["syntax_errno"] = me.Number
	if e = db.QueryRowContext(ctx, "SELECT 1").Scan(&n); e != nil || n != 1 {
		return out, fmt.Errorf("following query: %v", e)
	}
	n, e = counter(ctx, db, "Prepared_stmt_count")
	if e != nil || n != 0 {
		return out, fmt.Errorf("statement cleanup: %d %v", n, e)
	}
	out["prepared_after"] = n
	out["transaction_binary_values"] = true
	out["following_query"] = true
	out["result"] = "PASS"
	return out, nil
}
func main() {
	ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
	defer cancel()
	r := map[string]any{"scope": "P5 Go driver1.9.3 consumer", "result": "PASS"}
	var results []map[string]any
	for _, interpolate := range []bool{true, false} {
		m, e := mode(ctx, interpolate)
		if e != nil {
			m["result"] = "FAIL"
			m["error"] = e.Error()
			r["result"] = "FAIL"
		}
		results = append(results, m)
	}
	r["modes"] = results
	json.NewEncoder(os.Stdout).Encode(r)
	if r["result"] != "PASS" {
		os.Exit(1)
	}
}
