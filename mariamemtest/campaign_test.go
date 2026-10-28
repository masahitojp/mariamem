//go:build integration

package mariamemtest

import (
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"testing"
	"time"

	"github.com/masahitojp/mariamem"
)

// Campaign instrumentation is test-only. It wraps the actual production
// dependencies and DB(t), without adding product API or replacing the driver.
type campaign struct {
	mu              sync.Mutex
	Start           time.Time        `json:"-"`
	Cap             int              `json:"cap"`
	Parallel        int              `json:"parallel"`
	PID             int              `json:"pid"`
	Pools           []*sql.DB        `json:"-"`
	Children        int              `json:"active_children"`
	Baselines       int              `json:"retained_baselines"`
	PeakChildren    int              `json:"peak_children"`
	PeakConnections int              `json:"peak_physical_pool_connections"`
	Snapshots       []campaignSample `json:"samples"`
	Cases           []campaignCase   `json:"cases"`
	Batches         []campaignBatch  `json:"batches"`
	Phases          []campaignPhase  `json:"phases"`
	Stop            string           `json:"stop_reason"`
	Result          string           `json:"result"`
	Cleanup         bool             `json:"cleanup_complete"`
	NewSeconds      float64          `json:"new_fixture_seconds"`
	CloseSeconds    float64          `json:"fixture_close_seconds"`
	Limits          campaignLimits   `json:"guards"`
}
type campaignLimits struct {
	Disk int64  `json:"owned_disk_ceiling_bytes"`
	Free uint64 `json:"min_free_disk_bytes"`
	FD   uint64 `json:"min_fd_headroom"`
}
type campaignSample struct {
	Unix        int64   `json:"unix_ns"`
	At          float64 `json:"at_seconds"`
	Label       string  `json:"label"`
	FD          int     `json:"fd"`
	FDLimit     uint64  `json:"fd_soft_limit"`
	Linked      int64   `json:"linked_temp_bytes"`
	Unlinked    int64   `json:"unlinked_file_bytes"`
	Free        uint64  `json:"disk_free_bytes"`
	Children    int     `json:"children"`
	Baselines   int     `json:"baselines"`
	Connections int     `json:"physical_pool_connections"`
}
type campaignPhase struct {
	Name    string  `json:"name"`
	Seconds float64 `json:"seconds"`
}
type campaignBatch struct {
	Label   string  `json:"label"`
	Seconds float64 `json:"elapsed_seconds"`
}
type campaignCase struct {
	Name      string  `json:"name"`
	Admission float64 `json:"admission_seconds"`
	SQL       float64 `json:"sql_seconds"`
	Cleanup   float64 `json:"cleanup_seconds"`
}

func fdInventory() (int, int64, uint64, error) {
	var limit syscall.Rlimit
	if err := syscall.Getrlimit(syscall.RLIMIT_NOFILE, &limit); err != nil {
		return 0, 0, 0, err
	}
	var fds []int
	if runtime.GOOS == "linux" {
		entries, err := os.ReadDir("/proc/self/fd")
		if err != nil {
			return 0, 0, 0, err
		}
		for _, entry := range entries {
			fd, err := strconv.Atoi(entry.Name())
			if err != nil {
				return 0, 0, 0, err
			}
			fds = append(fds, fd)
		}
	} else {
		for fd := uint64(0); fd < limit.Cur; fd++ {
			fds = append(fds, int(fd))
		}
	}
	n := 0
	var unlinked int64
	seen := map[[2]uint64]bool{}
	for _, fd := range fds {
		var st syscall.Stat_t
		if err := syscall.Fstat(fd, &st); errors.Is(err, syscall.EBADF) {
			continue
		} else if err != nil {
			return 0, 0, 0, err
		}
		n++
		key := [2]uint64{uint64(st.Dev), uint64(st.Ino)}
		if st.Mode&syscall.S_IFMT == syscall.S_IFREG && st.Nlink == 0 && !seen[key] {
			seen[key] = true
			unlinked += st.Blocks * 512
		}
	}
	return n, unlinked, limit.Cur, nil
}
func tempUsage() (int64, uint64, error) {
	var total int64
	err := filepath.WalkDir(os.TempDir(), func(path string, d os.DirEntry, err error) error {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		if err != nil {
			return err
		}
		if d.IsDir() {
			return nil
		}
		info, err := d.Info()
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		if err != nil {
			return err
		}
		st, ok := info.Sys().(*syscall.Stat_t)
		if !ok {
			return errors.New("missing allocated-block counter")
		}
		total += st.Blocks * 512
		return nil
	})
	var fs syscall.Statfs_t
	if err == nil {
		err = syscall.Statfs(os.TempDir(), &fs)
	}
	return total, uint64(fs.Bavail) * uint64(fs.Bsize), err
}
func (m *campaign) saveLocked() error {
	b, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return err
	}
	path := os.Getenv("MARIAMEM_G1_REPORT")
	if err = os.WriteFile(path+".new", b, 0600); err != nil {
		return err
	}
	return os.Rename(path+".new", path)
}
func (m *campaign) sample(label string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	fd, unlinked, limit, err := fdInventory()
	if err != nil {
		return err
	}
	linked, free, err := tempUsage()
	if err != nil {
		return err
	}
	connections := 0
	for _, p := range m.Pools {
		connections += p.Stats().OpenConnections
	}
	s := campaignSample{time.Now().UnixNano(), time.Since(m.Start).Seconds(), label, fd, limit, linked, unlinked, free, m.Children, m.Baselines, connections}
	m.Snapshots = append(m.Snapshots, s)
	if m.Children > m.PeakChildren {
		m.PeakChildren = m.Children
	}
	if connections > m.PeakConnections {
		m.PeakConnections = connections
	}
	if m.Stop == "" {
		switch {
		case uint64(fd)+m.Limits.FD > limit:
			m.Stop = "FD headroom guard"
		case linked+unlinked > m.Limits.Disk:
			m.Stop = "owned linked/unlinked disk guard"
		case free < m.Limits.Free:
			m.Stop = "free disk guard"
		case m.Children > m.Cap:
			m.Stop = "child admission exceeded cap"
		}
		if stop, err := os.ReadFile(os.Getenv("MARIAMEM_G1_STOP")); err == nil {
			m.Stop = string(stop)
		} else if !errors.Is(err, os.ErrNotExist) {
			return err
		}
	}
	if err = m.saveLocked(); err != nil {
		return err
	}
	if m.Stop != "" {
		return errors.New(m.Stop)
	}
	return nil
}
func (m *campaign) phase(name string, started time.Time) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.Phases = append(m.Phases, campaignPhase{name, time.Since(started).Seconds()})
}

type observedDB struct {
	database
	m      *campaign
	source bool
	once   sync.Once
	err    error
}

func (d *observedDB) WaitDisconnected(ctx context.Context) error {
	start := time.Now()
	defer d.m.phase("disconnect", start)
	return d.database.WaitDisconnected(ctx)
}
func (d *observedDB) capture(ctx context.Context) (baseline, error) {
	start := time.Now()
	defer d.m.phase("capture", start)
	b, err := d.database.capture(ctx)
	if b == nil {
		return nil, err
	}
	d.m.mu.Lock()
	d.m.Baselines++
	d.m.mu.Unlock()
	return &observedBaseline{baseline: b, m: d.m}, err
}
func (d *observedDB) Close() error {
	d.once.Do(func() {
		d.err = d.database.Close()
		if d.err == nil && !d.source {
			d.m.mu.Lock()
			d.m.Children--
			d.m.mu.Unlock()
		}
	})
	return d.err
}

type observedBaseline struct {
	baseline
	m    *campaign
	once sync.Once
	err  error
}

func (b *observedBaseline) fork(ctx context.Context) (database, error) {
	if err := b.m.sample("before_fork"); err != nil {
		return nil, err
	}
	b.m.mu.Lock()
	b.m.Children++
	b.m.mu.Unlock()
	d, err := b.baseline.fork(ctx)
	if d == nil {
		b.m.mu.Lock()
		b.m.Children--
		b.m.mu.Unlock()
		return nil, err
	}
	return &observedDB{database: d, m: b.m}, err
}
func (b *observedBaseline) Close() error {
	b.once.Do(func() {
		b.err = b.baseline.Close()
		if b.err == nil {
			b.m.mu.Lock()
			b.m.Baselines--
			b.m.mu.Unlock()
		}
	})
	return b.err
}
func (m *campaign) dependencies() dependencies {
	d := production()
	start, open := d.start, d.open
	d.start = func(ctx context.Context, opts mariamem.Options) (database, error) {
		if err := m.sample("before_source"); err != nil {
			return nil, err
		}
		began := time.Now()
		db, err := start(ctx, opts)
		m.phase("start", began)
		if db == nil {
			return nil, err
		}
		return &observedDB{database: db, m: m, source: true}, err
	}
	d.open = func(dsn string, a, z int) (*sql.DB, error) {
		p, err := open(dsn, a, z)
		if p != nil {
			m.mu.Lock()
			m.Pools = append(m.Pools, p)
			m.mu.Unlock()
		}
		return p, err
	}
	return d
}

func TestFixtureCampaign(t *testing.T) {
	if os.Getenv("MARIAMEM_G1_REPORT") == "" {
		t.Skip("run through scripts/go_fixture_campaign.py")
	}
	cap, err := strconv.Atoi(os.Getenv("MARIAMEM_G1_CAP"))
	if err != nil || cap < 1 || cap > 2 {
		t.Fatal("invalid campaign cap")
	}
	parallel, err := strconv.Atoi(flag.Lookup("test.parallel").Value.String())
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(os.Getenv("MARIAMEM_G1_SQL"))
	if err != nil {
		t.Fatal(err)
	}
	limits, err := os.ReadFile(os.Getenv("MARIAMEM_G1_LIMITS"))
	if err != nil {
		t.Fatal(err)
	}
	m := &campaign{Start: time.Now(), PID: os.Getpid(), Cap: cap, Parallel: parallel, Result: "RUNNING"}
	if err = json.Unmarshal(limits, &m.Limits); err != nil {
		t.Fatal(err)
	}
	if m.Limits.Disk <= 0 || m.Limits.Free == 0 || m.Limits.FD == 0 {
		t.Fatal("missing finite guards")
	}
	var fixtures []*Fixture
	defer func() {
		began := time.Now()
		var cleanup error
		for i := len(fixtures) - 1; i >= 0; i-- {
			cleanup = errors.Join(cleanup, fixtures[i].Close())
		}
		m.CloseSeconds = time.Since(began).Seconds()
		if err := m.sample("final"); err != nil {
			t.Error(err)
		}
		m.mu.Lock()
		defer m.mu.Unlock()
		last := m.Snapshots[len(m.Snapshots)-1]
		m.Cleanup = cleanup == nil && m.Children == 0 && m.Baselines == 0 && last.Connections == 0 && last.Linked == 0 && last.Unlinked == 0
		if !m.Cleanup {
			t.Errorf("cleanup incomplete: %v %+v", cleanup, last)
		}
		m.Result = "PASS"
		if t.Failed() {
			m.Result = "FAIL"
		}
		if m.Stop != "" {
			m.Result = "STOP"
		}
		if err := m.saveLocked(); err != nil {
			t.Error(err)
		}
	}()
	if err = m.sample("baseline"); err != nil {
		t.Fatal(err)
	}
	prepareCalls := 0
	prepare := func(ctx context.Context, p *sql.DB, _ string) error {
		began := time.Now()
		defer m.phase("prepare", began)
		prepareCalls++
		// Fixed repository-authored SQL only. Not a dump reader/parser.
		for _, line := range strings.Split(string(data), "\n") {
			q := strings.TrimSpace(line)
			if q == "" || strings.HasPrefix(q, "--") {
				continue
			}
			// This pinned input has exactly one complete statement per line.
			// A semicolon in its human comment is not a SQL delimiter.
			if !strings.HasSuffix(q, ";") {
				return errors.New("fixed SQL line lacks its terminator")
			}
			if _, err := p.ExecContext(ctx, q); err != nil {
				return err
			}
		}
		return m.sample("prepared")
	}
	newOne := func() *Fixture {
		f, err := newFixture(t.Context(), Options{Prepare: prepare, MaxForks: cap}, m.dependencies())
		if f != nil {
			fixtures = append(fixtures, f)
		}
		if err != nil {
			t.Fatal(err)
		}
		return f
	}
	started := time.Now()
	f := newOne()
	m.NewSeconds = time.Since(started).Seconds()
	for batch := 0; batch < 4; batch++ {
		label := fmt.Sprintf("observed_%d", batch)
		if batch == 0 {
			label = "warmup"
		}
		began := time.Now()
		t.Run(label, func(t *testing.T) {
			for i := 0; i < 4; i++ {
				t.Run(strconv.Itoa(i), func(t *testing.T) {
					t.Parallel()
					var cleanupStart time.Time
					var row campaignCase
					row.Name = t.Name()
					t.Cleanup(func() {
						row.Cleanup = time.Since(cleanupStart).Seconds()
						m.mu.Lock()
						m.Cases = append(m.Cases, row)
						m.mu.Unlock()
						if err := m.sample("case_cleaned"); err != nil {
							t.Error(err)
						}
					})
					began := time.Now()
					p := f.DB(t)
					row.Admission = time.Since(began).Seconds()
					t.Cleanup(func() { cleanupStart = time.Now() })
					began = time.Now()
					// Hold two actual physical driver connections to observe the pool budget.
					a, err := p.Conn(t.Context())
					if err != nil {
						t.Fatal(err)
					}
					defer a.Close()
					b, err := p.Conn(t.Context())
					if err != nil {
						t.Fatal(err)
					}
					defer b.Close()
					if err = m.sample("case_two_connections"); err != nil {
						t.Fatal(err)
					}
					for table := 0; table < 64; table++ {
						var id int
						var payload string
						q := fmt.Sprintf("SELECT id,HEX(payload) FROM resource_%02d WHERE id=?", table)
						if err = a.QueryRowContext(t.Context(), q, 1).Scan(&id, &payload); err != nil || id != 1 || payload != "73656564" {
							t.Fatalf("seed %d/%s: %v", id, payload, err)
						}
					}
					var n int
					if err = a.QueryRowContext(t.Context(), "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='resource_00'").Scan(&n); err != nil || n != 2 {
						t.Fatalf("schema %d: %v", n, err)
					}
					for _, q := range []string{"UPDATE resource_00 SET payload=0x6368696c64", "ALTER TABLE resource_00 ADD changed INT"} {
						if _, err = a.ExecContext(t.Context(), q); err != nil {
							t.Fatal(err)
						}
					}
					row.SQL = time.Since(began).Seconds()
				})
			}
		})
		m.Batches = append(m.Batches, campaignBatch{label, time.Since(began).Seconds()})
		if err = m.sample("batch_done"); err != nil {
			t.Fatal(err)
		}
	}
	if prepareCalls != 1 {
		t.Fatal("preparation repeated for test cases")
	}
	for retained := 1; retained <= 3; retained++ {
		if retained > 1 {
			newOne()
		}
		runtime.GC()
		if err = m.sample(fmt.Sprintf("retained_%d", retained)); err != nil {
			t.Fatal(err)
		}
		// Deliberate observation window for the external RSS/available-memory sampler.
		time.Sleep(750 * time.Millisecond)
		if err = m.sample(fmt.Sprintf("retained_end_%d", retained)); err != nil {
			t.Fatal(err)
		}
	}
}
