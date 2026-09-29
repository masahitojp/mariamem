package dogfood

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"testing"
	"time"

	driver "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
	"gorm.io/driver/mysql"
	"gorm.io/gorm"
)

// Conventional has-many models: no test cleanup hooks or soft-delete policy.
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

type observation struct {
	Name     string                  `json:"name"`
	ReadyMS  float64                 `json:"ready_ms"`
	SetupMS  float64                 `json:"setup_ms"`
	TotalMS  float64                 `json:"total_ms"`
	Endpoint mariamem.ConnectionInfo `json:"endpoint"`
	Pool     sql.DBStats             `json:"pool"`
	Details  map[string]any          `json:"details"`
	Cleanup  bool                    `json:"cleanup"`
	Passed   bool                    `json:"passed"`
}
type application struct {
	runtime *mariamem.Database
	orm     *gorm.DB
	pool    *sql.DB
	record  *observation
}

func require(t *testing.T, err error) {
	t.Helper()
	if err != nil {
		t.Fatal(err)
	}
}
func check(t *testing.T, ok bool, message string) {
	t.Helper()
	if !ok {
		t.Fatal(message)
	}
}
func milliseconds(start time.Time) float64 {
	return float64(time.Since(start)) / float64(time.Millisecond)
}
func open(t *testing.T, db *mariamem.Database) (*gorm.DB, *sql.DB) {
	t.Helper()
	// parseTime is the ordinary MySQL driver option needed for time.Time models.
	orm, err := gorm.Open(mysql.Open(db.DSN()+"&parseTime=true"), &gorm.Config{})
	require(t, err)
	pool, err := orm.DB()
	require(t, err)
	return orm, pool
}
func prepare(t *testing.T, orm *gorm.DB) {
	t.Helper()
	require(t, orm.AutoMigrate(&User{}, &Address{}))
	require(t, orm.Create(&User{Name: "seed", Addresses: []Address{{Email: "seed@example.test"}}}).Error)
}
func childPIDs(t *testing.T) []string {
	t.Helper()
	out, err := exec.Command("ps", "-axo", "pid=,ppid=,comm=").Output()
	require(t, err)
	var ids []string
	for _, line := range strings.Split(string(out), "\n") {
		f := strings.Fields(line)
		if len(f) >= 3 && f[1] == strconv.Itoa(os.Getpid()) && strings.Contains(strings.Join(f[2:], " "), "wasmer") {
			ids = append(ids, f[0])
		}
	}
	return ids
}

func TestDogfood(t *testing.T) {
	native, output, mode := os.Getenv("DOGFOOD_NATIVE_DIR"), os.Getenv("DOGFOOD_EVIDENCE"), os.Getenv("DOGFOOD_MODE")
	if native == "" || output == "" {
		t.Skip("run via tests/consumer/run_gorm.py with an explicit native bundle")
	}
	check(t, mode == "start" || mode == "fork", "invalid mode")
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()
	opts := mariamem.Options{NativeDir: native}
	var cases []*observation
	result := map[string]any{"mode": mode, "go": runtime.Version(), "os": runtime.GOOS, "arch": runtime.GOARCH, "native_dir": native}
	manifest, err := os.ReadFile(filepath.Join(native, "manifest.json"))
	require(t, err)
	var metadata any
	require(t, json.Unmarshal(manifest, &metadata))
	result["native_manifest"] = metadata
	if b, err := exec.Command("go", "list", "-m", "-json", "all").Output(); err == nil {
		result["modules"] = string(b)
	}
	started := time.Now()
	t.Cleanup(func() {
		result["cases"], result["total_ms"], result["passed"] = cases, milliseconds(started), !t.Failed()
		result["runtime_children_after"] = childPIDs(t)
		data, err := json.MarshalIndent(result, "", "  ")
		if err == nil {
			err = os.WriteFile(output, append(data, '\n'), 0600)
		}
		if err != nil {
			t.Error(err)
		}
	})
	var snapshot *mariamem.Snapshot
	if mode == "fork" {
		begin := time.Now()
		template, err := mariamem.Start(ctx, opts)
		require(t, err)
		t.Cleanup(func() { require(t, template.Close()) })
		orm, pool := open(t, template)
		prepare(t, orm)
		require(t, pool.Close())
		require(t, template.WaitDisconnected(ctx))
		snapshot, err = template.Snapshot(ctx, mariamem.SnapshotOptions{})
		require(t, err)
		check(t, template.Closed() && template.Err() == nil, "snapshot did not consume template cleanly")
		result["template_snapshot_ms"] = milliseconds(begin)
		t.Cleanup(func() {
			path := snapshot.Path()
			require(t, snapshot.Close())
			_, err := os.Stat(path)
			check(t, os.IsNotExist(err), "snapshot files remain")
		})
	}
	run := func(name string, test func(*testing.T, *application)) {
		t.Run(name, func(t *testing.T) {
			begin := time.Now()
			r := &observation{Name: name, Details: map[string]any{}}
			cases = append(cases, r)
			var db *mariamem.Database
			var err error
			if snapshot == nil {
				db, err = mariamem.Start(ctx, opts)
			} else {
				db, err = snapshot.Fork(ctx)
			}
			require(t, err)
			var pool *sql.DB
			t.Cleanup(func() {
				if pool != nil {
					r.Pool = pool.Stats()
					require(t, pool.Close())
				}
				if !db.Closed() {
					require(t, db.WaitDisconnected(ctx))
				}
				require(t, db.Close())
				r.Cleanup = db.Closed() && db.Err() == nil
				check(t, r.Cleanup, "unclean database close")
				pids := childPIDs(t)
				r.Details["runtime_children_after"] = pids
				check(t, len(pids) == 0, "runtime child remains")
				r.Passed = !t.Failed()
				r.TotalMS = milliseconds(begin)
			})
			orm, p := open(t, db)
			pool = p
			r.ReadyMS = milliseconds(begin)
			setup := time.Now()
			if snapshot == nil {
				prepare(t, orm)
			}
			r.SetupMS = milliseconds(setup)
			r.Endpoint = db.ConnectionInfo()
			var users []User
			require(t, orm.Find(&users).Error)
			check(t, len(users) == 1 && users[0].Name == "seed", "unexpected initial state")
			test(t, &application{db, orm, pool, r})
		})
	}
	run("01_commit_without_cleanup", func(t *testing.T, a *application) {
		require(t, a.orm.Transaction(func(tx *gorm.DB) error { return tx.Create(&User{Name: "committed-A"}).Error }))
		var n int64
		require(t, a.orm.Model(&User{}).Count(&n).Error)
		check(t, n == 2, "commit missing")
		a.record.Details["committed_users"] = n
	})
	run("02_next_test_clean", func(t *testing.T, a *application) {
		var n int64
		require(t, a.orm.Model(&User{}).Where("name = ?", "committed-A").Count(&n).Error)
		check(t, n == 0, "test A leaked committed state")
		a.record.Details["prior_committed_rows"] = n
	})
	run("03_crud_relationships", func(t *testing.T, a *application) {
		u := User{Name: "alice", Addresses: []Address{{Email: "alice@example.test"}}}
		require(t, a.orm.Create(&u).Error)
		var loaded User
		require(t, a.orm.Preload("Addresses").First(&loaded, u.ID).Error)
		check(t, len(loaded.Addresses) == 1, "relationship missing")
		var joined Address
		require(t, a.orm.Joins("User").First(&joined, "addresses.user_id = ?", u.ID).Error)
		check(t, joined.User.Name == "alice", "join missing")
		require(t, a.orm.Model(&u).Update("fullname", "Alice Example").Error)
		require(t, a.orm.First(&loaded, u.ID).Error)
		check(t, loaded.Fullname != nil && *loaded.Fullname == "Alice Example" && !loaded.CreatedAt.IsZero(), "update/timestamp missing")
		// DELETE is application behavior, never fixture teardown.
		require(t, a.orm.Delete(&Address{}, "user_id = ?", u.ID).Error)
		require(t, a.orm.Delete(&u).Error)
		check(t, errors.Is(a.orm.First(&User{}, u.ID).Error, gorm.ErrRecordNotFound), "delete missing")
	})
	run("04_explicit_rollback", func(t *testing.T, a *application) {
		tx := a.orm.Begin()
		require(t, tx.Error)
		require(t, tx.Create(&User{Name: "rolled-back"}).Error)
		require(t, tx.Rollback().Error)
		var n int64
		require(t, a.orm.Model(&User{}).Where("name = ?", "rolled-back").Count(&n).Error)
		check(t, n == 0, "rollback failed")
	})
	run("05_constraint_errors_recoverable", func(t *testing.T, a *application) {
		for _, probe := range []struct {
			err  error
			code uint16
		}{
			{a.orm.Create(&User{Name: "seed"}).Error, 1062},
			{a.orm.Model(&User{}).Create(map[string]any{"name": nil}).Error, 1048},
			{a.orm.Create(&Address{Email: "orphan@example.test", UserID: 99999}).Error, 1452},
		} {
			var e *driver.MySQLError
			check(t, errors.As(probe.err, &e) && e.Number == probe.code, "unexpected constraint error")
		}
		var n int64
		require(t, a.orm.Model(&User{}).Count(&n).Error)
		check(t, n == 1 && !a.runtime.Closed(), "ordinary error invalidated database")
		a.record.Details["mysql_error_codes"] = []int{1062, 1048, 1452}
	})
	run("06_normal_pool_sessions", func(t *testing.T, a *application) {
		one, err := a.pool.Conn(ctx)
		require(t, err)
		defer one.Close()
		two, err := a.pool.Conn(ctx)
		require(t, err)
		defer two.Close()
		var first, second int
		require(t, one.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&first))
		require(t, two.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&second))
		check(t, first != second, "sessions not independent")
		_, err = one.ExecContext(ctx, "SET @dogfood_marker=17")
		require(t, err)
		var marker sql.NullInt64
		require(t, two.QueryRowContext(ctx, "SELECT @dogfood_marker").Scan(&marker))
		check(t, !marker.Valid, "session variable leaked")
		_, err = one.ExecContext(ctx, "CREATE TEMPORARY TABLE pool_probe (id INT)")
		require(t, err)
		_, err = two.ExecContext(ctx, "SELECT * FROM pool_probe")
		var mysqlErr *driver.MySQLError
		check(t, errors.As(err, &mysqlErr) && mysqlErr.Number == 1146, "temporary table leaked")
		tx, err := one.BeginTx(ctx, nil)
		require(t, err)
		_, err = tx.ExecContext(ctx, "INSERT INTO users (name) VALUES ('uncommitted')")
		require(t, err)
		var n int
		require(t, two.QueryRowContext(ctx, "SELECT COUNT(*) FROM users WHERE name='uncommitted'").Scan(&n))
		check(t, n == 0, "uncommitted transaction leaked")
		require(t, tx.Rollback())
		require(t, one.Close())
		require(t, two.Close())
		conn, err := a.pool.Conn(ctx)
		require(t, err)
		defer conn.Close()
		other, err := a.pool.Conn(ctx)
		require(t, err)
		defer other.Close()
		var reusedIDs []int
		var reusedMarkers []sql.NullInt64
		for _, reusedConn := range []*sql.Conn{conn, other} {
			var reused int
			require(t, reusedConn.QueryRowContext(ctx, "SELECT CONNECTION_ID()").Scan(&reused))
			check(t, reused == first || reused == second, "pool did not reuse connection")
			require(t, reusedConn.QueryRowContext(ctx, "SELECT @dogfood_marker").Scan(&marker))
			check(t, (reused == first && marker.Valid && marker.Int64 == 17) || (reused == second && !marker.Valid), "unexpected reused session state")
			if reused == first {
				_, err = reusedConn.ExecContext(ctx, "SELECT * FROM pool_probe")
				require(t, err)
			}
			reusedIDs = append(reusedIDs, reused)
			reusedMarkers = append(reusedMarkers, marker)
		}
		check(t, reusedIDs[0] != reusedIDs[1], "reused sessions unexpectedly identical")
		a.record.Details["initial_connection_ids"] = []int{first, second}
		a.record.Details["reused_connection_ids"] = reusedIDs
		a.record.Details["reused_session_variables"] = reusedMarkers
		check(t, a.pool.Stats().MaxOpenConnections == 0, "unexpected pool restriction")
	})
	run("07_idempotent_migrate_introspection", func(t *testing.T, a *application) {
		// Preserve the ordinary migrator and capture its failing boundary, rather
		// than replacing HasTable or supplying a special database name.
		diagnostics := map[string]any{}
		for _, query := range []string{
			"SELECT VERSION()", "SELECT DATABASE()",
			"SHOW DATABASES",
			"SELECT SCHEMA_NAME FROM information_schema.schemata",
			"SELECT SCHEMA_NAME FROM information_schema.schemata WHERE SCHEMA_NAME='test'",
			"SELECT SCHEMA_NAME from Information_schema.SCHEMATA where SCHEMA_NAME LIKE 'test%' ORDER BY SCHEMA_NAME='test' DESC,SCHEMA_NAME limit 1",
			"SELECT SCHEMA_NAME from information_schema.schemata where SCHEMA_NAME LIKE 'test%' ORDER BY SCHEMA_NAME='test' DESC,SCHEMA_NAME limit 1",
			"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'test' AND table_name = 'users' AND table_type = 'BASE TABLE'",
			"SHOW TABLES",
		} {
			rows, err := a.pool.QueryContext(ctx, query)
			if err != nil {
				diagnostics[query] = map[string]any{"error": err.Error()}
				continue
			}
			var values []string
			for rows.Next() {
				var value string
				require(t, rows.Scan(&value))
				values = append(values, value)
			}
			require(t, rows.Err())
			require(t, rows.Close())
			diagnostics[query] = values
		}
		diagnostics["gorm_current_database"] = a.orm.Migrator().CurrentDatabase()
		diagnostics["gorm_has_users"] = a.orm.Migrator().HasTable(&User{})
		a.record.Details["migration_diagnostics"] = diagnostics
		require(t, a.orm.AutoMigrate(&User{}, &Address{}))
		check(t, a.orm.Migrator().HasTable(&User{}) && a.orm.Migrator().HasConstraint(&Address{}, "User"), "metadata missing")
		var version string
		require(t, a.orm.Raw("SELECT VERSION()").Scan(&version).Error)
		a.record.Details["server_version"] = version
	})
	run("08_shutdown_with_pool", func(t *testing.T, a *application) {
		conn, err := a.pool.Conn(ctx)
		require(t, err)
		idle, err := a.pool.Conn(ctx)
		require(t, err)
		require(t, idle.Close())
		a.record.Details["pool_before_runtime_close"] = a.pool.Stats()
		require(t, a.runtime.Close())
		_, err = conn.ExecContext(ctx, "SELECT 1")
		check(t, err != nil, "closed runtime still served SQL")
		require(t, conn.Close())
		require(t, a.pool.Close())
	})
}
