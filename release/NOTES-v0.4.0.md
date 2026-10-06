# mariamem v0.4.0

Terminology note: “This is not CoW” below describes cold-copy preallocation;
it does not deny existing OS CoW on prepared-file private mappings. No running
MariaDB state is cloned. See [current CoW semantics](../docs/copy-on-write.md).
Published release measurements below are retained unchanged.

v0.4.0 makes generated-Go MariaDB the default runtime while preserving the
public Go/Python workflows and cold Snapshot/Fork semantics. This remains a
0.x release; public APIs may change before 1.0.

## Runtime and distribution

Ordinary Go `mariamem.Start(ctx, mariamem.Options{})` runs MariaDB directly in
the consumer process. Generated Go is normal module source compiled by
`go build`; WASM is now a build intermediate. Startup does not materialize a
guest executable, launch a guest subprocess or download a native runtime.
Python wheels contain only the platform Go host and its manifest, with the
generated guest linked in. Neither normal path requires Wasmer or NativeDir.
Explicit legacy Wasmer overrides remain available with a matching verified bundle.

Each DB reconstructs fresh execution/thread/TLS/FD state and private writable
files. Snapshot/Fork reuses prepared files, not live heaps or worker state.
The release includes corresponding GPL source, notices, provenance and hashes;
translation to Go does not remove upstream licensing obligations.

## Measured improvements and fixes

On the fixed Apple M1 / 16 GiB / macOS 27.0.1 / Go 1.26.8 reference environment,
the integrated candidate versus the historical Wasmer baseline measured:

| Boundary | Wasmer p50 | v0.4 candidate p50 |
| --- | ---: | ---: |
| Start → first SQL | 308.5 ms | 38.4 ms |
| prepared Fork → COUNT | 288.7 ms | 104.6 ms |
| Snapshot | 404.6 ms | 399.9 ms |
| ×16 group-ready | 1.890 s | 0.574 s |
| ×16 CPU | 9.463 CPU-sec | 2.814 CPU-sec |
| SQLAlchemy100 Fork | 43.142 s | 20.430 s |

These are reference-machine observations, not universal guarantees. No slow runs
were removed: Start p95 was 593.7 ms and Snapshot p95 was 570.8 ms, both slower
than the historical reference. See the [canonical report](../benchmarks/v04-integrated-candidate.md)
for trial counts, exact identities, boundaries and full distributions.

Known-size cold filesystem copies now pre-size destinations, reducing diagnostic
Snapshot TotalAlloc from 914.83 to 278.17 MiB (**69.6%**). This is not CoW and
does not change the Snapshot format/API. Close now releases the response pipe
FD even when the closed Database handle remains retained. Directory-FD
rename/name-reuse identity and MemFS grow/truncate regression coverage is preserved.

## Compatibility and supported scope

Normal SQL, transactions, constraints, authentication, CLIENT_FOUND_ROWS,
multiple sessions, lifecycle and independent Snapshot/Fork children pass the
existing acceptance suites. SQLAlchemy **44/44** and GORM **32/32**, including
repeated AutoMigrate/schema discovery, passed the preceding hosted candidate
on both supported platforms. Final version/artifact acceptance is required for
the exact release commit; earlier evidence does not approve changed bytes.

Release CI targets macOS 15+ arm64 and Ubuntu 24.04 x86_64 with Go 1.26.8 and
Python 3.14. Package minimums do not imply a broad tested language-version matrix.
Ubuntu wheels are not a manylinux claim. GitHub Release wheels remain the Python
installation channel while PyPI account recovery is pending.

## Important known limitations

- The full generated guest is not Go `-race` clean: **GENERAL SHARED-MEMORY MODEL
  WORK REQUIRED**. No suppression is used; focused handwritten/runtime race
  checks remain enabled. The observed conflicts are not claimed harmless.
- Forced query-timeout reclamation and hard failure containment are not
  guaranteed for non-cooperative in-process execution. Normal cooperative Close
  passes; this does not establish forced guest termination.
- Approximately one-second startup tails remain observable. Earlier experiments
  identified legal guest-side condition-variable behavior; timeouts are not
  shortened or wakeups forced to hide it.
- Go 1.27.0/1.27.1 arm64 are unsupported due to upstream compiler issue
  [#81036](https://github.com/golang/go/issues/81036), `LDPSW: constant is not in pool`.
  An upstream toolchain containing fix `b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa`
  built and ran the unchanged consumer. No mariamem compiler workaround is used.
- macOS post-Close physical footprint is distinct from live Go heap. The
  [lifetime investigation](../benchmarks/v04-snapshot-memory-lifetime.md) concluded
  **OS PHYSICAL ACCOUNTING DOMINATES**; it is not claimed harmless or immediately
  reclaimable.

Broader shared-memory adaptation, forced failure containment, prepared-scaling
memory work and stable-MariaDB migration remain deferred; see
[project status](../docs/project-status.md).
