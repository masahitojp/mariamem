# mariamem v0.4.6 — Product Usability & Validation (draft)

Not release authorization. Canonical metadata remains 0.4.5 until final approval.

- Go adds `LoadSnapshot(ctx, path, opts)` for persisted prepared baselines. Import
  validates and owns the backing; mutable Forks remain independent of the source
  path and parent lifetime. The Snapshot format is unchanged.
- Comparable Go/Python guides clarify Fresh, prepared reuse, optional persistence
  and explicit cleanup. Python's existing loading capability is unchanged.
- Bounded external consumers passed Go 1.26.8 and 1.27.0/1.27.1/1.27.2 on macOS
  arm64; Ubuntu Go1.27.2 execution was emulated pending native release evidence.
  The minimum remains Go1.26.0 and mysql development/test client remains v1.9.3.
- Representative types and disposable test workloads were validated with stated
  driver, guest/native-version and isolation-model limits. This is not a full
  MySQL compatibility guarantee or a permanent performance promise.
- Go1.27 has no demonstrated practical suite speed advantage. No toolchain,
  generated code, guest, filesystem or Snapshot performance optimization is added.

Known limitations: full generated-guest races and non-cooperative forced reclaim
remain outside guarantees; retained Snapshots consume prepared-file FDs; import
checks cancellation before/after existing copy/hash, not within it. macOS15+
arm64 and Ubuntu24.04 x86_64 remain the product platforms.

Future work: the v0.5 guest decision remains separate; broader workloads, types,
frameworks and fixture ergonomics remain v0.6 Discovery. Filesystem buffer growth
and synchronization are profile observations, not accepted optimizations.
