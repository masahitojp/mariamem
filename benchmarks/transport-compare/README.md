# mariamem main / pgmem1.18.2: database/sql TCP and Pipe

2026-11-05, Apple M1 / macOS27.2 arm64, Go1.26.10, GOMAXPROCS8,
GOGC100. Three fresh processes x500 operations/cell; all48 cells PASS.
**Within this workload, mariamem connects faster; pgmem executes repeated SQL
faster.** This is driver + protocol + database cost, not a pure-wire benchmark
or a claim about general application/fixture throughput.

## Latency results

Medians of three process-level per-operation averages, in microseconds:

| Workload | mariamem TCP | pgmem TCP | mariamem Pipe | pgmem Pipe |
| --- | ---: | ---: | ---: | ---: |
| Connect + handshake + Ping + client close |339.11|1155.56|156.98|796.14|
| Warm SELECT1 |100.64|74.29|56.29|12.12|
| Warm explicit prepared SELECT parameter + 1 |102.40|46.49|59.39|9.43|
|64 rows x128-byte payload |885.70|89.63|672.08|49.93|

For Pipe, pgmem's elapsed medians are about4.6x shorter for SELECT1,6.3x for
prepared execution and13.5x for this result transfer. mariamem's connect/Ping
median is about5.1x shorter. These ratios compare medians, not query percentiles.
They do not identify which driver/engine/protocol component explains the gap.

## Go allocations

B/op medians (allocated bytes, not retained memory/RSS):

| Workload | mariamem TCP | pgmem TCP | mariamem Pipe | pgmem Pipe |
| --- | ---: | ---: | ---: | ---: |
| Connect/Ping |18718|328795|20019|328582|
| SELECT1 |9142|906|9944|843|
| Prepared1 |9536|1284|10371|1221|
| Result64x128 |99245|12497|108204|12433|

Allocation counts and every process observation are retained in results.csv/JSON.
No RSS, CPU, startup/Fork, end-to-end fixture, concurrency, p95 or confidence
interval measurement was performed. This finite run does not change defaults or
approve a new performance/engine implementation project.

## Fairness and known differences

- Both use database/sql, one open/idle connection for steady work, one open/zero
  idle for connect/Ping, serial iterations and default driver timeout settings.
  An iteration of Ping on an idle0 pool includes client close; protocol startup,
  authentication and Ping implementations naturally differ between drivers.
- mysql1.9.3 disables interpolation. pgx5.11.0 uses SimpleProtocol for ordinary
  SELECTs, avoiding implicit statement-cache effects. Both use explicit sql.Prepare
  for the prepared case; pgx's named prepared statements override SimpleProtocol
  (verified in pinned pgx conn.go preparedStatements lookup and stdlib Stmt path).
  Parameter spelling is `?` versus `$1`; both compute41 +1 and assert42.
- Both create the same table with64 fixed ASCII VARCHAR(128) values and execute
  exactly `SELECT payload FROM transport_rows ORDER BY id`. Results are fully
  scanned, setup checks contents/count and timed scans check row count/errors.
  Default MariaDB/PostgreSQL storage/configuration are retained, not normalized
  into an artificial shared engine configuration.
- Setup uses the server's existing system database (`mysql` / `postgres`) so no
  extra database switch is introduced. Root startup, schema/seed, statement
  preparation and final server close are outside operation timers. No Fork.
- Engine order is maria/pgmem, pgmem/maria, maria/pgmem across processes; transport
  order reverses in the middle process. A server is closed before the next
  engine starts. Maria WaitDisconnected is used outside timing; pgmem exposes
  no equivalent in this pinned API, so no equal physical-retirement boundary or
  shutdown-speed comparison is claimed. Both SQL pools are closed per cell.
- mariamem is rerun in this SAME cohort. The earlier light run used a sequence
  generator and different connection-pool configuration, so do not merge its
  values into these rows or attribute differences to a product improvement.

## Inputs and reproduction

mariamem product baseline_source_commit:
`676515eb9244fc501b5a600791b0cf0a6174fecd`.
pgmem release v1.18.2 source_commit:
`a61005d37d01e6671f814fe8ca828222e8147df4`.
Its annotated tag_object_sha is
`145e5d2fc70983b89a4bdd8438e547fcd60244ed`, a distinct object.
The pin is in release/baselines/pgmem-v1.18.2.json. scripts/git_identity.py
validated the actual tag object/name and commit before build, and the upstream
checkout remained clean. metadata.json records the harness source and executable
SHA256; this test binary has no VCS stamp. Later collector/results are not Go
executable inputs. Product/guest/generated source, version and CI are unchanged.

The nested Go module isolates pgmem/pgx dependencies from the product module.
It replaces mariamem with the repository root and pgmem with an owned clone at
`TASK_WORK/temp/pgmem-source`. Check out the pinned release there, verify the
release pin, tidy this nested module with its lockfile, and inspect the harness
source using git_identity.py before compilation. With Go1.26.10:

```sh
# From benchmarks/transport-compare, with an owned cache and absolute paths:
go test -p 1 -vet=off -c -o TASK_WORK/temp/compare.test
# From the repository root:
python scripts/experiment_disk.py --work-dir TASK_WORK \
  --min-free-gib 8 --budget-gib 6 --timeout 300 -- \
  python benchmarks/transport-compare/run.py TASK_WORK
```

Build used GOMEMLIMIT3GiB/GOGC50; run.py clears the limit and sets GOGC100 for
measurement. Workspace budget6GiB, reserve8GiB, active-work budget30 minutes.
The collector stops on any error/missing cell, with no retries. Compact source,
lockfiles, all48 observations and calculations are pushed; owned clones, caches,
compiler output and worktree are then disposable. No CI or broad runtime
qualification is added for this local measurement.
