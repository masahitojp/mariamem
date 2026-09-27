# Decision: test direct source reads in real restore

Recommend exactly one next implementation experiment: **replace only the
restore source's buffered stdio reads with single-iovec WASI reads, and measure
the complete Fork → first SQL path.** This is permission to propose an experiment,
not acceptance of a production change or a final storage architecture.

Basis: main/release candidate `8b44e9d`, the
[production FAST baseline](fast-tranche-baseline.md), and the verified
[host-volume investigation](restore-host-volume-investigation.md) at measurement
commit `52e1528`, run 36322161992. This review adds no implementation.

## Interpretation and target budget

**Measured:** read-only ×1 p50 is 146/222 ms through guest stdio, 96/157 ms through
direct WASI, and 19/10 ms natively (macOS/Ubuntu). Ubuntu stdio causes 4,437 host
reads versus 2,227 direct reads; both guest paths retain 2,227 seeks and worker
thread servicing. Direct guest reads still degrade at ×8. The source copy is
~138 MiB, almost entirely fixed InnoDB files. Pre-staging moves the cost earlier;
it has not removed it.

**Inference:** eliminating stdio amplification has a specific, experimentally
supported mechanism and could save tens of milliseconds and some CPU in real
restore. The read-only result does not prove that saving: it omitted destination
writes and interspersed costly checksumming. The remaining direct/native gap is
not an exclusive measurement of seek, scheduler, copies, or physical storage.

**Derived target constraint:** for each of the 20 ×1 production samples, compute
`Fork latency - (restore_complete - restore_begin)`, then take percentiles:

| Platform | Observed Fork p50 / p95 | Hypothetical zero-restore remainder p50 / p95 |
|---|---:|---:|
| macOS | 516.9 / 688.7 ms | 317.8 / 429.4 ms |
| Ubuntu | 539.2 / 566.4 ms | 308.9 / 327.5 ms |

Raw JSON hashes match those recorded in the production baseline. This calculation
uses same-sample intervals, not subtraction of independent medians. It assumes
every other cost is fixed; it is neither measured optimized performance nor a
universal lower bound. Changes in contention could affect other stages.
Nevertheless, even perfect removal of this interval does not establish p50
<250 ms. None of the restore-only options currently demonstrates that target.
Preparation (~159/171 ms), engine initialization and the startup envelope remain.
This is a reason to avoid paying for a large redesign solely to chase that target.

## Comparison

| Direction | Costs plausibly affected; end-to-end potential | Risk and maintenance | Decision now |
|---|---|---|---|
| Direct WASI source reads | Removes observed stdio/iovec amplification; likely tens of ms and lower read CPU. Keeps transfer, seek, destination materialization and engine init. Does not by itself reach 250 ms. | Small mariamem copy-helper change; no MariaDB engine or runtime fork. Must handle short reads/errors correctly. Same WASIX boundary on both platforms. | **Selected experiment:** highest-confidence small mechanism; missing evidence is real Fork benefit. |
| Existing Wasmer/WASIX servicing | Could reduce seek/handoff/copy cost and ×8 contention beyond the stdio saving. Magnitude and exact mechanism remain unknown. | Instrumentation is bounded, but changing file offsets, async I/O or worker behavior can affect all guest file users. Carrying a runtime patch/build has a larger maintenance and provenance cost. | Defer implementation; retain as a candidate if real restore remains servicing-dominated. Do not skip seeks based on trace counts alone. |
| Different snapshot/runtime handoff | Bulk image/stream ingestion or runtime-backed prepared state could reduce repeated per-file servicing. A plain alternate channel still transfers/materializes ~138 MiB; a reused immutable backing could avoid more work. | Requires a concrete ingress/lifetime design, format/integrity and failure handling. Pre-staging alone has already failed the cost test. Neither lower CPU nor RSS follows from a different transport alone. | Defer; no proven existing drop-in boundary and no end-to-end estimate yet. |
| Host-owned VFS / overlay / CoW | May avoid eager copy and share untouched backing; could address memory as well as latency. Deferred reads/copy-up may move cost to first SQL/write. Engine init and validation remain. | Largest filesystem correctness burden: isolation, writes, truncate, rename/unlink, locking, recovery, base lifetime and cleanup. Current `/mariadb` is runtime memory FS: a host reflink alone does not remove its materialization. Cross-platform backing needs proof. | Not justified as the next experiment; keep as a later option with an explicit cost budget. |

All options must preserve real MariaDB and ordinary MySQL wire/multi-session
behavior. The selected change naturally leaves those boundaries intact. No
public API or Snapshot ownership change is needed. Reference systems using
overlays do not establish a benefit or a compatible implementation here.

## Hypothesis and smallest prototype

Hypothesis: avoiding the extra stdio read service per logical chunk reduces real
Fork latency/CPU on both supported platforms, without merely shifting that work
into writes, initialization or first SQL.

Start a fresh experiment from the production baseline; carry only the small
reader change in `guest/experimental.patch`, not the read-only probe entry points.
Compare two conditions within the same experimental guest, selected privately
for benchmarking: existing stdio versus one 64 KiB, single-iovec WASI read per
loop. Use the already exercised direct-read mechanism. Scope it to snapshot
**import**; the shared helper also serves export, which must retain its current
path. No MariaDB/lite4mariadb engine changes or Wasmer rebuild.

Keep destination `fwrite`, exclusive creation, directory traversal, file set,
chunk size, RSA keys, integrity validation, runtime settings and snapshot/export
semantics identical. Handle short reads, EOF, interrupted/error returns and
descriptor cleanup explicitly. Do not treat a short read as EOF. No per-chunk
FNV or syscall tracing in performance runs.

Run paired/interleaved canonical Go Fork/SQL measurements with two warmups and
at least 20 measured rounds, 1,000 rows, ×1/4/8, on macOS arm64 and Ubuntu 24.04
x86_64. Reuse the exact verified experimental WASM and platform AOTs. Record
raw end-to-end, restore/read/write stage timings and available CPU; compare
round-paired effects and p50/p95. Keep timing overhead identical. A small separate
trace may verify reduced read-call count, but is not a performance sample.

## Acceptance and rejection

- **Correctness is mandatory:** dedicated runs verify exact source/destination
  inventory and hashes before MariaDB opens the copy, including large and partial
  final chunks, empty files, short-read/error cases and failure cleanup. Retain
  normal production checks in measured runs; do not insert an extra full hash
  into only one measured condition. Exercise Snapshot/Fork isolation, multiple
  clients, transactions, interrupted-query invalidation and cleanup on both
  platforms. Preserve source bytes and export behavior.
- **Advance for production review** only with reproducible end-to-end benefit
  on both platforms. A proposed minimum worth this small code change is ≥25 ms
  ×1 paired-median Fork/SQL reduction (roughly 5% of today's latency), with the
  same direction in each half of the interleaved run. Read-call reduction alone
  is insufficient. This is an experiment decision threshold, not a CI gate or
  a prediction of the saving.
- Require no reproducible deterioration in ×1/4/8 p95 or CPU per completed Fork;
  investigate differences above roughly 5% before calling the result positive.
  Noisy or conflicting samples are inconclusive; at most one confirming paired
  run before review, rather than tuning the experiment until it passes.
- **Reject as the next production change** if correctness requires broader
  semantic changes, if the gain stays in the microbenchmark, or if meaningful
  end-to-end/CPU benefit fails to reproduce. A negative result is still useful:
  it rules out this low-maintenance path before investing in a runtime boundary.

The FAST p50 <250 ms / p95 <500 ms target remains a separate end-to-end goal.
Passing this experiment would not mean FAST is complete, nor authorize merging.

## Not yet

Do not patch Wasmer scheduling/seek behavior, add a transport/protocol, pre-stage
snapshots, change chunk/file sizes, weaken validation, alter caches/authentication,
add VFS/CoW/overlay or initialized-state continuation, or change public APIs.
Do not combine several optimizations in the A/B candidate. No implementation,
new benchmark execution, merge or release is part of this architecture review.
