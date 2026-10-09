# Historical OwnedPrepared comparison and reusable measurement primitives

## Current responsibility (v0.4.5)

The v0.4.4 comparison below is historical evidence. The existing Product workflow
has become runtime-only qualification, with a new receipt contract. It no longer
builds wheels or compares performance. `validate_product_candidate.py --phase`
is not a current command. Use [developer verification roles](../../docs/development.md#local-verification).

For manual measurement, reuse `main.go` (deterministic payload, full-public
Snapshot/Fork/SQL/cleanup timers), `import_measure.py` (Python temporary/persisted
Snapshot and import/child suites), the existing timing trace and
`benchmarks/tools/process_cost.c`. No measurement creates runtime qualification.
Pin the actual source commit with `git_identity.require_commit` before building;
record source/toolchain/binary/harness hashes and matching correctness evidence.
Old `run_compare.py` is a historical v0.4.3/v0.4.4 campaign, not the new runtime
verifier or an instruction to rebuild both releases on every change.

## Historical v0.4.4 campaign

This is a bounded comparison after correctness acceptance, not release approval.
It builds the exact production candidate and released v0.4.3 commit
`c8bd25a56e9d5221abaf40b2c98102bd60c217ae` using the same Go measurement source.
The published annotated tag object is
`dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20`; it is checked separately and must
resolve to that exact commit. Tag-object identity is not source-commit identity.
The machine-readable source of truth is `release/baselines/v0.4.3.json`.
Workflow and runner use `scripts/git_identity.py` to validate it before building.
The runner's optional override is explicitly named `--baseline-commit-sha` and
must equal the checked source commit.
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

## Historical reproduction

The following runner/workflow syntax belongs to the tested v0.4.4 source.
It is not executable with the current runtime-only runner.

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

## Actual Fresh/prepared crossover (v0.4.5)

The [completed v0.4.5 review](../../docs/reviews/v045-human-review.md) preserves
actual sequential Fresh/Fork suites, parallel and multi-connection controls,
Snapshot attribution, exact binary/input identities and all retained tails.
Its numbers are local observations, not release benchmark promises. Fresh wins
for the measured light setup even at 32 tests; fixture preparation cost, data
size and reuse count determine whether preparing once is worthwhile.
The [benchmark document](../v045-measurement.md) owns final conditions, raw
evidence and reproduction; no Snapshot optimization is adopted in v0.4.5.

`main.go -lifecycle fresh|fork` executes the same deterministic fixture and SQL
oracle for each instance. `fresh` starts and prepares every DB; `fork` prepares
one DB, creates a temporary Snapshot and starts every child from it. Both allow
real application commits/rollback and discard each DB. `-forks` is the instance
count in either mode, retained as a harness flag rather than a public API name.
`-workers` controls suite concurrency, not a simultaneous-worker peak sampler.

Compare `suite_product_seconds` and preserve full wall time, CPU and probes.
Preparation, SQL and cleanup are measured, never estimated by subtracting hash
latency. Fresh has no Snapshot creation/close phase. The default remains `fork`;
FD scaling and artifact provisioning apply only to `fork`. `instance_suite_wall_seconds`
names the common child-loop boundary; the old `fork_suite_wall_seconds` is retained
for Fork results. A point-read verifies exact fixture bytes before mutations, so
same-length changes in a previous child cannot masquerade as unchanged input.
