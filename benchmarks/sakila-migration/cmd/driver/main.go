package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"net"
	"os"
	"os/exec"
	"strconv"
	"strings"
	"time"

	"github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem/benchmarks/sakila-migration/internal/trace"
	"github.com/testcontainers/testcontainers-go"
)

var runtimeCommit string

type suiteSample struct {
	OriginMonoNS       int64 `json:"origin_mono_ns"`
	OriginNS           int64 `json:"origin_ns"`
	testStarted        time.Time
	testStartedMonoNS  int64
	TestFinishedMonoNS int64           `json:"test_finished_mono_ns"`
	ImageID            string          `json:"image_id"`
	Mode               string          `json:"mode"`
	Trial              int             `json:"trial"`
	ReadyMS            float64         `json:"ready_ms"`
	ProcessMS          float64         `json:"process_ms"`
	ThroughTestsMS     float64         `json:"through_tests_ms"`
	WithShutdownMS     float64         `json:"with_shutdown_ms"`
	Native             *sample         `json:"native,omitempty"`
	Metrics            json.RawMessage `json:"metrics"`
}

type caseID struct {
	Kind string
	Name string
}

func invokeSuite(ctx context.Context, bin, backend, dsn string, r *suiteSample, expected map[caseID]bool) error {
	file, err := os.CreateTemp("", "sakila-metrics-*.json")
	if err != nil {
		return err
	}
	defer os.Remove(file.Name())
	if err := file.Close(); err != nil {
		return err
	}
	cmd := exec.CommandContext(ctx, bin, "-test.run=^TestSakila$", "-test.parallel=8",
		"-test.timeout=1m", "-sakila.backend="+backend, "-sakila.metrics="+file.Name())
	if dsn != "" {
		cmd.Env = append(os.Environ(), "SAKILA_MYSQL_DSN="+dsn)
	}
	start := time.Now()
	r.testStarted = start
	r.testStartedMonoNS = trace.MonotonicNS()
	output, err := cmd.CombinedOutput()
	r.TestFinishedMonoNS = trace.MonotonicNS()
	r.ProcessMS = millis(time.Duration(r.TestFinishedMonoNS - r.testStartedMonoNS))
	if err != nil {
		return fmt.Errorf("%w\n%s", err, output)
	}
	raw, err := os.ReadFile(file.Name())
	if err != nil {
		return err
	}
	var m trace.Report
	if err := json.Unmarshal(raw, &m); err != nil {
		return err
	}
	if m.Backend != backend || m.SourceCommit != runtimeCommit || m.Reads != 0 || m.Writes != 8 || m.Parallel != 8 ||
		!strings.HasPrefix(m.Version, "12.3.4-MariaDB-") {
		return fmt.Errorf("unexpected suite metadata: %s %s %s %d/%d/%d", m.Backend, m.SourceCommit, m.Version, m.Reads, m.Writes, m.Parallel)
	}
	cases := make(map[caseID]bool)
	for _, p := range m.Phases {
		switch p.Name {
		case "ready":
			if backend == "mariamem" {
				r.ReadyMS = millis(time.Duration(m.StartMonoNS-r.testStartedMonoNS)) + p.To
			}
		case "read", "write":
			key := caseID{p.Name, p.Case}
			if cases[key] {
				return fmt.Errorf("duplicate case %v", key)
			}
			cases[key] = true
		}
	}
	if len(cases) != 8 {
		return fmt.Errorf("only %d unique cases", len(cases))
	}
	if len(expected) == 0 {
		for key := range cases {
			expected[key] = true
		}
	}
	for key := range cases {
		if !expected[key] {
			return fmt.Errorf("unexpected case %v", key)
		}
	}
	r.Metrics = raw
	return nil
}

func millis(d time.Duration) float64 {
	return float64(d) / float64(time.Millisecond)
}

func main() {
	if len(os.Args) != 8 {
		log.Fatal("usage: controller template disk-root test-binary image network mode trial")
	}
	template, disk, bin, image, network, mode := os.Args[1], os.Args[2], os.Args[3], os.Args[4], os.Args[5], os.Args[6]
	trial, err := strconv.Atoi(os.Args[7])
	if err != nil {
		log.Fatal(err)
	}
	r := suiteSample{Mode: mode, Trial: trial, ImageID: image}
	ctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
	defer cancel()
	expected := make(map[caseID]bool)
	for variant := 1; variant <= 8; variant++ {
		expected[caseID{"write", fmt.Sprintf("late_fee/%02d", variant)}] = true
	}
	switch mode {
	case "mariamem":
		err = invokeSuite(ctx, bin, "mariamem", "", &r, expected)
		r.OriginNS = r.testStarted.UnixNano()
		r.OriginMonoNS = r.testStartedMonoNS
		r.ThroughTestsMS = r.ProcessMS
		r.WithShutdownMS = r.ProcessMS
	case "native":
		ready := sample{Mode: mode, Trial: trial}
		err = native(ctx, &ready, template, disk, "16777216", func(dsn string) error {
			appDSN, drop, err := prepareApp(ctx, dsn)
			if err != nil {
				return err
			}
			defer drop()
			ready.ReadyMS = millis(time.Since(ready.started))
			err = invokeSuite(ctx, bin, "mysql", appDSN, &r, expected)
			r.ThroughTestsMS = millis(time.Duration(r.TestFinishedMonoNS - ready.startedMonoNS))
			return err
		})
		if err == nil {
			r.ReadyMS = ready.ReadyMS
			r.WithShutdownMS = millis(ready.stopped.Sub(ready.started))
			r.OriginNS = ready.started.UnixNano()
			r.OriginMonoNS = ready.startedMonoNS
			r.Native = &ready
		}
	case "testcontainers", "docker":
		err = managed(ctx, image, network, mode, bin, &r, expected)
	default:
		err = fmt.Errorf("unknown mode %s", mode)
	}
	if err != nil {
		log.Fatalf("%s trial %d: %v", mode, trial, err)
	}
	if err := json.NewEncoder(os.Stdout).Encode(r); err != nil {
		log.Fatal(err)
	}
}

func managed(ctx context.Context, image, network, mode, bin string, r *suiteSample, expected map[caseID]bool) (err error) {
	name := fmt.Sprintf("%s-%s-%d", network, mode, r.Trial)
	const password = "local-benchmark-only"
	env := map[string]string{"MARIADB_ROOT_PASSWORD": password, "MARIADB_DATABASE": "sakila_app"}
	args := []string{"--skip-log-bin", "--innodb-buffer-pool-size=16M"}
	start := time.Now()
	r.OriginNS = start.UnixNano()
	r.OriginMonoNS = trace.MonotonicNS()
	defer func() { r.WithShutdownMS = millis(time.Since(start)) }()
	if mode == "testcontainers" {
		request := testcontainers.ContainerRequest{
			Image: image, Name: name, Env: env, Networks: []string{network},
			Cmd:   append(args, "--innodb-flush-log-at-trx-commit=0"),
			Tmpfs: map[string]string{"/var/lib/mysql": "rw,size=512m"},
		}
		container, startErr := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
			ContainerRequest: request, Started: true,
		})
		if container != nil {
			defer func() {
				cleanup, cancel := context.WithTimeout(context.Background(), 30*time.Second)
				defer cancel()
				if stopErr := container.Terminate(cleanup); stopErr != nil {
					err = errors.Join(err, stopErr)
				}
			}()
		}
		if startErr != nil {
			return startErr
		}
	} else {
		launch := []string{"run", "-d", "--name", name, "--network", network,
			"-e", "MARIADB_ROOT_PASSWORD", "-e", "MARIADB_DATABASE", image}
		cmd := exec.CommandContext(ctx, "docker", append(launch, args...)...)
		cmd.Env = append(os.Environ(), "MARIADB_ROOT_PASSWORD="+password, "MARIADB_DATABASE=sakila_app")
		defer func() {
			cleanup, cancel := context.WithTimeout(context.Background(), 30*time.Second)
			defer cancel()
			if output, stopErr := exec.CommandContext(cleanup, "docker", "rm", "-fv", name).CombinedOutput(); stopErr != nil && err == nil {
				err = fmt.Errorf("remove docker server: %w: %s", stopErr, output)
			}
		}()
		if output, err := cmd.CombinedOutput(); err != nil {
			return fmt.Errorf("docker run: %w: %s", err, output)
		}
	}
	cfg := mysql.NewConfig()
	cfg.Net, cfg.Addr, cfg.User, cfg.Passwd, cfg.DBName = "tcp", net.JoinHostPort(name, "3306"), "root", password, "sakila_app"
	pool, err := open(cfg)
	if err != nil {
		return err
	}
	defer pool.Close()
	ready := sample{Mode: mode, Trial: r.Trial}
	if err := waitSQL(ctx, pool, start, &ready); err != nil {
		return err
	}
	r.ReadyMS = ready.ReadyMS
	if err := invokeSuite(ctx, bin, "mysql", cfg.FormatDSN(), r, expected); err != nil {
		return err
	}
	r.ThroughTestsMS = millis(time.Duration(r.TestFinishedMonoNS - r.OriginMonoNS))
	return nil
}
