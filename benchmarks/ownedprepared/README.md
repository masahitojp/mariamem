# Owned prepared-state production qualification

This is a bounded comparison after correctness acceptance, not release approval.
It builds the exact production candidate and released v0.4.3 commit
`dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20` using the same Go measurement source.
Python uses each commit's SDK and exact host binary. No previous spike numbers
are treated as production results.

The dedicated `v044-product-validation.yml` workflow runs on native macOS arm64
and Ubuntu 24.04 x86_64. It checks source/unit boundaries, handwritten races,
real Go/Python isolation/lifecycle, and installed pytest/xdist before comparison.
A candidate-specific PASS record gates performance. No release/tag/merge occurs.

## Measurements

- Minimal, 10 MiB and 100 MiB deterministic payloads: three independent trials,
  sixteen children per variant/trial. Baseline/candidate execution order alternates.
- Go preparation includes Fresh startup, fixture creation and Snapshot creation.
- Python capture separately measures temporary and persisted Snapshot creation from
  identical logical input, including acquisition/source startup as separate phases.
  The candidate uses `snapshot_to(path)`; the release baseline uses `snapshot(path)`.
- Python imports the same exact release-produced external artifact in both variants.
  Input provisioning is recorded separately and excluded from import suite time.
- Ready latency excludes SQL use. Point lookup and COUNT are separate Go operations;
  Python records SQL use separately from ready. Large COUNT is a scan, not startup.
- Bounded realistic workloads add committed CRUD, writes from a separate application
  connection, and sixteen children with four concurrent workers on a 10 MiB baseline.
- FD scaling is a separate phase: a 64-table InnoDB baseline with up to sixteen
  concurrent Snapshot handles, including counts at one/four/sixteen and OS limits.
  An actual EMFILE/ENFILE limit is retained as evidence with held-handle count and
  cleanup; it is not silently classified as successful sixteen-handle scaling.
- Physical footprint on macOS and PSS/RSS on Linux come from the existing OS
  counter helper. `file_mapping_bytes` is mapped virtual extent, not resident bytes.
- Python suite CPU is diagnostic-inclusive: process CPU plus reaped child CPU,
  including DB hosts **and counter-helper subprocesses**. Go suite CPU uses
  process CPU only; it includes benchmark/diagnostic parent overhead and GC but
  excludes counter-helper child CPU. Each JSON/summary row exposes its scope;
  these are measured suite CPU totals, not estimates of pure database CPU.
  Per-operation Python CPU is omitted
  because reaping attributes accumulated host CPU to Close. Parallel Go per-operation
  CPU is likewise omitted because process totals overlap.

`summary.csv` pools forty-eight ready samples per normal cell. p95 is nearest-rank.
Suite p50/p95 uses only three trials; preserve min/max/raw results for tail review.
Raw suite wall time includes resource probes and preparation/SQL/cleanup.
`suite_product_seconds` excludes resource/FD probes and GC: serial uses measured
operation sum; parallel uses preparation + the uninstrumented child-loop wall
window + Snapshot Close. Diagnostic overhead is reported separately. Parallel
summed operation time overlaps and is **not** wall latency. Parallel resource
probes sample before/after the child loop, **not a simultaneous-child peak**.
FD enumeration and profiling never occur inside ready timing.

## Reproduction

Use a fresh disposable checkout at the exact candidate SHA, installed Go 1.26.8,
Python 3.14, native C tools and the dependency versions pinned in the workflow.
The workspace must be outside that checkout. The runner removes recreated build,
cache, source archives, wheel staging and measurement inputs after compact evidence
is preserved. Do not point it at a development checkout with unique local artifacts.

```sh
python scripts/validate_product_candidate.py \
  --candidate-sha FULL_CANDIDATE_SHA \
  --workspace /tmp/mariamem-product-validation \
  --disposable-checkout --phase all
```

The workflow uses separate `correctness` and `performance` invocations against the
same evidence directory. After a successful push to the dedicated implementation
branch, CI owns execution; human review resumes after the results are available.

Durable output contains exact source SHAs, binary/harness hashes, command records,
PASS/FAIL gates, small OS probes, input manifests, raw measurements, reduced CSV/JSON
and cleanup status. No persisted database contents are retained as evidence.
