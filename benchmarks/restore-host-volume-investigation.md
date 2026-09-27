# Read servicing at the snapshot host-volume boundary

## Scope and status

This attribution probe starts from production candidate
`8b44e9db569c0ea04e45ae6c60fc8ecf54b7b8ab` on
`experiment/restore-host-volume`. It does not include the old prepared-auth
experiment history. Production prepared RSA keys, within-call validation and
Snapshot/Fork remain unchanged. No restore optimization is implemented.

[Run 36322161992](https://github.com/masahitojp/mariamem/actions/runs/36322161992)
completed successfully on both platforms at measurement commit
`52e15283d23ed10fb3c6f5a8007f4a45967b86e4`. Previous production Fork/SQL p50
(~517/539 ms) and restore (~196/231 ms) are context, not measurements of this
read-only probe. The earlier run failed before measurement because the harness
omitted the manifest's `.` root entry; that harness-only fix preserved guest identity.

## Concrete path: source facts

1. `internal/guest/guest.go` mounts the immutable snapshot directory at
   `/snapshot-in` using Wasmer `--volume`. `guest/resident.inc` calls
   `snapshot_copy("/snapshot-in/data", "/mariadb", ...)` before MariaDB startup.
2. `guest/snapshot_fs.inc` enumerates directories, opens each regular file with
   `fopen(..., "rb")`, and repeatedly calls `fread` into a 65,536-byte buffer.
   The existing destination `fwrite` is a separate operation.
3. The pinned WASIX libc's musl `fread.c` drains buffered bytes before invoking
   its read callback. `__stdio_read.c` uses `readv` with the caller's destination
   and the stdio buffer as separate iovecs; it also copies/manages buffered bytes.
   One `fread` is therefore not necessarily one runtime or kernel read.
4. Wasmer 7.4.2 `lib/wasix/src/syscalls/wasi/fd_read.rs` checks pending operations,
   obtains the descriptor/offset, and reaches `fd_read_internal`. For a file it
   takes the virtual-file handle lock, seeks to the descriptor offset, obtains
   guest-memory iovec slices, and awaits virtual-file reads for the iovecs.
   `__asyncify_light` drives this asynchronous operation with `block_on`.
5. `lib/virtual-fs/src/host_fs.rs` delegates host files to `tokio::fs::File`.
   The cached dependency source (`tokio-1.53.1/src/fs/file.rs`) shows a staging
   buffer, asynchronous completion, and copying that buffer into the caller's
   `ReadBuf`. Its fallback read implementation uses `spawn_blocking`; seek can
   also involve asynchronous work. An io-uring path exists behind additional
   configuration. Which path the distributed binary actually exercises must be
   checked against traces; source availability alone does not prove it.

These are source boundaries, not a measured decomposition of runtime time.
Inspection used the pinned lite4mariadb/WASIX-libc archives and Wasmer/runtime
notice sources; workflow output records the actual WASM/AOT build provenance.
This path includes locks, service scheduling and buffer copies as well as host
filesystem access. None of its wall time can yet be called physical disk I/O.

## Bounded controls and observables

`guest/experimental.patch` adds two explicit diagnostic entry points. Ordinary
startup delegates to the existing resident entry point without changing it.
Neither diagnostic entry point starts MariaDB or creates a destination copy.

| Condition | Source and operation | Observable boundary |
|---|---|---|
| guest-stdio | `/snapshot-in/data`, same 64 KiB `fread` | libc + WASIX + host-volume servicing |
| guest-direct | same mount, single 64 KiB WASI `fd_read` iovec | bypasses stdio buffering; includes runtime servicing |
| native-stdio | same host snapshot, identical C probe | native libc + host file access |
| native-direct | same host snapshot, native 64 KiB `read` | native syscall baseline |

The native harness extracts and compiles the exact C source in the experimental
patch. It is not a second implementation. Guest direct reads are a diagnostic
control, not a proposed change to production restore. Native libc differs from
WASIX libc; differences do not give an exact removable-latency estimate.

For each file we record timed-read wall/process/current-thread CPU, bytes,
read-call count (including EOF), checksum wall, and complete open/read/checksum/
close wall/CPU. Complete probe and process-lifecycle wall are separate. Directory
enumeration and printing are outside the sum of timed reads but inside probe
wall. No destination-memory-FS writes are present.

Wasmer's Unix `clock_time_get` maps guest process/thread CPU clocks to native
process/current-thread clocks. Thus process CPU can include runtime service
threads; current-thread CPU can omit work on other threads. Clock calls and
observer overhead remain present. Unsupported CPU clocks are null, not estimates.
Parent `RUSAGE_CHILDREN` deltas additionally record complete batch CPU, including
runtime startup/checksum/exit. No service-thread CPU breakdown is claimed.

Ubuntu produces separate `strace -f -T -yy` logs for read/readv/pread64/lseek/futex
for all four controls. These diagnostic runs never enter latency percentiles.
Kernel-call durations and descriptor/PID identities can constrain read/seek/wait
hypotheses, but overlapping worker/futex durations must not be summed as an
exclusive waterfall. Trace overhead is not representative performance.
macOS has no equivalent kernel trace in this probe.

## Fixture, identity and execution

`benchmarks/hostvolumefixture` uses the public Go API to prepare the canonical
1,000-row InnoDB fixture, Snapshot it, Fork it, and verify the row count. Normal
startup/key validation and lifecycle cleanup remain mandatory. Setup and that
public Fork check are recorded separately, outside the read-only cases.

`benchmarks/host_volume_read.py` verifies every snapshot inventory entry, file
size and SHA256 before and after each condition batch. Consumed bytes are
checked against per-file FNV-1a checksums from a separately recorded native pass;
FNV is reconciliation, not a substitute for cryptographic artifact integrity.
Duplicates, missing files, mismatched bytes/checksums and symlinks fail closed.
WASM and platform AOT are sealed/verified through the existing immutable reuse
path. This patch changes guest identity, requiring one fresh guest build and
dependent AOTs; subsequent harness-only changes can reuse those exact identities.

Two warmup rounds and 20 measured rounds run at ×1/×4/×8. Each round rotates the
four conditions, with processes launched together at the requested concurrency.
Raw file/process/batch samples are preserved. p50/p95 are computed from actual
per-process observations; adding component medians is not a measured total.

SHA verification reads all source bytes and warms the host page cache before
each batch. This is deliberately a **repeated/warm-source** experiment, not a
cold-storage benchmark. Verification and the initial reference/cache-warming
pass have separate timings. FNV calculation is outside timed reads, but consumes
CPU between reads and can perturb scheduling. It is identical across controls
and its cost is reported. Complete probe/lifecycle totals include that work.
No pre-staging, chunk-size change or expensive memory diagnostics are used.

Dispatch `guest-build-boundary.yml` on this branch with
`host_volume_measurement=true` and other measurement inputs false. The workflow
uploads `initialization-<platform>-<candidate SHA>` containing
`init-host-volume.json`, Ubuntu `host-volume-traces/*.log`, and AOT provenance.
Raw results remain ignored. CI is handed off after submission, without polling.

## Verified measurement identity

- macOS 15.7.9 arm64: 3 reported CPUs; Go 1.26.8; Python 3.14.7.
- Ubuntu runner: Linux 6.17.0-1022-azure x86_64, glibc 2.39; 4 reported CPUs;
  Go 1.26.8; Python 3.14.7. Wasmer 7.4.2 on both platforms.
- Original guest build checkout: `e1f1edc84c3e9483091b43594b863bd882c8e0e7`.
  This run reused verified WASM and both AOTs; no guest rebuild was needed.
- Common WASM SHA256:
  `14c69bf76f2fc373509c7a2efa261da01d3381c6117bd8e04cb6ca5128e57c73`.
- macOS AOT SHA256:
  `b85e04745139f0dc647e094de07f9cf48422b68eb76bf2601050012552dd54a3`.
- Ubuntu AOT SHA256:
  `e2be78917bd03394792b6b79605a841ffb18ed98af28a82dea0d56551caf76f3`.
- Downloaded macOS result JSON SHA256:
  `6b6b86978459cd1e79ed0e4397a4df781931f96413d22b14a637558924558905`.
- Downloaded Ubuntu result JSON SHA256:
  `32b07cea629917f766d3cf59b822286f05d601d633a77b99aafb93f2780db006`.

Verification reran `benchmark_artifacts.verify_wasm` against the downloaded
WASM/reuse records and current exact guest inputs. Result source SHA, completion,
sample counts, embedded versus separately uploaded manifest/provenance, manifest
hash, and WASM/AOT hash links all match. AOT binaries are not in the initialization
analysis artifact; their bytes were verified by CI, not rehashed locally here.
Each platform has 264 condition batches including warmup, 1,040 measured process
observations, and 20/80/160 observations per condition at ×1/×4/×8. Every read
reconciled 144,885,808 bytes (138.173 MiB), 11 files and 2,227 probe read calls.
SHA256 inventory checks before/after each batch and consumed-content checks passed.

## Read-only results: measured fact

All entries below are **p50 / p95 milliseconds**. CPU is the sum of observed
CPU deltas around reads, not full runtime CPU. The clocks have slightly different
brackets and include observer overhead; subtracting them does not give an exact
service-thread CPU total.

| Platform | Concurrency | Condition | Read wall | Read process CPU | Read current-thread CPU |
|---|---:|---|---:|---:|---:|
| macOS | 1 | guest stdio | 145.60 / 171.46 | 149.08 / 164.62 | 77.73 / 85.47 |
| macOS | 1 | guest direct | 96.29 / 133.96 | 100.06 / 133.44 | 51.51 / 68.39 |
| macOS | 1 | native stdio | 18.36 / 33.72 | 21.08 / 38.58 | 18.83 / 34.81 |
| macOS | 1 | native direct | 18.61 / 25.28 | 21.84 / 28.88 | 19.27 / 25.94 |
| macOS | 4 | guest stdio | 246.95 / 412.59 | 144.06 / 170.96 | 79.47 / 95.05 |
| macOS | 4 | guest direct | 187.75 / 267.60 | 101.63 / 125.52 | 56.36 / 68.69 |
| macOS | 4 | native stdio | 22.17 / 34.35 | 18.18 / 26.49 | 16.24 / 23.38 |
| macOS | 4 | native direct | 22.20 / 35.10 | 18.05 / 24.27 | 16.17 / 21.58 |
| macOS | 8 | guest stdio | 493.53 / 722.82 | 91.73 / 154.08 | 51.03 / 87.13 |
| macOS | 8 | guest direct | 424.00 / 600.62 | 64.99 / 95.23 | 36.41 / 53.20 |
| macOS | 8 | native stdio | 31.11 / 62.58 | 13.29 / 21.09 | 12.06 / 18.83 |
| macOS | 8 | native direct | 29.14 / 61.45 | 13.06 / 19.45 | 11.78 / 17.28 |
| Ubuntu | 1 | guest stdio | 221.79 / 233.37 | 206.30 / 223.62 | 101.04 / 106.63 |
| Ubuntu | 1 | guest direct | 156.73 / 163.29 | 149.12 / 162.70 | 71.86 / 79.73 |
| Ubuntu | 1 | native stdio | 9.96 / 10.19 | 14.21 / 14.44 | 11.38 / 11.63 |
| Ubuntu | 1 | native direct | 9.77 / 10.16 | 13.99 / 14.40 | 11.19 / 11.59 |
| Ubuntu | 4 | guest stdio | 255.07 / 409.97 | 172.72 / 201.85 | 73.18 / 94.54 |
| Ubuntu | 4 | guest direct | 202.40 / 313.15 | 125.96 / 141.08 | 53.84 / 66.32 |
| Ubuntu | 4 | native stdio | 10.10 / 11.30 | 15.32 / 16.53 | 11.83 / 12.99 |
| Ubuntu | 4 | native direct | 10.28 / 11.35 | 15.49 / 16.72 | 12.01 / 13.08 |
| Ubuntu | 8 | guest stdio | 588.58 / 740.28 | 171.34 / 191.84 | 77.67 / 89.91 |
| Ubuntu | 8 | guest direct | 466.41 / 581.33 | 121.36 / 137.94 | 54.97 / 64.61 |
| Ubuntu | 8 | native stdio | 10.23 / 13.07 | 15.34 / 16.51 | 11.79 / 12.94 |
| Ubuntu | 8 | native direct | 10.14 / 11.85 | 15.30 / 16.28 | 11.71 / 12.70 |

Same-round, same-worker-index stdio-minus-direct differences provide an additional
paired comparison, rather than adding/subtracting stage medians as a waterfall:

| Platform | Concurrency | Paired read-wall difference p50 / p95 ms | Positive pairs |
|---|---:|---:|---:|
| macOS | 1 | 48.88 / 86.70 | 20 / 20 |
| macOS | 4 | 51.91 / 244.88 | 66 / 80 |
| macOS | 8 | 83.21 / 302.47 | 107 / 160 |
| Ubuntu | 1 | 65.55 / 78.57 | 20 / 20 |
| Ubuntu | 4 | 56.86 / 260.64 | 52 / 80 |
| Ubuntu | 8 | 140.51 / 337.10 | 128 / 160 |

Higher-concurrency pairs are noisier; worker indices are not controlled identical
scheduling slots. Both controls show large ×8 degradation even without stdio.

### Setup and checksum costs are not free

Fixture setup including Go invocation/public Fork check took 2.377 s macOS /
1.748 s Ubuntu. Before/after full SHA verification p50 was 88.97/98.18 ms macOS
and 102.49/102.57 ms Ubuntu **per batch**. These are outside timed probe execution
and warm the source cache. They are not estimates of production validation cost.

| Platform, ×1 | Condition | Checksum wall p50 / p95 ms | Complete probe wall p50 / p95 ms | Process lifecycle p50 / p95 ms |
|---|---|---:|---:|---:|
| macOS | guest stdio | 228.31 / 260.78 | 392.08 / 457.21 | 465.9 / 594.7 |
| macOS | guest direct | 219.89 / 249.65 | 330.75 / 397.20 | 408.3 / 484.6 |
| macOS | native stdio | 233.81 / 270.71 | 257.45 / 315.26 | 262.9 / 320.3 |
| macOS | native direct | 235.12 / 251.99 | 258.08 / 287.50 | 264.1 / 293.2 |
| Ubuntu | guest stdio | 180.19 / 180.86 | 416.78 / 427.42 | 461.0 / 471.2 |
| Ubuntu | guest direct | 180.34 / 180.61 | 351.61 / 357.52 | 395.7 / 400.2 |
| Ubuntu | native stdio | 180.85 / 181.32 | 196.89 / 197.63 | 198.2 / 199.0 |
| Ubuntu | native direct | 180.83 / 181.05 | 196.67 / 197.47 | 197.9 / 198.8 |

These process totals are not Fork/SQL measurements: diagnostic entry points skip
MariaDB initialization but add a full FNV pass between reads. At ×8 checksum wall
p50 reaches ~262 ms guest / 522–536 ms native on macOS and ~205–215 ms guest /
194 ms native on Ubuntu. Different read/wait patterns change competing checksum
CPU load, so controls do not perfectly reproduce production restore scheduling.
Full batch CPU divided by concurrency gives macOS guest stdio/direct p50
455.6/388.9 ms at ×1 and 363.0/337.6 ms at ×8; Ubuntu gives 436.9/380.3 and
423.7/372.0 ms. These include startup, checksum and exit; they are not read-only
CPU or evidence that identical useful work becomes cheaper at ×8.

### Files

The redo file `data/ib_logfile0` contributes 96 MiB, `data/ibdata1` 12 MiB, and
three undo files 10 MiB each. Together these five files account for ~99.87% of
bytes. Guest-stdio ×1 per-file read-wall p50 is:

| File | MiB | macOS ms | Ubuntu ms |
|---|---:|---:|---:|
| ib_logfile0 | 96 | 102.71 | 155.22 |
| ibdata1 | 12 | 11.29 | 18.96 |
| undo001 | 10 | 10.05 | 15.83 |
| undo002 | 10 | 9.51 | 15.80 |
| undo003 | 10 | 10.32 | 15.70 |

The redo file dominates both bytes and read time. These medians do not sum to
an observed sample total. Nothing here establishes that any file can be omitted.

## Ubuntu servicing trace: measured fact and source interpretation

Completed/resumed syscall lines were reconstructed by PID. Only read/seek
operations whose resolved descriptor belongs to `snapshot/data/` enter the
file counts; both conditions return exactly 144,885,808 bytes.

| Traced condition | Host read calls | Host seek calls | Requested read sizes | Read/seek worker PIDs |
|---|---:|---:|---|---|
| guest stdio | 4,437 | 2,227 | chiefly 2,205 × 64,512 and 2,210 × 1,024 bytes | 13240, 13241 |
| guest direct | 2,227 | 2,227 | 2,227 × 65,536 bytes | 13256, 13257 |
| native stdio | 2,233 | 0 | chiefly 65,536 bytes | main PID 13261 |
| native direct | 2,227 | 0 | 65,536 bytes | main PID 13265 |

The guest stdio source path therefore amplifies host read calls almost 2×;
this matches libc's buffered/two-iovec source path and Wasmer's separate virtual
reads. The probe itself still makes 2,227 reads in either condition. Direct WASI
bypasses that amplification but retains a host seek per probe read and servicing
on threads other than the guest process main thread (13231 / 13247).

In these **traced diagnostic runs**, summed kernel read durations were 138.13 ms
stdio / 76.51 ms direct guest, versus 78.70/77.45 ms native. Guest seek durations
sum to 65.22/67.57 ms. These heavily traced values must not be subtracted from
untraced probe wall or called physical disk cost. They show syscall shape,
not an exclusive latency breakdown. About 51,382/32,541 completed numeric-return
futex calls occur across the whole guest stdio/direct processes, versus none
in the native controls. Their overlapping aggregate durations are not queue
wait per read. The trace confirms thread handoff/synchronization exists; it
cannot quantify its contribution or prove a specific futex is the bottleneck.

## Attribution conclusions

**Measured fact:** the largest observable excess is inside guest host-volume
read servicing, not destination writes (absent) or warm native file reading.
By difference of distribution medians, guest-direct still exceeds native-direct
by ~77.7 ms macOS and ~147.0 ms Ubuntu at ×1. Bypassing stdio reduces read time
on both platforms, but does not remove most of that remaining boundary cost.
The machines differ; those absolute gaps are not a cross-platform speed ranking.

**Derived comparison:** guest stdio read-wall p50 grows 3.39× macOS / 2.65× Ubuntu
from ×1 to ×8; direct guest grows 4.40× / 2.98×. Native direct grows only 1.57× /
1.04×. Guest read process CPU does not rise with wall time (149→92 ms macOS,
206→171 ms Ubuntu for stdio). This is inconsistent with explaining wall growth
solely as proportionally more CPU work during reads.

**Inference:** runtime servicing, handoff and scheduling/resource contention are
strong candidates for the excess and parallel degradation. ×1 guest process CPU
is substantially above current-thread CPU, consistent with observed worker-thread
servicing. No exact CPU split into libc, WASIX, seek, buffer copy and scheduler
is available. Native reading's small cost in this warm-cache workload weakens a
physical-storage explanation; it does not establish behavior on cold storage.

**Unknown:** exclusive seek versus service-queue versus memcpy/locking cost;
service-thread CPU per operation; macOS kernel-call shape; timer perturbation;
how much of the read-only saving transfers to normal restore with destination
writes and without FNV. No removable destination materialization has been shown.
There is no evidence here requiring a VFS redesign, and no production read-path
optimization has been accepted.

## Restore architecture decision inputs

The results narrow the smallest plausible next options for a separate review:

1. A bounded stdio/iovec-path experiment: keep file inventory and 64 KiB logical
   copy semantics, test whether avoiding the observed amplification helps actual
   restore while preserving integrity and destination behavior. Evidence is
   strongest for a small mechanism here, but these read-only controls are not
   that production experiment.
2. A runtime seek/service-path probe: determine whether repeated seeks and
   blocking-worker handoffs explain the remaining direct-read excess and ×8
   growth, before proposing changes to those boundaries.
3. Host-owned VFS/overlay investigation: consider only if the servicing boundary
   remains dominant after smaller path probes. This measurement neither proves
   it necessary nor establishes its correctness or expected Fork/SQL gain.

No option is selected or implemented. The read-only experiment supports further
bounded servicing work; it does not predict a complete end-to-end FAST result.
