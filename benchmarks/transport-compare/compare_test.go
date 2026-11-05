package transportcompare

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/go-sql-driver/mysql"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/stdlib"
	"github.com/masahitojp/mariamem"
	"github.com/shibukawa/pgmem"
)

type server struct {
	open      func(string) *sql.DB
	retire    func()
	close     func() error
	parameter string
}

func start(b *testing.B, engine string) *server {
	b.Helper()
	ctx := context.Background()
	if engine == "maria" {
		db, e := mariamem.Start(ctx, mariamem.Options{})
		if e != nil {
			b.Fatal(e)
		}
		return &server{parameter: "?", close: db.Close, retire: func() {
			if e := db.WaitDisconnected(ctx); e != nil {
				b.Fatal(e)
			}
		}, open: func(mode string) *sql.DB {
			c, e := mysql.ParseDSN(db.DSN())
			if e != nil {
				b.Fatal(e)
			}
			c.InterpolateParams = false
			if mode == "pipe" {
				c.DialFunc = db.DialContext
			}
			connector, e := mysql.NewConnector(c)
			if e != nil {
				b.Fatal(e)
			}
			return sql.OpenDB(connector)
		}}
	}
	db, e := pgmem.Start(ctx, pgmem.Options{Database: "postgres"})
	if e != nil {
		b.Fatal(e)
	}
	return &server{parameter: "$1", close: db.Close, retire: func() {}, open: func(mode string) *sql.DB {
		c, e := pgx.ParseConfig(db.DSN())
		if e != nil {
			b.Fatal(e)
		}
		c.DefaultQueryExecMode = pgx.QueryExecModeSimpleProtocol
		if mode == "pipe" {
			c.DialFunc = db.Dial
		}
		return sql.OpenDB(stdlib.GetConnector(*c))
	}}
}
func scan(b *testing.B, p *sql.DB, query string, check bool) {
	b.Helper()
	rows, e := p.Query(query)
	if e != nil {
		b.Fatal(e)
	}
	defer rows.Close()
	n := 0
	for rows.Next() {
		var s string
		if e = rows.Scan(&s); e != nil {
			b.Fatal(e)
		}
		if check && s != strings.Repeat("x", 128) {
			b.Fatal("wrong payload")
		}
		n++
	}
	if e = rows.Err(); e != nil || n != 64 {
		b.Fatal(n, e)
	}
}
func BenchmarkCompare(b *testing.B) {
	engines := []string{"maria", "pgmem"}
	modes := []string{"tcp", "pipe"}
	if os.Getenv("COMPARE_ORDER") == "reverse" {
		engines = []string{"pgmem", "maria"}
		modes = []string{"pipe", "tcp"}
	}
	for _, engine := range engines {
		b.Run(engine, func(b *testing.B) {
			s := start(b, engine)
			b.Cleanup(func() {
				if e := s.close(); e != nil {
					b.Error(e)
				}
			})
			setup := s.open("tcp")
			if _, e := setup.Exec("CREATE TABLE transport_rows(id INTEGER PRIMARY KEY, payload VARCHAR(128) NOT NULL)"); e != nil {
				b.Fatal(e)
			}
			vals := []string{}
			for i := 1; i <= 64; i++ {
				vals = append(vals, fmt.Sprintf("(%d,'%s')", i, strings.Repeat("x", 128)))
			}
			if _, e := setup.Exec("INSERT INTO transport_rows VALUES " + strings.Join(vals, ",")); e != nil {
				b.Fatal(e)
			}
			setup.Close()
			s.retire()
			for _, mode := range modes {
				b.Run(mode, func(b *testing.B) {
					for _, work := range []string{"connect_ping", "select1", "prepared1", "result64x128"} {
						b.Run(work, func(b *testing.B) {
							p := s.open(mode)
							p.SetMaxOpenConns(1)
							p.SetMaxIdleConns(1)
							if work == "connect_ping" {
								p.SetMaxIdleConns(0)
							} else if e := p.Ping(); e != nil {
								b.Fatal(e)
							}
							var stmt *sql.Stmt
							if work == "prepared1" {
								var e error
								stmt, e = p.Prepare("SELECT " + s.parameter + " + 1")
								if e != nil {
									b.Fatal(e)
								}
							}
							query := "SELECT payload FROM transport_rows ORDER BY id"
							if work == "result64x128" {
								scan(b, p, query, true)
							}
							b.ReportAllocs()
							b.ResetTimer()
							for i := 0; i < b.N; i++ {
								switch work {
								case "connect_ping":
									if e := p.Ping(); e != nil {
										b.Fatal(e)
									}
								case "select1":
									var n int
									if e := p.QueryRow("SELECT 1").Scan(&n); e != nil || n != 1 {
										b.Fatal(n, e)
									}
								case "prepared1":
									var n int
									if e := stmt.QueryRow(41).Scan(&n); e != nil || n != 42 {
										b.Fatal(n, e)
									}
								case "result64x128":
									scan(b, p, query, false)
								}
							}
							b.StopTimer()
							if stmt != nil {
								stmt.Close()
							}
							p.Close()
							s.retire()
						})
					}
				})
			}
		})
	}
}
