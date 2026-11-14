// Command alternatives measures pgmem next to the other common ways of
// getting a PostgreSQL for tests: a plain docker run, testcontainers-go
// and a devbox (nix) installed PostgreSQL. One invocation measures one
// target in a fresh process and prints one JSON object; run.sh repeats
// it and summarize.py aggregates the samples.
//
//	go run . -target pgmem|docker|testcontainers|devbox
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"
)

// Result is one run of one target. Durations are in milliseconds,
// memory values are in mebibytes.
type Result struct {
	Target           string    `json:"target"`
	StartupMS        float64   `json:"startup_ms"`
	SetupMS          float64   `json:"setup_ms"`
	SimpleQueryUS    float64   `json:"simple_query_us"`
	DialQueryUS      float64   `json:"dial_query_us,omitempty"`
	HeavyQueryMS     float64   `json:"heavy_query_ms"`
	IsolateMS        float64   `json:"isolate_ms"`
	MemIdleMB        float64   `json:"mem_idle_mb"`
	MemAfterMB       float64   `json:"mem_after_mb"`
	ServiceIdleMB    float64   `json:"service_idle_mb,omitempty"`
	ServiceAfterMB   float64   `json:"service_after_mb,omitempty"`
	RSSIdleMB        float64   `json:"rss_idle_mb,omitempty"`
	ContainerMB      float64   `json:"container_mb,omitempty"`
	ContainerAfterMB float64   `json:"container_after_mb,omitempty"`
	ProcessMB        float64   `json:"process_mb,omitempty"`
	VMGrowthMB       float64   `json:"vm_growth_mb,omitempty"`
	VMTotalMB        float64   `json:"vm_total_mb,omitempty"`
	ProcessAfterMB   float64   `json:"process_after_mb,omitempty"`
	VMGrowthAfterMB  float64   `json:"vm_growth_after_mb,omitempty"`
	FreshVM          bool      `json:"fresh_vm,omitempty"`
	Version          string    `json:"version"`
	Time             time.Time `json:"time"`
}

// target is what each backend implements.
// Host is the measured host-footprint reading; for container targets it is
// VM net change plus benchmark-process growth, and can shrink when the VM
// reclaims memory. Service is backend usage plus separately measured runner
// growth, which stays comparable when the VM changes its allocation.
type memory struct {
	Host, RSS, Process, VMGrowth, Container, VMTotal, Service float64
}

type target interface {
	// start boots a server and returns once SELECT 1 succeeds on url().
	start(ctx context.Context) error
	url() string
	// isolate gives one test an isolated copy of the prepared database,
	// runs fn against its URL and discards it.
	prepareIsolation(ctx context.Context) error
	isolate(ctx context.Context, fn func(url string) error) error
	mem(ctx context.Context) (memory, error)
	stop(ctx context.Context)
}

const (
	benchRows  = 1000
	orderRows  = 10000
	simpleN    = 3000
	simpleWarm = 300
	heavyN     = 3
	isolateN   = 20
)

const schema = `
CREATE TABLE bench (id int PRIMARY KEY, v text NOT NULL);
INSERT INTO bench SELECT i, md5(i::text) FROM generate_series(1, 1000) i;
CREATE TABLE users (id bigserial PRIMARY KEY, name text NOT NULL, email text UNIQUE);
CREATE TABLE orders (id bigserial PRIMARY KEY, user_id bigint NOT NULL REFERENCES users(id), amount int NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX orders_user_id ON orders(user_id);
INSERT INTO users(name, email) SELECT 'user' || i, 'user' || i || '@example.com' FROM generate_series(1, 1000) i;
INSERT INTO orders(user_id, amount) SELECT 1 + (i % 1000), i % 997 FROM generate_series(1, 10000) i;
`

const heavyQuery = `SELECT count(*) FROM (SELECT md5(i::text) AS h FROM generate_series(1, 200000) i ORDER BY h) t`

func main() {
	name := flag.String("target", "pgmem", "pgmem | docker | testcontainers | devbox")
	image := flag.String("image", "postgres:18-alpine", "image for docker and testcontainers")
	devboxDir := flag.String("devbox", "devbox", "directory with devbox.json")
	freshVM := flag.Bool("fresh-vm", false, "docker and testcontainers: restart OrbStack and count benchmark-process plus VM memory growth")
	flag.Parse()

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
	defer cancel()

	var t target
	switch *name {
	case "pgmem":
		t = &pgmemTarget{}
	case "docker":
		t = &dockerTarget{image: *image, fresh: *freshVM}
	case "testcontainers":
		t = &tcTarget{image: *image, fresh: *freshVM}
	case "devbox":
		t = &devboxTarget{dir: *devboxDir}
	default:
		fatal(fmt.Errorf("unknown target %q", *name))
	}
	r, err := measure(ctx, *name, t)
	if r != nil {
		r.FreshVM = *freshVM && (*name == "docker" || *name == "testcontainers")
	}
	t.stop(context.Background())
	if err != nil {
		fatal(err)
	}
	json.NewEncoder(os.Stdout).Encode(r)
}

func measure(ctx context.Context, name string, t target) (*Result, error) {
	r := &Result{Target: name, Time: time.Now().UTC()}

	if p, ok := t.(preparer); ok {
		if err := p.prepare(ctx); err != nil {
			return nil, fmt.Errorf("prepare: %w", err)
		}
	}
	begin := time.Now()
	if err := t.start(ctx); err != nil {
		return nil, fmt.Errorf("start: %w", err)
	}
	r.StartupMS = ms(time.Since(begin))

	conn, err := pgx.Connect(ctx, t.url())
	if err != nil {
		return nil, err
	}
	if err := conn.QueryRow(ctx, "SHOW server_version").Scan(&r.Version); err != nil {
		return nil, err
	}
	begin = time.Now()
	if _, err := conn.Exec(ctx, schema); err != nil {
		return nil, fmt.Errorf("schema: %w", err)
	}
	r.SetupMS = ms(time.Since(begin))
	conn.Close(ctx)

	idle, err := t.mem(ctx)
	if err != nil {
		return nil, fmt.Errorf("memory: %w", err)
	}
	r.MemIdleMB, r.RSSIdleMB, r.ContainerMB, r.ProcessMB, r.VMGrowthMB, r.VMTotalMB = idle.Host, idle.RSS, idle.Container, idle.Process, idle.VMGrowth, idle.VMTotal
	r.ServiceIdleMB = idle.Service

	conn, err = pgx.Connect(ctx, t.url())
	if err != nil {
		return nil, err
	}
	if r.SimpleQueryUS, err = simpleQuery(ctx, conn); err != nil {
		return nil, err
	}
	var heavy []float64
	for i := 0; i <= heavyN; i++ {
		begin := time.Now()
		var n int
		if err := conn.QueryRow(ctx, heavyQuery).Scan(&n); err != nil {
			return nil, err
		}
		if i > 0 { // first run is warm-up
			heavy = append(heavy, ms(time.Since(begin)))
		}
	}
	r.HeavyQueryMS = median(heavy)
	conn.Close(ctx)

	if d, ok := t.(dialer); ok {
		if r.DialQueryUS, err = d.dialQuery(ctx); err != nil {
			return nil, err
		}
	}

	if err := t.prepareIsolation(ctx); err != nil {
		return nil, fmt.Errorf("prepare isolation: %w", err)
	}
	var iso []float64
	for i := 0; i < isolateN; i++ {
		begin := time.Now()
		err := t.isolate(ctx, func(url string) error {
			c, err := pgx.Connect(ctx, url)
			if err != nil {
				return err
			}
			defer c.Close(ctx)
			var n int
			return c.QueryRow(ctx, "SELECT count(*) FROM orders JOIN users ON users.id = orders.user_id").Scan(&n)
		})
		if err != nil {
			return nil, fmt.Errorf("isolate: %w", err)
		}
		iso = append(iso, ms(time.Since(begin)))
	}
	r.IsolateMS = median(iso)

	after, err := t.mem(ctx)
	if err != nil {
		return nil, fmt.Errorf("memory: %w", err)
	}
	r.MemAfterMB, r.ProcessAfterMB, r.VMGrowthAfterMB = after.Host, after.Process, after.VMGrowth
	r.ServiceAfterMB, r.ContainerAfterMB = after.Service, after.Container
	return r, nil
}

// preparer is implemented by targets with untimed work before start.
type preparer interface {
	prepare(ctx context.Context) error
}

type dialer interface {
	dialQuery(ctx context.Context) (float64, error)
}

func simpleQuery(ctx context.Context, conn *pgx.Conn) (float64, error) {
	var v string
	for i := 0; i < simpleWarm; i++ {
		if err := conn.QueryRow(ctx, "SELECT v FROM bench WHERE id = $1", 1+i%benchRows).Scan(&v); err != nil {
			return 0, err
		}
	}
	begin := time.Now()
	for i := 0; i < simpleN; i++ {
		if err := conn.QueryRow(ctx, "SELECT v FROM bench WHERE id = $1", 1+i%benchRows).Scan(&v); err != nil {
			return 0, err
		}
	}
	return float64(time.Since(begin).Microseconds()) / simpleN, nil
}

// waitReady polls url until SELECT 1 succeeds.
func waitReady(ctx context.Context, url string) error {
	for {
		c, err := pgx.Connect(ctx, url)
		if err == nil {
			var one int
			err = c.QueryRow(ctx, "SELECT 1").Scan(&one)
			c.Close(ctx)
			if err == nil {
				return nil
			}
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("server not ready: %w (last error %v)", ctx.Err(), err)
		case <-time.After(10 * time.Millisecond):
		}
	}
}

// templateIsolation is the usual way to isolate tests on a real server:
// the prepared database becomes a template and each test gets a copy.
func templateIsolation(ctx context.Context, adminURL, dbURL func(db string) string, n *int, fn func(string) error) error {
	*n++
	db := fmt.Sprintf("t%d", *n)
	admin, err := pgx.Connect(ctx, adminURL("postgres"))
	if err != nil {
		return err
	}
	defer admin.Close(ctx)
	if _, err := admin.Exec(ctx, "CREATE DATABASE "+db+" TEMPLATE app"); err != nil {
		return err
	}
	if err := fn(dbURL(db)); err != nil {
		return err
	}
	_, err = admin.Exec(ctx, "DROP DATABASE "+db)
	return err
}

func run(ctx context.Context, name string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	out, err := cmd.Output()
	if err != nil {
		if ee, ok := err.(*exec.ExitError); ok {
			return "", fmt.Errorf("%s %s: %v: %s", name, strings.Join(args, " "), err, ee.Stderr)
		}
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// dockerMemMB reads the container's memory usage from docker stats.
func dockerMemMB(ctx context.Context, id string) (float64, error) {
	out, err := run(ctx, "docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", id)
	if err != nil {
		return 0, err
	}
	used := strings.TrimSpace(strings.SplitN(out, "/", 2)[0])
	units := []struct {
		suffix string
		mb     float64
	}{{"GiB", 1024}, {"MiB", 1}, {"KiB", 1.0 / 1024}, {"B", 1.0 / 1024 / 1024}}
	for _, u := range units {
		if strings.HasSuffix(used, u.suffix) {
			v, err := strconv.ParseFloat(strings.TrimSuffix(used, u.suffix), 64)
			return v * u.mb, err
		}
	}
	return 0, fmt.Errorf("cannot parse docker stats %q", out)
}

// rssMB sums the resident set of the given pids (ps reports KiB).
func rssMB(ctx context.Context, pids ...int) (float64, error) {
	var total float64
	for _, pid := range pids {
		out, err := run(ctx, "ps", "-o", "rss=", "-p", strconv.Itoa(pid))
		if err != nil {
			continue // a short-lived child (autovacuum worker) exited meanwhile
		}
		kb, err := strconv.ParseFloat(strings.TrimSpace(out), 64)
		if err != nil {
			return 0, err
		}
		total += kb / 1024
	}
	return total, nil
}

func ms(d time.Duration) float64 { return float64(d.Microseconds()) / 1000 }

func median(v []float64) float64 {
	if len(v) == 0 {
		return 0
	}
	s := append([]float64(nil), v...)
	sort.Float64s(s)
	return s[len(s)/2]
}

func fatal(err error) {
	fmt.Fprintln(os.Stderr, err)
	os.Exit(1)
}
