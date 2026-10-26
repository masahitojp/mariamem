package main

import (
	"context"
	"database/sql"
	"encoding/json"
	_ "github.com/go-sql-driver/mysql"
	"html/template"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"
)

type order struct {
	SKU      string
	Quantity int
	Status   string
}

var page = template.Must(template.New("orders").Parse(`<!doctype html><html><body><h1>Orders</h1><a href="/orders">New order</a>{{if .Created}}<p>Order created</p>{{end}}<form method="post"><label>SKU<input name="sku"></label><label>Quantity<input name="quantity" value="1"></label><button type="submit">Save</button></form><ul>{{range .Orders}}<li data-testid="order">{{.SKU}}:{{.Quantity}}:{{.Status}}</li>{{end}}</ul></body></html>`))

func main() {
	db, err := sql.Open("mysql", os.Getenv("E2E_MYSQL_DSN"))
	if err != nil {
		log.Fatal(err)
	}
	defer db.Close()
	db.SetMaxOpenConns(2)
	db.SetMaxIdleConns(2)
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, r *http.Request) {
		var version, name string
		if err := db.QueryRowContext(r.Context(), "SELECT VERSION(),DATABASE()").Scan(&version, &name); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		json.NewEncoder(w).Encode(map[string]any{"pid": os.Getpid(), "db_version": version, "db_name": name})
	})
	mux.HandleFunc("/orders", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == "POST" {
			if err := r.ParseForm(); err != nil {
				http.Error(w, "invalid form", 400)
				return
			}
			n, err := strconv.Atoi(r.Form.Get("quantity"))
			if err != nil || n < 1 || len(r.Form.Get("sku")) > 64 {
				http.Error(w, "invalid quantity/SKU", 400)
				return
			}
			if _, err := db.ExecContext(r.Context(), "INSERT INTO orders_order(sku,quantity,status) VALUES(?,?,'ready')", r.Form.Get("sku"), n); err != nil {
				http.Error(w, err.Error(), 500)
				return
			}
			http.Redirect(w, r, "/orders?created=1", http.StatusSeeOther)
			return
		}
		if r.Method != "GET" {
			http.Error(w, "method", 405)
			return
		}
		rows, err := db.QueryContext(r.Context(), "SELECT sku,quantity,status FROM orders_order ORDER BY id")
		if err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		defer rows.Close()
		all := []order{}
		for rows.Next() {
			var o order
			if err := rows.Scan(&o.SKU, &o.Quantity, &o.Status); err != nil {
				http.Error(w, err.Error(), 500)
				return
			}
			all = append(all, o)
		}
		if err := rows.Err(); err != nil {
			http.Error(w, err.Error(), 500)
			return
		}
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		if err := page.Execute(w, struct {
			Created bool
			Orders  []order
		}{r.URL.Query().Get("created") == "1", all}); err != nil {
			log.Print(err)
		}
	})
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		log.Fatal(err)
	}
	json.NewEncoder(os.Stdout).Encode(map[string]any{"address": listener.Addr().String(), "pid": os.Getpid()})
	server := &http.Server{Handler: mux, ReadHeaderTimeout: 5 * time.Second}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	done := make(chan struct{})
	go func() {
		<-ctx.Done()
		deadline, cancel := context.WithTimeout(context.Background(), 3*time.Second)
		defer cancel()
		server.Shutdown(deadline)
		close(done)
	}()
	if err := server.Serve(listener); err != nil && err != http.ErrServerClosed {
		log.Fatal(err)
	}
	<-done
}
