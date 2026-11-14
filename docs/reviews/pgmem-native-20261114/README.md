# Actual pgmem official benchmark — 2026-11-14

The unmodified shibukawa/pgmem v1.18.2 benchmark successfully ran on this Mac.
This measures pgmem itself, not the preceding MariaDB adaptation. No mariamem
runtime or production inputs changed. These are local reference measurements;
no adoption or release decision is implied.

## Inputs and conditions

- Upstream: https://github.com/shibukawa/pgmem/tree/a61005d37d01e6671f814fe8ca828222e8147df4
- Release v1.18.2; `source_commit`: `a61005d37d01e6671f814fe8ca828222e8147df4`.
- Annotated `tag_object_sha`: `145e5d2fc70983b89a4bdd8438e547fcd60244ed`.
- Identity verified with `scripts/git_identity.py` before compilation; the
  alternatives binary also stamps the same commit and `vcs.modified=false`.
- Apple M1, 8 logical CPUs, 16 GiB RAM, darwin/arm64; Go 1.27.4, default build
  settings, CGO enabled. The alternatives module requires Go 1.27.
- Official code and Go module files remained clean before and after execution.
  Source hashes, resolved module versions and raw samples are adjacent.
- Builds completed before timing. Five sequential fresh processes; no samples
  discarded. A separate official Go microbenchmark ran three repetitions per
  benchmark with `-benchtime=1s` and no ordinary tests.
- Background work was present: another experiment's guest-build monitor and
  Docker/virtualization processes were active. No other user's work was stopped.
  The disk monitor was also active. This is not a quiet-machine comparison.

## Official alternatives harness (five runs)

Median across five harness outputs; range is across those outputs. `_ms` is
milliseconds, `_us` microseconds; memory `_mb` is MiB. Each harness output itself
averages 3,000 simple queries after 300 warmups, takes the median of three heavy
queries after one warmup, and the median of 20 isolation cycles.

| Official field | Median | Min–max |
| --- | ---: | ---: |
| `startup_ms` | 125.202 | 121.997–171.939 |
| `setup_ms` | 134.363 | 127.660–144.841 |
| `simple_query_us` | 107.901 | 74.451–112.897 |
| `dial_query_us` | 24.136 | 23.635–26.161 |
| `heavy_query_ms` | 211.673 | 203.214–225.513 |
| `isolate_ms` | 23.239 | 21.817–24.711 |
| `mem_idle_mb` | 60.500 | 60.204–60.907 |
| `mem_after_mb` | 545.173 | 493.876–579.063 |
| `rss_idle_mb` | 125.594 | 125.547–152.000 |

`setup_ms` includes schema and bulk inserts (1,000 bench rows, 1,000 users,
10,000 orders); it is not a standalone INSERT benchmark. `heavy_query_ms` is the
upstream 200,000-row MD5/sort query. `isolate_ms` includes Fork, connect, JOIN
query and cleanup; initial Snapshot construction is outside that timer.
Memory is process phys_footprint growth relative to the pre-start harness,
not absolute RSS; `mem_idle_mb` is sampled after setup and `mem_after_mb` after
workload/isolation. Both memory readings were positive in all five samples.
Reported PostgreSQL version: 18.3.

## Official root Go microbenchmarks

Three repetitions; median ns/op converted below. These use the root module,
whereas alternatives uses its own module; resolved dependencies can differ.

- `BenchmarkSimpleQueries`: 80.145 µs/op.
- `BenchmarkSimpleQueriesInProcess`: 22.954 µs/op.
- `BenchmarkCPUHeavyQuery`: 235524.217 µs/op.

The official suite contains no isolated INSERT benchmark. No claim about INSERT
improvement follows from this run. Differences from the MariaDB adaptation also
include engine, SQL, defaults, toolchain and background load, so the earlier
measurements do not establish a controlled engine speed ratio.

## Reproduction

Use an isolated checkout/cache and Go 1.27.4. Resolve the annotated tag to the
source commit above, verify identity, and keep the checkout unmodified:

```sh
git clone --branch v1.18.2 --depth 1 https://github.com/shibukawa/pgmem.git
cd pgmem
# OUT is an absolute directory outside this checkout.
(cd bench/alternatives && go build -o "$OUT/alternatives" .)
go test -c -o "$OUT/pgmem.test" .
for n in 1 2 3 4 5; do
  "$OUT/alternatives" -target pgmem > "$OUT/run-$n.json"
done
"$OUT/pgmem.test" -test.run '^$'   -test.bench '^(BenchmarkSimpleQueries|BenchmarkSimpleQueriesInProcess|BenchmarkCPUHeavyQuery)$'   -test.benchtime=1s -test.count=3
```

The target-specific harness was used directly rather than `run.sh`, whose full
comparison also pulls Docker images, provisions devbox and restarts OrbStack.
Official methodology: https://shibukawa.github.io/pgmem/benchmarks/
The published M3 figures are not this Mac's measurements.

## Recommendation and limits

Use this report as the actual pgmem local baseline. It answers whether the
ordinary upstream benchmark runs and what it measures here. For a defensible
mariamem/pgmem speed comparison, run both under matched, quiet conditions and
state the SQL/default differences. A dedicated INSERT comparison would require
a separately agreed workload because upstream's ordinary suite does not isolate it.

Disposable source, binaries and dedicated module/compiler caches are removed
once this evidence is preserved. Existing unrelated checkout changes are kept.
