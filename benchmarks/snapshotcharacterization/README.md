# Snapshot/Fork characterization

This harness observes the current public API. It introduces no CoW, mapping,
Snapshot, Fork or guest optimization. Run performance cells sequentially with an
exclusive machine slot; compilation/tests in other worktrees must also pause.

Build with the supported toolchain and an existing shared Go cache:

```sh
GOTOOLCHAIN=go1.26.8 go build -p 1 -o /absolute/work/temp/characterize ./benchmarks/snapshotcharacterization
cc -O2 -o /absolute/work/temp/process_cost benchmarks/tools/process_cost.c
python3 benchmarks/snapshotcharacterization/run.py \
  --binary /absolute/work/temp/characterize \
  --helper /absolute/work/temp/process_cost \
  --disk-guard /absolute/path/to/scripts/experiment_disk.py \
  --work-dir /absolute/work --min-free-gib 12 --budget-gib 4 \
  --max-memory-gib 8
```

The disk guard is the existing experiment-workspace tool (an explicit path avoids
copying a tool into this evidence branch). A fresh process owns each cell. Temporary
snapshots use the owned workspace's TMPDIR and successful Snapshot.Close removes
them. Failed cells retain partial JSON/logs for review; the outer guard stops owned
process groups. No uncertain scratch is automatically deleted.

Default matrix: additional deterministic SQL payload 0/10/100 MiB × 1/4/8/16 live
children × COUNT/read-mostly or eight-row mutation. `0` is one row, not an empty
MariaDB datadir. Actual prepared bytes/file sizes are inventoried. COUNT does not guarantee consuming every payload byte; InnoDB clustered COUNT
may still traverse data pages. Use separate `--scan-payload` cells to execute
SUM(CRC32(payload)) and demonstrate touched prepared-page behavior. `--label`
allows independent replicas without overwriting evidence.

Suite comparison includes fresh Start/setup/use/Close repeated N times versus
prepare once/Snapshot then Fork/use/Close repeated N times, including Snapshot
Close. Default N is 1/4/8/16. These are synthetic setup classes, not general
application crossover guarantees. Mutation changes at most eight 1KiB rows and
keeps table row count stable; fixture/setup uses bounded 128-row inserts.

Each cell preserves operation wall/parent CPU, ready and first-query durations,
opt-in startup traces, actual snapshot inventory, HeapAlloc/TotalAlloc/HeapSys,
RSS/OS physical accounting, virtual size, FD and goroutine counts. macOS vmmap
summary is a separate live-children observation. Continuous 250ms RSS/physical
watchdog stops over the configured memory ceiling; it is a sampling guard, not a
hard kernel memory cap. Native helper child CPU is excluded from parent CPU, while
parent serialization/watching overhead is included. Individual concurrent CPU
intervals overlap; use whole-group CPU instead of summing child intervals.

Natural after-Close counters and diagnostic GC counters are separate. Diagnostic
GC is confined to the harness; no FreeOSMemory or production GC policy is used.
RSS, physical footprint, Go heap, and virtual address space are distinct measures.
Neither TotalAlloc nor vmmap alone is an exact count of private filesystem bytes;
source tracing and observed growth must be interpreted together.

Checkpoints and vmmap are outside timed operation intervals, except that the
continuous budget watchdog and trace recording remain active. Use `--untraced`
control cells before interpreting small latency differences. Keep compact JSON,
report and checksums; delete successful disposable binaries/source/build scratch
only after preserving evidence and the worktree/branch history.
