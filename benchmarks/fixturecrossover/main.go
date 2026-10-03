// Diagnostic only: public API, existing fixtures, no runtime/configuration changes.
package main

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"runtime"
	"strings"
	"time"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"
)

// Same model shapes as tests/consumer/gorm/dogfood_test.go.
type User struct {
	ID        uint
	Name      string  `gorm:"size:30;not null;uniqueIndex"`
	Fullname  *string `gorm:"size:120"`
	CreatedAt time.Time
	UpdatedAt time.Time
	Addresses []Address
}
type Address struct {
	ID     uint
	Email  string `gorm:"size:120;not null"`
	UserID uint   `gorm:"not null"`
	User   User   `gorm:"constraint:OnUpdate:CASCADE,OnDelete:RESTRICT;"`
}
type sample struct {
	Index     int     `json:"index"`
	EntryMS   float64 `json:"entry_ms"`
	PrepareMS float64 `json:"prepare_ms"`
	ReadyMS   float64 `json:"ready_ms"`
	WorkMS    float64 `json:"work_ms"`
	CloseMS   float64 `json:"close_ms"`
	TotalMS   float64 `json:"total_ms"`
}
type report struct {
	Scenario          string   `json:"scenario"`
	Mode              string   `json:"mode"`
	Tests             int      `json:"tests"`
	Go                string   `json:"go"`
	OS                string   `json:"os"`
	Arch              string   `json:"arch"`
	ServerVersion     string   `json:"server_version"`
	SetupStartMS      float64  `json:"setup_start_ms"`
	SetupPrepareMS    float64  `json:"setup_prepare_ms"`
	SetupDisconnectMS float64  `json:"setup_disconnect_ms"`
	SetupSnapshotMS   float64  `json:"setup_snapshot_ms"`
	SetupMS           float64  `json:"setup_ms"`
	FinalCleanupMS    float64  `json:"final_cleanup_ms"`
	TotalMS           float64  `json:"total_ms"`
	Completed         bool     `json:"completed"`
	Error             string   `json:"error,omitempty"`
	Samples           []sample `json:"samples"`
}

func ms(t time.Time) float64 { return float64(time.Since(t)) / float64(time.Millisecond) }
func open(db *mariamem.Database, scenario string) (*sql.DB, *gorm.DB, error) {
	if scenario == "gorm-user-address" {
		orm, e := gorm.Open(mysql.Open(db.DSN()+"&parseTime=true"), &gorm.Config{Logger: logger.Default.LogMode(logger.Silent)})
		if e != nil {
			return nil, nil, e
		}
		p, e := orm.DB()
		return p, orm, e
	}
	p, e := sql.Open("mysql", db.DSN())
	return p, nil, e
}
func prepare(ctx context.Context, p *sql.DB, orm *gorm.DB) error {
	if orm != nil {
		if e := orm.WithContext(ctx).AutoMigrate(&User{}, &Address{}); e != nil {
			return e
		}
		return orm.WithContext(ctx).Create(&User{Name: "seed", Addresses: []Address{{Email: "seed@example.test"}}}).Error
	}
	if _, e := p.ExecContext(ctx, "CREATE TABLE benchmark_rows(id INT PRIMARY KEY,payload VARCHAR(64)) ENGINE=InnoDB"); e != nil {
		return e
	}
	tx, e := p.BeginTx(ctx, nil)
	if e != nil {
		return e
	}
	defer tx.Rollback()
	values := make([]string, 1000)
	args := make([]any, 0, 2000)
	for i := range 1000 {
		values[i] = "(?,?)"
		args = append(args, i, strings.Repeat("x", 32))
	}
	if _, e = tx.ExecContext(ctx, "INSERT INTO benchmark_rows VALUES"+strings.Join(values, ","), args...); e != nil {
		return e
	}
	return tx.Commit()
}
func verify(ctx context.Context, p *sql.DB, scenario string) error {
	var n int
	var v string
	if scenario == "gorm-user-address" {
		if e := p.QueryRowContext(ctx, "SELECT COUNT(*) FROM users").Scan(&n); e != nil {
			return e
		}
		if n != 1 {
			return fmt.Errorf("users=%d", n)
		}
		if e := p.QueryRowContext(ctx, "SELECT COUNT(*) FROM addresses").Scan(&n); e != nil {
			return e
		}
		if n != 1 {
			return fmt.Errorf("addresses=%d", n)
		}
		if e := p.QueryRowContext(ctx, "SELECT name FROM users WHERE id=1").Scan(&v); e != nil {
			return e
		}
		if v != "seed" {
			return errors.New("GORM fixture contamination")
		}
		return nil
	}
	if e := p.QueryRowContext(ctx, "SELECT COUNT(*) FROM benchmark_rows").Scan(&n); e != nil {
		return e
	}
	if n != 1000 {
		return fmt.Errorf("rows=%d", n)
	}
	if e := p.QueryRowContext(ctx, "SELECT payload FROM benchmark_rows WHERE id=0").Scan(&v); e != nil {
		return e
	}
	if v != strings.Repeat("x", 32) {
		return errors.New("fixture contamination")
	}
	return nil
}
func work(ctx context.Context, p *sql.DB, scenario string) error {
	// Same transaction/isolation semantics in both paths; never cleanup/reset SQL.
	update := "UPDATE benchmark_rows SET payload='committed-private' WHERE id=0"
	read := "SELECT payload FROM benchmark_rows WHERE id=0"
	if scenario == "gorm-user-address" {
		update = "UPDATE users SET name='committed-private' WHERE id=1"
		read = "SELECT name FROM users WHERE id=1"
	}
	tx, e := p.BeginTx(ctx, nil)
	if e != nil {
		return e
	}
	defer tx.Rollback()
	if _, e = tx.ExecContext(ctx, update); e != nil {
		return e
	}
	if e = tx.Commit(); e != nil {
		return e
	}
	tx, e = p.BeginTx(ctx, nil)
	if e != nil {
		return e
	}
	defer tx.Rollback()
	if _, e = tx.ExecContext(ctx, strings.ReplaceAll(update, "committed-private", "rolled-back")); e != nil {
		return e
	}
	if e = tx.Rollback(); e != nil {
		return e
	}
	var value string
	if e = p.QueryRowContext(ctx, read).Scan(&value); e != nil {
		return e
	}
	if value != "committed-private" {
		return errors.New("commit/rollback mismatch")
	}
	return nil
}
func run(r *report) (err error) {
	ctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
	defer cancel()
	begin := time.Now()
	var snapshot *mariamem.Snapshot
	defer func() {
		if snapshot != nil {
			err = errors.Join(err, snapshot.Close())
		}
		r.TotalMS = ms(begin)
	}()
	if r.Mode == "fork" {
		t := time.Now()
		base, e := mariamem.Start(ctx, mariamem.Options{})
		if e != nil {
			return e
		}
		defer base.Close()
		p, orm, e := open(base, r.Scenario)
		if e != nil {
			return e
		}
		if e = p.QueryRowContext(ctx, "SELECT VERSION()").Scan(&r.ServerVersion); e != nil {
			p.Close()
			return e
		}
		r.SetupStartMS = ms(t)
		t = time.Now()
		e = prepare(ctx, p, orm)
		if e == nil {
			e = verify(ctx, p, r.Scenario)
		}
		r.SetupPrepareMS = ms(t)
		if e != nil {
			p.Close()
			return e
		}
		t = time.Now()
		if e = p.Close(); e != nil {
			return e
		}
		if e = base.WaitDisconnected(ctx); e != nil {
			return e
		}
		r.SetupDisconnectMS = ms(t)
		t = time.Now()
		snapshot, e = base.Snapshot(ctx, mariamem.SnapshotOptions{})
		r.SetupSnapshotMS = ms(t)
		if e != nil {
			return e
		}
		if e = base.Close(); e != nil {
			return e
		}
		r.SetupMS = ms(begin)
	}
	for i := range r.Tests {
		t := time.Now()
		db, e := func() (*mariamem.Database, error) {
			if snapshot != nil {
				return snapshot.Fork(ctx)
			}
			return mariamem.Start(ctx, mariamem.Options{})
		}()
		if e != nil {
			return e
		}
		p, orm, e := open(db, r.Scenario)
		if e != nil {
			db.Close()
			return e
		}
		row := sample{Index: i, EntryMS: ms(t)}
		if r.Mode == "fresh" {
			prep := time.Now()
			e = prepare(ctx, p, orm)
			row.PrepareMS = ms(prep)
		}
		if e == nil {
			e = verify(ctx, p, r.Scenario)
		}
		if e != nil {
			p.Close()
			db.Close()
			return e
		}
		row.ReadyMS = ms(t)
		if r.ServerVersion == "" {
			if e = p.QueryRowContext(ctx, "SELECT VERSION()").Scan(&r.ServerVersion); e != nil {
				p.Close()
				db.Close()
				return e
			}
		}
		q := time.Now()
		e = work(ctx, p, r.Scenario)
		row.WorkMS = ms(q)
		q = time.Now()
		e = errors.Join(e, p.Close())
		e = errors.Join(e, db.WaitDisconnected(ctx))
		e = errors.Join(e, db.Close())
		row.CloseMS = ms(q)
		if e != nil {
			return e
		}
		if db.Err() != nil {
			return db.Err()
		}
		row.TotalMS = ms(t)
		r.Samples = append(r.Samples, row)
	}
	if snapshot != nil {
		q := time.Now()
		if e := snapshot.Close(); e != nil {
			return e
		}
		r.FinalCleanupMS = ms(q)
		snapshot = nil
	}
	r.Completed = true
	return nil
}
func main() {
	scenario := flag.String("scenario", "fixture-1000", "fixture-1000 or gorm-user-address")
	mode := flag.String("mode", "fresh", "fresh or fork")
	n := flag.Int("tests", 10, "isolated tests")
	out := flag.String("json", "", "result path")
	flag.Parse()
	if (*scenario != "fixture-1000" && *scenario != "gorm-user-address") || (*mode != "fresh" && *mode != "fork") || *n < 1 || *out == "" {
		panic("invalid args")
	}
	for _, key := range []string{"MARIAMEM_NATIVE_DIR", "MARIAMEM_RUNTIME", "MARIAMEM_TIMING_DIR", "MARIAMEM_INIT_DIAGNOSTICS", "MARIAMEM_MEMORY_DIAGNOSTICS"} {
		os.Unsetenv(key)
	}
	r := report{Scenario: *scenario, Mode: *mode, Tests: *n, Go: runtime.Version(), OS: runtime.GOOS, Arch: runtime.GOARCH, Samples: []sample{}}
	e := run(&r)
	if e != nil {
		r.Error = e.Error()
	}
	b, encodeErr := json.MarshalIndent(r, "", "  ")
	if encodeErr != nil {
		panic(encodeErr)
	}
	if writeErr := os.WriteFile(*out, append(b, '\n'), 0600); writeErr != nil {
		panic(writeErr)
	}
	fmt.Printf("%s %s n=%d total=%.3fs completed=%v\n", *scenario, *mode, *n, r.TotalMS/1000, r.Completed)
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
