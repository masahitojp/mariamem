package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime/pprof"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
	maria "github.com/masahitojp/mariamem"
	"github.com/shibukawa/pgmem/bench/modelcase/store"
)

var arm = flag.String("arm", "", "A, B or C")
var duration = flag.Duration("duration", 0, "measurement duration after setup; zero runs one batch")
var profile = flag.String("profile", "", "CPU profile path")
var rowsOut = json.NewEncoder(os.Stdout)
var ctx = context.Background()

func must(err error) {
	if err != nil {
		panic(err)
	}
}
func check(ok bool, details ...any) {
	if !ok {
		panic(fmt.Sprint(details...))
	}
}
func openDB(s *maria.Database) *sql.DB {
	cfg, err := mysql.ParseDSN(s.DSN())
	must(err)
	check(cfg.InterpolateParams, "expected text interpolation outside target")
	cfg.MultiStatements = true
	cfg.ClientFoundRows = true
	cfg.DialFunc = s.DialContext
	c, err := mysql.NewConnector(cfg)
	must(err)
	return sql.OpenDB(c)
}
func count(db *sql.DB, query string) int {
	var n int
	must(db.QueryRow(query).Scan(&n))
	return n
}
func reference() map[string]string {
	sum := "(SELECT COALESCE(SUM(quantity*unit_price_cents),0) FROM order_items WHERE order_id=NEW.order_id)"
	update := "UPDATE orders SET total_cents=" + sum + ",updated_at=CURRENT_TIMESTAMP(6) WHERE id=NEW.order_id"
	want := map[string]string{
		"order_items_total_update": update,
		"order_items_total_delete": strings.ReplaceAll(update, "NEW.", "OLD."),
		"orders_audit_insert":      "INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,NULL,NEW.status)",
		"orders_audit_update":      "BEGIN IF NOT(NEW.status <=> OLD.status) THEN INSERT INTO audit_log(order_id,old_status,new_status) VALUES(NEW.id,OLD.status,NEW.status); END IF; END",
	}
	switch *arm {
	case "A":
		want["order_items_total_insert"] = update
	case "B":
		want["order_items_total_insert"] = strings.Replace(update, sum, "total_cents+NEW.quantity*NEW.unit_price_cents", 1)
	case "C":
	default:
		panic("invalid arm")
	}
	return want
}
func normalized(s string) string { return strings.ToLower(strings.Join(strings.Fields(s), "")) }
func triggers(db *sql.DB, want map[string]string) map[string]string {
	rows, err := db.Query("SELECT TRIGGER_NAME,ACTION_STATEMENT FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA=DATABASE() ORDER BY TRIGGER_NAME")
	must(err)
	got := map[string]string{}
	for rows.Next() {
		var name, body string
		must(rows.Scan(&name, &body))
		exp, ok := want[name]
		check(ok && normalized(body) == normalized(exp), "trigger ", name, " body ", body, " expected ", exp)
		got[name] = body
	}
	must(rows.Err())
	must(rows.Close())
	check(len(got) == len(want), "trigger count ", len(got))
	return got
}
func constraint(db *sql.DB, q string, code uint16) {
	_, err := db.Exec(q)
	var e *mysql.MySQLError
	check(errors.As(err, &e) && e.Number == code, "expected SQL error ", code, " got ", err)
}
func baseline(orders []store.SampleOrder) *maria.Snapshot {
	srv, err := maria.Start(ctx, maria.Options{})
	must(err)
	defer func() { must(srv.Close()) }()
	db := openDB(srv)
	must(store.Migrate(ctx, db))
	must(store.SeedMaster(ctx, db))
	if *arm == "C" {
		_, err := db.Exec("DROP TRIGGER order_items_total_insert")
		must(err)
	}
	tx, err := db.Begin()
	must(err)
	for _, o := range orders {
		var id int64
		must(tx.QueryRow("INSERT INTO orders(user_id,status) VALUES (?,?) RETURNING id", o.UserID, o.Status).Scan(&id))
		check(id == o.ID, "unexpected parent ", id)
	}
	must(tx.Commit())
	must(db.Close())
	must(srv.WaitDisconnected(ctx))
	snap, err := srv.Snapshot(ctx, maria.SnapshotOptions{})
	must(err)
	return snap
}
func batch(snap *maria.Snapshot, orders []store.SampleOrder, n int, want map[string]string) time.Duration {
	srv, err := snap.Fork(ctx)
	must(err)
	defer func() { must(srv.Close()) }()
	db := openDB(srv)
	defer func() { must(db.Close()) }()
	bodies := triggers(db, want)
	if n == 0 {
		must(rowsOut.Encode(map[string]any{"arm": *arm, "registered": bodies}))
	}
	check(count(db, "SELECT count(*) FROM orders WHERE total_cents=0") == 40 && count(db, "SELECT count(*) FROM order_items") == 0, "fork baseline")
	tx, err := db.Begin()
	must(err)
	st, err := tx.Prepare("INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES (?,?,?,?)")
	must(err)
	start := time.Now()
	for _, o := range orders {
		for _, it := range o.Items {
			_, err = st.Exec(o.ID, it.ProductID, it.Quantity, it.UnitPriceCents)
			must(err)
		}
	}
	elapsed := time.Since(start)
	must(st.Close())
	must(tx.Commit())
	check(count(db, "SELECT count(*) FROM orders") == 40 && count(db, "SELECT count(*) FROM order_items") == 100 && count(db, "SELECT count(*) FROM audit_log") == 40, "row counts")
	check(count(db, "SELECT count(*) FROM products WHERE stock=100") == 500 && count(db, "SELECT count(*) FROM products") == 500, "stock")
	rows, err := db.Query("SELECT o.id,o.total_cents,COUNT(i.id),SUM(i.quantity*i.unit_price_cents) FROM orders o JOIN order_items i ON o.id=i.order_id GROUP BY o.id,o.total_cents ORDER BY o.id")
	must(err)
	i := 0
	for rows.Next() {
		var id, total, items, sum int64
		must(rows.Scan(&id, &total, &items, &sum))
		o := orders[i]
		i++
		var expected int64
		for _, it := range o.Items {
			expected += int64(it.Quantity) * it.UnitPriceCents
		}
		check(id == o.ID && int64(len(o.Items)) == items && sum == expected, "item contents at order ", id)
		if *arm == "C" {
			expected = 0
		}
		check(total == expected, "order ", id, " total ", total, " expected ", expected)
	}
	must(rows.Err())
	must(rows.Close())
	check(i == 40, "order count")
	constraint(db, "INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(999999,1,1,100)", 1452)
	constraint(db, "INSERT INTO order_items(order_id,product_id,quantity,unit_price_cents) VALUES(1,1,0,100)", 4025)
	return elapsed
}
func run() {
	want := reference()
	must(os.Setenv("MARIA_AUDIT_OF", "1"))
	must(os.Setenv("MODELCASE_MATCHED", "1"))
	mode := "sum"
	if *arm == "B" {
		mode = "incremental"
	}
	must(os.Setenv("SUM_EXPERIMENT", mode))
	orders := store.SampleOrders()
	if *profile != "" {
		f, err := os.Create(*profile)
		must(err)
		must(pprof.StartCPUProfile(f))
		defer func() { pprof.StopCPUProfile(); must(f.Close()) }()
	}
	snap := baseline(orders)
	defer func() { must(snap.Close()) }()
	deadline := time.Now().Add(*duration)
	for i := 0; ; i++ {
		elapsed := batch(snap, orders, i, want)
		must(rowsOut.Encode(map[string]any{"db": i, "raw_ns": elapsed.Nanoseconds(), "inserts": 100, "close": "pass"}))
		if time.Now().After(deadline) {
			break
		}
	}
}
func main() { flag.Parse(); run() }
