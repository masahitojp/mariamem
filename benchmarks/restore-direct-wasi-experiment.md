# Direct WASI source reads in actual restore

## Status

**Reject as a production candidate at this checkpoint:** real restore read/CPU
savings are demonstrated, but the parallel tail acceptance condition is not
established. This is not a correctness failure or evidence that direct reads
necessarily cause the tail regressions.
Nothing is integrated into main. The rationale is recorded in
[the decision note](restore-next-experiment-decision.md); prior read-only results
are in [host-volume attribution](restore-host-volume-investigation.md).

## Only the import reader changes

One experimental WASM/AOT supports two private modes:

- `stdio`: production-style `fread` of the source, then existing destination
  `fwrite` into the guest memory filesystem.
- `direct`: the same source opened with `fopen`, read through its descriptor
  with one 64 KiB WASI `fd_read` iovec, then the identical destination `fwrite`.

The direct path retries WASI interrupted calls and handles short reads without
treating them as EOF. It fails on other read errors, and closes input/output
through the existing cleanup path. `fclose`, exclusive destination creation,
directory traversal, snapshot inventory, file sizes and destination filesystem
are retained. Export continues using stdio, with the import counters inactive.
RSA provisioning, engine configuration, validation and SQL/session behavior are
unchanged. No Wasmer/runtime modification is made.

Changes to guest helpers live in `guest/experimental.patch`. Preparation now
applies experimental diffs after canonical overlay installation so the helper
diffs are reproducible; their actual hashes and patch identity are recorded.
Canonical `guest/source.patch` and overlay files remain unchanged. Existing
release verification still rejects experimental provenance.

## Correctness separately from timing

Before measurement, the public Go fixture helper creates the normal 1,000-row
snapshot and verifies a real Fork/SQL. For each reader mode a diagnostic import
copies the snapshot into `/mariadb`, then uses the unchanged stdio export to
return that copied tree before MariaDB can alter it. Python compares every
directory/file entry, byte count and SHA256 against the verified snapshot
manifest and rechecks the source. This additional export/hash cost is recorded
as separate correctness setup, never treated as a restore optimization.

Both modes additionally run the maintained Go race/Python integration path:
Snapshot/Fork, sessions, multi-client isolation, interruption/unusable semantics
and cleanup. Missing/incorrect timing or mode evidence and byte/count mismatches
fail the experiment. Normal startup still requires the prepared keys.

Native C tests apply the exact experimental diff, checking byte-identical import
and export, empty/partial-chunk files, simulated short reads/EINTR, read errors,
occupied destinations and symlinks. Those tests validate the copy algorithm;
actual WASI ABI/runtime behavior is exercised by the two CI platform jobs.

## Paired measurement

`benchmarks/goisolation --restore-ab` reuses the canonical public API startup,
batch, SQL-readiness, sampler and cleanup implementation. One prepared snapshot
is shared across all batches. At ×1/4/8, two warmup rounds and 20 measurement
rounds execute both modes, reversing their order each round. Conditions switch
only after the preceding batch has closed completely. No global trust cache,
pre-staging or extra per-chunk checksum is introduced.

Raw samples include Fork → first verified SQL, read/write wall and process/thread
CPU, total copy wall/CPU, bytes/files/calls, guest-main → ready CPU, and canonical
runner CPU/approximate descendant observations. Guest-main CPU excludes runtime
pre-main, first SQL and shutdown; runner CPU is host/harness work, not guest CPU.
Process/thread clock brackets include diagnostic overhead. Both modes use the
same counters; absolute latency may differ from the less-instrumented production
baseline. A close acceptance result needs confirmation without per-read timing
before production integration.

`benchmarks/restore_read_ab.py` preserves canonical Go raw samples and adds
identity/environment, correctness results, p50/p95 per mode, and same-round
differences. Parallel paired differences use per-batch means, because worker
arrival order is not a stable pairing identity. Component percentiles must not
be added as a measured total. No expensive mapping/memory diagnostics run.

Dispatch `guest-build-boundary.yml` on this branch with
`restore_read_comparison=true`, other measurement inputs false. This guest change
requires a new verified WASM and both AOTs once; unchanged identities are reused
thereafter. Artifacts are `initialization-<platform>-<candidate SHA>`, containing
`init-restore-read-ab.json` and manifest/AOT provenance. Raw results stay ignored.

## Completed evidence

Primary [run 36327052926](https://github.com/masahitojp/mariamem/actions/runs/36327052926)
measured `b4cd12be9e669ecd51daab240a980bbc576c3303`. Both platform jobs passed,
including both-mode integration, content verification, first SQL and cleanup.
macOS was 15.7.9 arm64 (3 CPUs); Ubuntu was 24.04 x86_64, kernel
6.17.0-1022-azure/glibc 2.39 (4 CPUs). Go 1.26.8, Python 3.14.7 and Wasmer
7.4.2 were used. These are different hosted machines, not a platform speed contest.

The immutable guest/AOT inputs were reused from build commit
`691a054d18aeac1e2099a7561bc3c489abb8599a`:

| Identity | SHA256 |
|---|---|
| Common WASM | `dae1186b81ef007316ac82ee93a58f9c7c9b3a739beee4bd0afc7d227487930f` |
| macOS AOT | `4a5ec3a0411e38e8fd15bd39db1748391ba8e8ea624e29986fb6e83e6afd2383` |
| Ubuntu AOT | `4b7c429a564ec4b3a5423924f3289ab4e07c9f3c1dd3f2e9ea17476d500ca6f2` |
| macOS result JSON | `8ba8c59ca3edc3bd42ecec138b42fc6e8da100e6b0ce6367d148e8aea9a8dc7e` |
| Ubuntu result JSON | `0b8eed37c9148a749b82598e61f406f52241b047e60099b4aac09f36e766a680` |

Downloaded evidence lives in ignored `benchmarks/results/restore-read-ab-36327052926/`.
Manifest/provenance copies agree with the embedded evidence; manifest SHA256
matches provenance. Recalculation reproduces summaries within floating-point
roundoff. All 572 per-DB rows per platform (including warmups) reconcile mode,
64 KiB chunks, bytes and file counts against their batch inventory. There are
20/80/160 measured per-DB observations per condition at ×1/4/8.
The separately hashed correctness fixture and the timed fixture are independent;
within each comparison the two modes share one exact inventory. Each contains
11 files and approximately 138.17 MiB. Their small metadata-size differences
must not be mistaken for failed byte reconciliation.

## Real restore results

Values are milliseconds, **p50 / p95**. Arrows mean stdio → direct.
Percentiles are pooled per-DB observations, not sums of stage medians.

| Platform | DBs | Fork → SQL | Restore total | Source read | Destination write | Restore process CPU |
|---|---:|---|---|---|---|---|
| macOS | 1 | 508.8 / 606.6 → 491.2 / 613.7 | 175.1 / 215.0 → 141.5 / 221.3 | 121.0 / 140.2 → 86.4 / 130.2 | 34.4 / 43.2 → 32.5 / 51.7 | 163.2 / 208.2 → 131.5 / 191.4 |
| macOS | 4 | 1003.9 / 1656.9 → 896.1 / 1857.8 | 393.1 / 753.6 → 282.8 / 700.7 | 255.2 / 503.6 → 166.6 / 407.9 | 80.0 / 215.8 → 65.1 / 181.5 | 267.5 / 447.1 → 202.4 / 328.4 |
| macOS | 8 | 2283.8 / 3152.5 → 1934.7 / 2864.8 | 841.4 / 1330.0 → 629.6 / 1034.1 | 578.3 / 945.8 → 402.8 / 674.4 | 168.7 / 481.6 → 121.5 / 383.9 | 300.9 / 420.7 → 241.1 / 364.7 |
| Ubuntu | 1 | 446.9 / 459.9 → 404.4 / 416.5 | 190.9 / 194.5 → 149.2 / 158.5 | 146.8 / 150.8 → 105.9 / 112.9 | 22.1 / 23.4 → 21.9 / 23.7 | 176.2 / 177.9 → 137.3 / 141.9 |
| Ubuntu | 4 | 626.5 / 721.8 → 566.4 / 633.8 | 267.1 / 393.7 → 197.7 / 300.3 | 205.5 / 327.0 → 139.6 / 243.1 | 30.7 / 36.9 → 30.2 / 34.5 | 179.9 / 199.6 → 142.1 / 152.4 |
| Ubuntu | 8 | 1110.3 / 1200.5 → 1033.4 / 1110.5 | 453.2 / 604.9 → 372.7 / 480.5 | 382.2 / 529.0 → 305.9 / 415.9 | 36.2 / 46.4 → 34.7 / 44.2 | 181.7 / 198.0 → 145.0 / 157.7 |

### Paired effects and CPU

Same-round batch-mean stdio-minus-direct median Fork savings were macOS
**29.38 / 114.98 / 297.21 ms** and Ubuntu **42.72 / 62.67 / 75.43 ms**
at ×1/4/8. ×1 Fork improved in 15/20 macOS and 20/20 Ubuntu pairs.
These paired effects are distinct from subtracting the pooled p50s.

Paired restore process-CPU savings were macOS **28.22 / 81.31 / 58.28 ms**,
Ubuntu **38.05 / 38.70 / 37.93 ms**. Copy CPU improved in 16/18/19 of 20
macOS pairs, and all Ubuntu pairs. At ×1, source-read process/thread CPU p50
fell from 116.9/59.4 to 83.9/42.7 ms on macOS and 140.3/60.6 to 101.7/42.9
ms on Ubuntu. Destination-write process/thread CPU stayed approximately
38.9/35.6 → 37.9/34.9 ms and 29.4/24.8 → 29.4/24.7 ms respectively.
Guest-main → ready process CPU p50 fell from 260.6 to 222.1 ms on macOS
and 245.3 to 208.7 ms on Ubuntu. This supports a source-side CPU saving;
it does not attribute all runtime CPU or infer physical disk activity.

Go runner batch CPU is separate: ×1/4/8 p50 was macOS
182/754/1447 → 177/763/1431 ms; Ubuntu 162/670/1347 → 162/670/1346 ms.
There is no corresponding material host-CPU saving. Sampling cannot account
perfectly for process startup/shutdown edges. Read/write clock brackets have
instrumentation overhead; an uninstrumented end-to-end check is still needed.

### Tail check using existing independent evidence

Ubuntu p95 improves at every concurrency. macOS primary-run ×4 Fork p95
increases **1656.9 → 1857.8 ms (+12.1%)**, although restore/read p95 and CPU
improve. ×1 p95 also increases slightly (606.6 → 613.7 ms).

The already-completed macOS artifact from
[run 36325170300](https://github.com/masahitojp/mariamem/actions/runs/36325170300)
uses the identical WASM/AOT. Its host commit is `691a054`; the subsequent
`b4cd12b` only waits for disconnect before fixture Snapshot, outside timing.
Its JSON SHA256 is
`2c7629a6b7eca16d6675cf4b518854d49380f19a07f919494eac129d95bb1b36`.
Its manifest, summaries and 572 inventory reconciliations were also verified.
This run's Ubuntu setup failed, so it is only corroborating macOS evidence.

| macOS prior run | stdio Fork p50/p95 | direct Fork p50/p95 | paired median saving |
|---|---|---|---|
| ×1 | 688.2 / 1381.3 | 649.2 / 1044.3 | 62.0 |
| ×4 | 1769.1 / 2821.4 | 1572.2 / 2228.5 | 311.2 |
| ×8 | 4147.3 / 4821.3 | 3755.2 / 5155.4 | 341.7 |

The ×4 regression does not reproduce at that same concurrency, but prior ×8
p95 instead worsens by 6.9%. Paired copy CPU improves in 19/18/20 of 20
pairs. Absolute latency varies substantially between hosted runs. **Unknown:**
whether tail differences are runner scheduling/resource variation or a causal
path effect; these data cannot prove either explanation. Do not dismiss the
regressions as noise, and do not claim reproducible harm has been established.

## Decision: reject at this checkpoint

**Measured fact:** source read, copy CPU and paired end-to-end latency improve
on both platforms, including the requested approximately 25 ms ×1 threshold.
Correctness and maintained lifecycle coverage pass.

**Decision:** reject as a production candidate now because evidence is mixed
for parallel tails. The required no-reproducible-regression condition has not
been established; CPU/microbenchmark gains do not override it. This conservative
rejection does not assert that direct reads are intrinsically unsuitable.

**Inference:** this small source-side change offers tens of milliseconds at ×1,
not a demonstrated route to the <250 ms FAST target. Destination writes and
other startup costs remain, and substantial direct-read cost still exists.
Historical production baselines are context, not controlled subtraction.

If reconsidered, the smallest missing evidence is bounded paired end-to-end
confirmation without per-read timing on both platforms, retaining exact content
and error/cleanup checks. Only after tails are resolved should a clean import-only
production helper and exact packaged Go/Python acceptance be considered.
No write optimization, architecture change, merge or release is performed here.
