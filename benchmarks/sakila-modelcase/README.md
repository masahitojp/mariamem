# Sakila audit model-case benchmark

The same 100 application tests (50 reads, 50 writes) use the same SQL schema, migration statements, seed and assertions in each mode. The runner compiles one Go test binary and runs a fresh process with `-test.parallel=8`; a direct `go test` invocation without backend selection skips the suite.

The execution models draw on [pgmem's model-case benchmark](https://shibukawa.github.io/pgmem/benchmarks/#model-case-suite-one-test-suite-two-execution-models) and use a [Sakila-derived rental workflow](https://dev.mysql.com/doc/sakila/en/sakila-usage.html). The seed starts with 599 customers, 500 films, 500 inventory items, two stores, two staff members, 40 rentals, 40 payments and 40 insert audit records (1,723 rows). Two triggers record a new rental and a change to a rental's return date.

| Group | Scenarios |
|---|---|
| 5 × 10 reads | Customer rentals, inventory/catalog join, customer payments, store sales and rental history |
| 5 × 10 writes | Checkout, return and duplicate suppression, rollback, reopening a return and payment adjustment |

| Mode | Start and isolation |
|---|---|
| mariamem | Start one embedded MariaDB, seed it and take a Snapshot. The 50 read cases share one reader Fork and the 50 write cases each get a separate writer Fork. Both groups use Go's parallel scheduler, and the reader is checked again after the writers. |
| Testcontainers, one shared server | Start one official MySQL container per suite using Testcontainers Go. Run reads concurrently, then run writes sequentially and reset the transactional tables before each writer. |
| MySQL, one shared server | Use one already-running MySQL endpoint. The suite creates and drops a dedicated randomly named database and uses the same shared-server reset as Testcontainers. |
| `docker run`, one shared server | Start one official MySQL container per suite using the Docker CLI. Use the same shared-server test and reset path. |

The three shared modes use the same MySQL version in the recorded campaign. The started-on-demand containers use the same image and defaults. The already-running endpoint for that campaign is also a container from that image with its startup outside the timer. A native or remote endpoint can instead be supplied with the DSN. The benchmark measures actual workflow and cleanup costs, including the different isolation guarantees, database implementations and startup policies. Reported phase spans may overlap. The reset restores the logical rows and values inspected by the tests and leaves the server's auto-increment counters running.

The ten variants in each scenario use different SQL inputs. Read cases vary customer/history row counts, catalog ranges and payment totals. Write cases vary the targeted rows, return dates or payment amounts. The return scenario repeats a single UPDATE within each case to check that a same-value update creates no duplicate audit entry.

## Recorded comparison

2026-11-22 JST, macOS 27.2.1 (26B131) arm64, Go 1.27.4, Docker Desktop server 29.9.3, Testcontainers Go 0.40.0 and Go MySQL driver 1.10.1. mariamem source commit `3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d`. The Linux arm64 MySQL image ID was `sha256:ae113cae2661960c4665a586812ae8150b2a133772a9f3ad63d1f1ae4f9e8ce7`. All three shared arms reported MySQL 8.4.13 and matching sampled settings. The embedded server reported `12.3.4-MariaDB-embedded`.

All 24 suites passed the same 100 case names, including one excluded warm-up per mode. Reader and writer execution overlapped in all five measured embedded suites.

| Mode | Ready, median | Full suite process, median | Observed full suite range |
|---|---:|---:|---:|
| mariamem | 52.18 ms | **541.87 ms** | 460.62–554.65 ms |
| Testcontainers, one shared server | 6,045.89 ms | **7,652.18 ms** | 7,520.06–7,682.24 ms |
| MySQL, one already-running shared server | 2.10 ms | **616.98 ms** | 591.11–637.55 ms |
| Docker CLI, one shared server | 6,009.40 ms | **6,791.26 ms** | 6,714.58–6,838.92 ms |

Ready ends at the first successful SQL version query. Full suite measures wall time from test-process launch through exit and includes initialization of the two on-demand MySQL modes. Image downloads, compilation and startup of the already-running endpoint are outside the interval. The MySQL image enabled binlogging and set `sync_binlog=1`; the embedded server had binlogging off. The Docker arms run inside the Linux VM.

## Reproduce

Use an already-running MySQL 8.4 server reachable over TCP. The supplied account needs permission to create/drop a dedicated database, create triggers and perform the fixture DDL/DML. The other two server modes require Docker. For the recorded arm64 comparison, the pinned MySQL image is `mysql@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902`. Pull that and `testcontainers/ryuk:0.13.0` before timing. Docker Desktop may need `DOCKER_HOST` from the selected Docker context and `TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock`.

Build from the repository root at the runtime commit you intend to measure. The module's local replacement links the checked-out runtime. For the recorded comparison, use a clean export or checkout of `3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d` and copy this benchmark's four Go files and module files into its `benchmarks/sakila-modelcase` directory.

```sh
source_commit=$(python3 scripts/git_identity.py inspect HEAD | python3 -c 'import json,sys; print(json.load(sys.stdin)["source_commit"])')
trial="$PWD/build/sakila-modelcase"
mkdir -p "$trial"
(
  cd benchmarks/sakila-modelcase
  go test -c -ldflags "-X github.com/masahitojp/mariamem/benchmarks/sakila-modelcase.sourceCommit=$source_commit" -o "$trial/sakila.test"
)
# Set SAKILA_MYSQL_DSN in the environment for the already-running endpoint.
image=mysql@sha256:a81d043930e51745522bd5c430961cf8286f0a23f0a9a2a6e0108f7ea71b0902
python3 benchmarks/sakila-modelcase/run.py run "$trial/sakila.test" "$image" > "$trial/samples.jsonl"
python3 benchmarks/sakila-modelcase/run.py summarize "$trial/samples.jsonl"
```

For a single embedded correctness run:

```sh
(cd benchmarks/sakila-modelcase && go test -count=1 -parallel=8 -run '^TestSakila$' -args -sakila.backend=mariamem)
```
