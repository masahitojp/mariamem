# Model-case suite

The same test suite on two execution models, with every node timed, for
the comparison on the top page of the website.

`store/` is the project under test: the data layer of a small shop
(database/sql, five SQL migrations with a trigger and a view, master data
of 20 categories, 500 products and 1,000 users) and 70 tests as tables of
cases: five read-only scenarios with ten cases each and five writing
scenarios with four cases each. Every test starts from the same 40 sample
orders. `go test ./...` runs it on pgmem like any other suite.

`store/fixture_test.go` picks the model:

- **pgmem** (default): boot in the test process, import, one snapshot;
  read-only tests share the template server itself, loaded with the sample
  data once after the snapshot; every writing test forks its own copy. All
  tests are `t.Parallel()`.
- **shared server** (`MODELCASE_DSN` set): import into the shared
  database; read-only tests run in parallel on it, writing tests run one
  at a time, each after a reset (TRUNCATE of the transactional tables,
  stock and prices restored) and a fresh load of the sample data.

`MODELCASE_TRACE=path` makes TestMain write every node as a span
(`internal/trace`). `cmd/driver` starts the external server for the
testcontainers, devbox and docker targets, times its boot until `SELECT 1` succeeds, runs
the compiled test binary, and prints one JSON line per run with the boot
time, the binary's wall clock and the spans. `run.sh` ties it together:

```sh
RUNS=5 ./run.sh                    # pgmem, Testcontainers, devbox and docker
TARGETS="pgmem devbox" ./run.sh    # without Docker
```

It writes `results/raw.jsonl`, `results/summary.json` (the run with the
median total per model, its spans, per-node sums and the total's range)
and copies the summary to `website/src/data/modelcase.json`, which
`website/src/components/ModelCaseChart.astro` renders. The first run of
each target is an untimed warm-up: the first execution of a freshly built
binary pays for page-in and code signing.

testcontainers uses testcontainers-go's postgres module on
`postgres:18-alpine` in memory (PGDATA on tmpfs, fsync off), one driver process per run so
every run starts Ryuk as a fresh test process would; devbox uses `bench/alternatives/devbox` (PostgreSQL 18 from nix) run
directly with `pg_ctl` on a cluster initialized once before timing; docker
uses `postgres:18-alpine` with `docker run`, disk-backed like
`bench/alternatives`.
