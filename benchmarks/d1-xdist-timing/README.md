# D1 serial / local xdist timing (2026-11-03)

The local candidate benefits from parallelism once the suite has enough work.
For240 tests,4 workers reduced median end-to-end wall time from14.00s to5.76s
(2.43x,59% shorter). For24 tests,2 workers took1.72s vs2.10s serial;4 workers
added no improvement. Keep worker count explicit and tune against the actual
suite; this is one local workload, not a universal speedup or CI-latency claim.

| Tests | Workers | Median seconds | Observed range | Speedup |
| --- | --- | --- | --- | --- |
| 24 | serial | 2.102 | 2.095–2.120 | 1.00x |
| 24 | 2 | 1.723 | 1.718–1.743 | 1.22x |
| 24 | 4 | 1.771 | 1.705–2.347 | 1.19x |
| 240 | serial | 14.001 | 13.796–14.229 | 1.00x |
| 240 | 2 | 8.372 | 8.048–8.396 | 1.67x |
| 240 | 4 | 5.755 | 5.750–6.554 | 2.43x |

## Method and identity

Apple M1,8 logical CPUs,16GiB RAM, macOS27.2 arm64; Python3.11.18,
Django5.2.8, pytest9.0.2, pytest-django4.12.0, xdist3.8.0, execnet2.1.2,
mysqlclient2.2.7. Source and dependency identities are in
[evidence/inputs.json](evidence/inputs.json).

Benchmark source_commit: `eecd8f7c5fd9df30a3d65c29398e416138fa94b4`.
Installed wheel and embedded host are the exact candidate from successful
[Release CI41457221670](https://github.com/masahitojp/mariamem/actions/runs/41457221670),
source_commit `d99f07cd16a8a11c1644225206a3d1fcc0a39edd`. The benchmark branch
changes no product/runtime/test/workflow files from that candidate. Wheel hash,
host hash and embedded Go VCS identity were checked before the campaign and are
retained in [artifact.json](evidence/artifact.json). The wheel version string is
still0.6.0; candidate commit identity distinguishes this unreleased implementation.

Eight classes (four prepared atomic, four prepared transactional),3 or30 tests
per class, exercise the existing authored orders workload: ORM seed/isolation,
class data mutation, commit visibility via a second real connection, DDL and
Snapshot/Fork restoration. Serial and parallel execute the same exact tests and
assertions. There are no artificial sleeps, overlap barriers or fault scenarios.
Parallel uses `--dist=loadscope`, giving four workers enough classes to distribute.

Each sample starts a fresh pytest process, fresh hosts, migrations/seeding and
baseline capture, then runs all tests and cleanup. Measured time spans the whole
pytest subprocess. Each size/worker condition runs once for warmup (excluded),
then three measured repetitions. Order rotates across repetitions. OS/file caches
are warm; processes/DBs are fresh. Ordinary background activity and CPU scheduling
are uncontrolled. This is one sequential campaign, no competing benchmark.

All24 subprocesses passed exactly the intended test count (3168 test executions
including warmups), and all56 observed hosts exited. An initial preflight caught
an extra collected unittest alias; that run is excluded. Public SDK start,
snapshot and fork wrappers accumulate counters/timings in memory and write at
exit. Aggregate API times across workers are sums, not wall-time phases.

## Cost and limits

Host/baseline ownership increases from1 to2 to4. Total fork counts for24 tests
are33/34/36; for240 tests249/250/252. Parallelism shortens elapsed time while
increasing owned setup work; it is not a reduction in total work. Memory/RSS,
CPU time, energy, Linux behavior, Python3.14 speed, other schedulers and large
real application suites were not measured. The4-worker240-test range5.75–6.55s
also cautions against treating a single timing as exact.

Recommendation: try2 workers first for short suites;4 is useful for this larger
workload. Retain serial as the default and avoid `-n auto`. No production default,
CI topology or release behavior changed by this measurement.

## Reproduction

Install the pinned `tests/django_lifecycle/requirements.txt` and the matching
CI wheel into an isolated Python3.11 environment. Verify source/wheel/host identity
as in the retained inputs, then from a clean benchmark checkout run:

```sh
python benchmarks/d1-xdist-timing/run.py --host /absolute/installed/mariamem/_native/mariamem-host --output /absolute/results
```

[Raw sample summaries](evidence/samples.json), [medians](evidence/summary.json),
JUnit, subprocess output and per-worker ownership counters are preserved.
`checksums.json` records raw and saved hashes; absolute workspace prefixes and
trailing whitespace are normalized. Generated environments/downloads and the
completed worktree are disposable after preserving this branch and evidence.
