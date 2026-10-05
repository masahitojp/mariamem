# mariamem v0.4.2

v0.4.2 improves the **Disposable memory lifecycle** of generated-Go MariaDB.
Released pure-memory32 accesses now use non-wrapping effective addresses,
access-width-aware logical bounds and atomic alignment checks. Scalar, SIMD
and atomic/RMW out-of-bounds accesses produce controlled WASM traps; worker
failures are captured and joined rather than terminating the host process.
Host imports respect the current logical memory range.

On macOS arm64 and Ubuntu 24.04 x86_64, shared linear memory reserves a stable
2 GiB mmap range instead of allocating a 2 GiB Go backing array per instance.
It initially enables 256 MiB, preserves data/base-address and zero-fill semantics
through memory.grow, and releases the mapping after cooperative workers exit.
Initialization, startup, controlled guest failures and repeated Close retain
correct ownership; failed unmap retains a retryable owner.

The accepted bounded macOS campaign shows approximately stable 100-generation
latency/CPU and multi-DB resources. Versus controlled heap, settled lifecycle CPU
fell about 77%; repeated Snapshot/Fork cycle CPU fell about 43%. Fresh Start→SQL
adds about 10 ms versus v0.4.1 in that campaign, an accepted correctness cost.
These are workload-specific measurements, not performance guarantees. See the
[candidate report](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md)
for controls, budgets, startup tails and comparison limits.

SQL/auth/session and Snapshot/Fork behavior, the guest, explicit legacy fallback
and corresponding-source/NOTICE/license obligations are preserved. Supported
release targets remain macOS 15+ arm64 and Ubuntu 24.04 x86_64, validated with
Go 1.26.8 / Python 3.14. Native contract/product/ORM acceptance passed on both;
Release CI verifies the exact final-version source and artifacts before release.
Memory64, full generated-guest race adaptation and non-cooperative forced
termination remain outside scope. No Wasmer retirement, Fork optimization or
v0.5 guest update is included.
