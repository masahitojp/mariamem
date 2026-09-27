# Read servicing at the snapshot host-volume boundary

## Scope and status

This attribution probe starts from production candidate
`8b44e9db569c0ea04e45ae6c60fc8ecf54b7b8ab` on
`experiment/restore-host-volume`. It does not include the old prepared-auth
experiment history. Production prepared RSA keys, within-call validation and
Snapshot/Fork remain unchanged. No restore optimization is implemented.

**Measurements pending:** the experiment workflow will produce independent
macOS arm64 and Ubuntu 24.04 x86_64 artifacts. New numerical conclusions must
wait for those artifacts. Previous production Fork/SQL p50 (~517/539 ms) and
restore (~196/231 ms) are context, not measurements of this read-only probe.

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

## Analysis to complete from CI artifacts

For each platform and ×1/×4/×8, compare read wall and CPU distributions for all
four controls, then identify dominant files by bytes and read time. Compare
process with current-thread CPU and batch CPU; inspect Ubuntu snapshot-file
read/seek syscall counts and worker identities. Report complete lifecycle and
checksum/setup costs separately from timed reads.

Unknowns until measured: the libc contribution; actual runtime service-thread
path; kernel-read contribution; scheduler/lock wait fraction; whether ×8 growth
is explained by servicing rather than byte transfer. Even afterward the probe
will not uniquely attribute every runtime lock, memcpy or queue wait. Direct
runtime instrumentation would be a separate decision, not assumed necessary.

## Restore architecture decision inputs

The smallest plausible next options are conditional, not selected here:

- A large stdio/direct gap would support a bounded libc/iovec servicing probe.
- Cheap native reads but expensive direct guest reads would support measuring
  runtime seek/service scheduling/buffer transfer before a larger redesign.
- Similar CPU-dominated direct/native transfer would support a byte-transfer
  investigation; high waiting with low kernel-read time would support service
  scheduling attribution.
- A host-owned VFS/overlay investigation becomes better motivated only if the
  servicing boundary is shown to dominate and smaller changes cannot address it.

No current measurements prove a removable copy or justify choosing one of
these options. Destination materialization is intentionally absent, so this
probe cannot by itself predict optimized end-to-end Fork latency.
