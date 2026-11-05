# Merged public Go API: lightweight TCP/Pipe measurement

2026-11-05, Apple M1 / macOS27.2 arm64, Go1.26.10, mysql1.9.3,
GOMAXPROCS8, GOGC100. All24 cells PASS. Same-process Pipe has lower elapsed
medians in this short serial comparison, with higher allocation. This does not
change the TCP default or qualify a general application speedup.

## Results

Three fresh processes, TCP-first / Pipe-first / TCP-first. Four workloads per
transport,500 operations per cell. Values below are medians of the three
process-level per-operation averages, not latency percentiles.

| Workload | TCP | Pipe | Elapsed reduction |
| --- | ---: | ---: | ---: |
| Connect/handshake/Ping/client close |338.60us|150.37us|55.6%|
| Warm SELECT1 |97.99us|57.28us|41.6%|
| Warm explicit prepared SELECT ? + 1 |101.91us|59.40us|41.7%|
|64 rows x128-byte payload |878.86us|685.94us|22.0%|

| Workload | TCP B/op | Pipe B/op | TCP allocs/op | Pipe allocs/op |
| --- | ---: | ---: | ---: | ---: |
| Connect/Ping |18722|20032|217|223|
| SELECT1 |9107|9949|98|109|
| Prepared1 |9508|10371|107|118|
| Result64x128 |98981|107966|814|951|

Allocated bytes increase about7–9%; result-transfer allocations increase about17%.
These are Go benchmark allocations, not retained memory/RSS. RSS, CPU, concurrency,
fixture end-to-end time, other platforms and confidence intervals were not measured.
Three process samples give a rough indication, not a release/performance guarantee.

## Identity and boundaries

Product main baseline_source_commit:
`676515eb9244fc501b5a600791b0cf0a6174fecd` (includes merged #110 and status #111).
Measured source_commit:
`e3f8f955dc1a4a8f0422cb5ed078bcee167772ef`.
The only difference from baseline is this benchmark/collector source; no product,
guest, generated code, driver dependency, default or CI changes. The source was
committed, clean and inspected using scripts/git_identity.py before compilation.
metadata.json records binary SHA256. Go test binaries do not contain a VCS stamp;
the report does not claim a stamped host. Later evidence files are not build input.

The benchmark uses public Start/DSN/DialContext/WaitDisconnected only. Both modes
parse the same DSN, set InterpolateParams=false and use the same driver/pool
settings. Pipe sets Config.DialFunc=database.DialContext; TCP leaves it unset.
Driver connect/read/write timeouts retain their defaults; server options are zero
values (default query timeout). Warm SQL has maxOpen1/maxIdle1; connect/Ping has
maxOpen16/maxIdle0, including client close on return to the pool. Server-close
acknowledgement is awaited after each cell, outside the timer.

`SELECT REPEAT('x',128) FROM seq_1_to_64` returns64 rows, read fully. Setup checks
payload values/count; timed iterations check scan errors and row count. SELECT1
and prepared results are asserted. Build, database startup, statement setup,
preparation/probe and final teardown are outside operation timing. Fork is not
used. Go's one-iteration benchmark calibration is not a reported final cell.

Prior spike absolute values are a separate cohort: its internal dialer and
explicit driver timeout settings differ. Do not interpret differences from that
report as an additional product optimization or pool/fixture result.

## Reproduction and preservation

Use an owned3GiB workspace with8GiB free reserve and the measured source in
`TASK_WORK/worktree`. Commit/inspect identity before build; record its JSON as
`TASK_WORK/evidence/source-identity.json`. Then, with absolute TASK_WORK paths:

```sh
GOTOOLCHAIN=go1.26.10 GOCACHE=TASK_WORK/temp/go-cache \
  GOTMPDIR=TASK_WORK/temp/go-tmp GOMEMLIMIT=3GiB GOGC=50 \
  go test -p 1 -vet=off -c -o TASK_WORK/temp/pipe.test ./benchmarks/pipe-transport
python scripts/experiment_disk.py --work-dir TASK_WORK \
  --min-free-gib 8 --budget-gib 3 --timeout 180 -- \
  python benchmarks/pipe-transport/run.py TASK_WORK
```

The collector explicitly sets benchmark GOGC100, removes GOMEMLIMIT and fixes
GOMAXPROCS8; build-only GC settings are not benchmark settings. It stops on an
error or missing cell, without automatic retries. results.csv/JSON retain all24
cells, summary.json the calculations and metadata.json the input identity.
Raw process/build info stays in compact local evidence. Source/results are
pushed before deleting the task's executable, compiler cache and worktree.
No runtime qualification or permanent CI addition is requested by this measurement.
