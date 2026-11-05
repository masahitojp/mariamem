package pipetransport_test

import (
	"context"
	"database/sql"
	"os"
	"runtime"
	"strings"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func startDatabase(b *testing.B) *mariamem.Database {
	b.Helper()
	db, err := mariamem.Start(context.Background(), mariamem.Options{})
	if err != nil {
		b.Fatal(err)
	}
	b.Cleanup(func() {
		if err := db.Close(); err != nil {
			b.Error(err)
		}
	})
	return db
}
func openPool(b *testing.B, db *mariamem.Database, mode string) *sql.DB {
	b.Helper()
	config, err := mysql.ParseDSN(db.DSN())
	if err != nil {
		b.Fatal(err)
	}
	config.InterpolateParams = false
	if mode == "pipe" {
		config.DialFunc = db.DialContext
	}
	connector, err := mysql.NewConnector(config)
	if err != nil {
		b.Fatal(err)
	}
	pool := sql.OpenDB(connector)
	pool.SetMaxOpenConns(16)
	pool.SetMaxIdleConns(16)
	b.Cleanup(func() { pool.Close() })
	return pool
}

func BenchmarkPipeTransport(b *testing.B) {
	modes := []string{"tcp", "pipe"}
	if os.Getenv("ISSUE66_ORDER") == "pipe-first" {
		modes = []string{"pipe", "tcp"}
	}
	b.Logf("Go=%s GOMAXPROCS=%d", runtime.Version(), runtime.GOMAXPROCS(0))
	s := startDatabase(b)
	for _, mode := range modes {
		b.Run(mode, func(b *testing.B) {
			for _, work := range []string{"connect_ping", "select1", "prepared1", "result64x128"} {
				b.Run(work, func(b *testing.B) {
					db := openPool(b, s, mode)
					if work == "connect_ping" {
						db.SetMaxIdleConns(0)
					} else {
						db.SetMaxOpenConns(1)
						db.SetMaxIdleConns(1)
						if err := db.Ping(); err != nil {
							b.Fatal(err)
						}
					}
					var stmt *sql.Stmt
					if work == "prepared1" {
						var err error
						stmt, err = db.Prepare("SELECT ? + 1")
						if err != nil {
							b.Fatal(err)
						}
						defer stmt.Close()
					}
					query := "SELECT REPEAT('x',128) FROM seq_1_to_64"
					if work == "result64x128" {
						rows, err := db.Query(query)
						if err != nil {
							b.Fatal(err)
						}
						n := 0
						for rows.Next() {
							var s string
							if err = rows.Scan(&s); err != nil || s != strings.Repeat("x", 128) {
								b.Fatal(err)
							}
							n++
						}
						if err = rows.Err(); err != nil || n != 64 {
							b.Fatal(n, err)
						}
						rows.Close()
					}
					b.ReportAllocs()
					b.ResetTimer()
					for i := 0; i < b.N; i++ {
						switch work {
						case "connect_ping":
							if err := db.Ping(); err != nil {
								b.Fatal(err)
							}
						case "select1":
							var n int
							if err := db.QueryRow("SELECT 1").Scan(&n); err != nil || n != 1 {
								b.Fatal(n, err)
							}
						case "prepared1":
							var n int
							if err := stmt.QueryRow(41).Scan(&n); err != nil || n != 42 {
								b.Fatal(n, err)
							}
						case "result64x128":
							rows, err := db.Query(query)
							if err != nil {
								b.Fatal(err)
							}
							n := 0
							for rows.Next() {
								var s string
								if err = rows.Scan(&s); err != nil {
									b.Fatal(err)
								}
								n++
							}
							if err = rows.Err(); err != nil || n != 64 {
								b.Fatal(n, err)
							}
							rows.Close()
						}
					}
					b.StopTimer()
					if stmt != nil {
						stmt.Close()
					}
					db.Close()
					if err := s.WaitDisconnected(context.Background()); err != nil {
						b.Fatal(err)
					}
				})
			}
		})
	}
}
