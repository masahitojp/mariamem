//go:build issue66

package host

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"io"
	"net"
	"os"
	"runtime"
	"strings"
	"testing"
	"time"

	"github.com/go-sql-driver/mysql"
)

func spikeServer(t testing.TB) *Server {
	t.Helper()
	s, err := StartGenerated(context.Background(), nil, 5*time.Second, io.Discard)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() {
		if s.Closing() {
			return
		}
		failed := s.Failure() != nil
		if err := s.Close(context.Background()); err != nil && !failed {
			t.Error(err)
		}
	})
	return s
}
func spikeDB(t testing.TB, s *Server, mode string) *sql.DB {
	t.Helper()
	c := mysql.NewConfig()
	c.User = "root"
	c.DBName = "mysql"
	c.Net = "tcp"
	c.Addr = fmt.Sprintf("127.0.0.1:%d", s.Port())
	c.Timeout = 2 * time.Second
	c.ReadTimeout = 3 * time.Second
	c.WriteTimeout = 3 * time.Second
	if mode == "pipe" {
		c.DialFunc = func(ctx context.Context, _, _ string) (net.Conn, error) { return s.DialPipe(ctx) }
	}
	connector, err := mysql.NewConnector(c)
	if err != nil {
		t.Fatal(err)
	}
	db := sql.OpenDB(connector)
	db.SetMaxOpenConns(16)
	db.SetMaxIdleConns(16)
	t.Cleanup(func() { db.Close() })
	return db
}
func spikeIdle(t testing.TB, s *Server) {
	t.Helper()
	deadline := time.Now().Add(3 * time.Second)
	for s.Active() != 0 {
		if time.Now().After(deadline) {
			t.Fatalf("active sessions remain: %d", s.Active())
		}
		time.Sleep(time.Millisecond)
	}
}
func TestIssue66(t *testing.T) {
	for _, mode := range []string{"tcp", "pipe"} {
		t.Run(mode, func(t *testing.T) {
			s := spikeServer(t)
			db := spikeDB(t, s, mode)
			ctx := context.Background()
			t.Run("handshake_select", func(t *testing.T) {
				var n int
				if err := db.QueryRow("SELECT 1").Scan(&n); err != nil || n != 1 {
					t.Fatal(n, err)
				}
			})
			t.Run("prepared_parameter", func(t *testing.T) {
				st, err := db.Prepare("SELECT ? + 1")
				if err != nil {
					t.Fatal(err)
				}
				defer st.Close()
				var n int
				if err = st.QueryRow(41).Scan(&n); err != nil || n != 42 {
					t.Fatal(n, err)
				}
			})
			t.Run("transaction_commit_rollback", func(t *testing.T) {
				if _, err := db.Exec("CREATE TABLE issue66_t (id INT PRIMARY KEY)"); err != nil {
					t.Fatal(err)
				}
				defer db.Exec("DROP TABLE issue66_t")
				tx, err := db.Begin()
				if err != nil {
					t.Fatal(err)
				}
				defer tx.Rollback()
				if _, err = tx.Exec("INSERT INTO issue66_t VALUES (?)", 1); err != nil {
					t.Fatal(err)
				}
				if err = tx.Rollback(); err != nil {
					t.Fatal(err)
				}
				var n int
				if err = db.QueryRow("SELECT COUNT(*) FROM issue66_t").Scan(&n); err != nil || n != 0 {
					t.Fatal(n, err)
				}
				tx2, err := db.Begin()
				if err != nil {
					t.Fatal(err)
				}
				defer tx2.Rollback()
				if _, err = tx2.Exec("INSERT INTO issue66_t VALUES (?)", 2); err != nil {
					t.Fatal(err)
				}
				if err = tx2.Commit(); err != nil {
					t.Fatal(err)
				}
				if err = db.QueryRow("SELECT COUNT(*) FROM issue66_t").Scan(&n); err != nil || n != 1 {
					t.Fatal(n, err)
				}

			})
			t.Run("capacity_and_reuse", func(t *testing.T) {
				conns := []*sql.Conn{}
				defer func() {
					for _, c := range conns {
						c.Close()
					}
				}()
				for i := 0; i < s.Capacity(); i++ {
					c, err := db.Conn(ctx)
					if err != nil {
						t.Fatal(i, err)
					}
					conns = append(conns, c)
				}
				other := spikeDB(t, s, mode)
				err := other.Ping()
				var me *mysql.MySQLError
				if !errors.As(err, &me) || me.Number != 1040 {
					t.Fatalf("want capacity1040, got %v", err)
				}
				for _, c := range conns {
					c.Close()
				}
				conns = nil
				db.Close()
				spikeIdle(t, s)
				if err = other.Ping(); err != nil {
					t.Fatal(err)
				}
				other.Close()
				spikeIdle(t, s)
			})
			t.Run("close_with_idle_and_unread_handshake", func(t *testing.T) {
				db2 := spikeDB(t, s, mode)
				if err := db2.Ping(); err != nil {
					t.Fatal(err)
				}
				var raw net.Conn
				var err error
				if mode == "pipe" {
					raw, err = s.DialPipe(ctx)
				} else {
					raw, err = net.Dial("tcp", fmt.Sprintf("127.0.0.1:%d", s.Port()))
				}
				if err != nil {
					t.Fatal(err)
				}
				defer raw.Close()
				if err = s.Close(ctx); err != nil {
					t.Fatal(err)
				}
				if s.Active() != 0 {
					t.Fatal("active after Close")
				}
				if err = db2.Ping(); err == nil {
					t.Fatal("closed DB accepted query")
				}
				if mode == "pipe" {
					if c, e := s.DialPipe(ctx); e == nil {
						c.Close()
						t.Fatal("dial after Close succeeded")
					}
				}
			})
		})
	}
	t.Run("pipe_cancelled_dial", func(t *testing.T) {
		s := spikeServer(t)
		ctx, cancel := context.WithCancel(context.Background())
		cancel()
		if c, e := s.DialPipe(ctx); !errors.Is(e, context.Canceled) {
			if c != nil {
				c.Close()
			}
			t.Fatal(e)
		}
		if s.Active() != 0 {
			t.Fatal("cancelled dial admitted")
		}
	})
	for _, mode := range []string{"tcp", "pipe"} {
		t.Run(mode+"_query_cancel", func(t *testing.T) {
			s := spikeServer(t)
			db := spikeDB(t, s, mode)
			if err := db.Ping(); err != nil {
				t.Fatal(err)
			}
			ctx, cancel := context.WithTimeout(context.Background(), 50*time.Millisecond)
			defer cancel()
			var n int
			err := db.QueryRowContext(ctx, "SELECT SLEEP(3)").Scan(&n)
			if !errors.Is(err, context.DeadlineExceeded) {
				t.Fatal(err)
			}
			deadline := time.Now().Add(3 * time.Second)
			for s.Failure() == nil && time.Now().Before(deadline) {
				time.Sleep(time.Millisecond)
			}
			if s.Failure() == nil {
				t.Fatal("query cancellation did not invalidate instance")
			}
			db.Close()
			spikeIdle(t, s)
			other := spikeDB(t, s, mode)
			if err = other.Ping(); err == nil {
				t.Fatal("failed instance usable")
			}
		})
	}
	t.Run("pipe_capacity_rejection_close", func(t *testing.T) {
		s := spikeServer(t)
		db := spikeDB(t, s, "pipe")
		conns := []*sql.Conn{}
		defer func() {
			for _, c := range conns {
				c.Close()
			}
		}()
		for i := 0; i < s.Capacity(); i++ {
			c, err := db.Conn(context.Background())
			if err != nil {
				t.Fatal(err)
			}
			conns = append(conns, c)
		}
		raw, err := s.DialPipe(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		defer raw.Close()
		if s.Active() != s.Capacity()+1 {
			t.Fatal("unread rejection not tracked")
		}
		if err = s.Close(context.Background()); err != nil {
			t.Fatal(err)
		}
		if s.Active() != 0 {
			t.Fatal("unread rejection retained after Close")
		}
	})
	t.Run("pipe_guest_failure_new_dial", func(t *testing.T) {
		s := spikeServer(t)
		s.Guest.Abort(errors.New("issue66 injected guest failure"))
		db := spikeDB(t, s, "pipe")
		err := db.Ping()
		var me *mysql.MySQLError
		if !errors.As(err, &me) || me.Number != 2013 {
			t.Fatalf("want unavailable2013, got %v", err)
		}
		db.Close()
		spikeIdle(t, s)
	})

	t.Run("pipe_read_deadline", func(t *testing.T) {
		s := spikeServer(t)
		c, err := s.DialPipe(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		defer c.Close()
		c.SetReadDeadline(time.Now().Add(-time.Second))
		_, err = c.Read(make([]byte, 1))
		var ne net.Error
		if !errors.As(err, &ne) || !ne.Timeout() {
			t.Fatal(err)
		}
		c.Close()
		spikeIdle(t, s)
	})
	t.Run("pipe_close_race", func(t *testing.T) {
		s := spikeServer(t)
		done := make(chan struct{})
		go func() {
			defer close(done)
			for i := 0; i < 40; i++ {
				c, err := s.DialPipe(context.Background())
				if err != nil {
					return
				}
				c.Close()
			}
		}()
		if err := s.Close(context.Background()); err != nil {
			t.Fatal(err)
		}
		select {
		case <-done:
		case <-time.After(3 * time.Second):
			t.Fatal("dial blocked by Close")
		}
		if s.Active() != 0 {
			t.Fatal("retained sessions")
		}
	})
}

func BenchmarkIssue66(b *testing.B) {
	modes := []string{"tcp", "pipe"}
	if os.Getenv("ISSUE66_ORDER") == "pipe-first" {
		modes = []string{"pipe", "tcp"}
	}
	b.Logf("Go=%s GOMAXPROCS=%d", runtime.Version(), runtime.GOMAXPROCS(0))
	s := spikeServer(b)
	for _, mode := range modes {
		b.Run(mode, func(b *testing.B) {
			for _, work := range []string{"connect_ping", "select1", "prepared1", "result64x128"} {
				b.Run(work, func(b *testing.B) {
					db := spikeDB(b, s, mode)
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
					spikeIdle(b, s)
				})
			}
		})
	}
}
