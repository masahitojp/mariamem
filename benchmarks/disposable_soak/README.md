# Disposable lifecycle diagnostic

This harness exercises the released public Go default (`Options{}`), without
changing production code. It runs one long-lived consumer process with 16 fresh
DBs per generation, first `SELECT 1`, private transactional CRUD/rollback, then
concurrent Close. All Database/SQL handles are dropped between generations.
There is no Snapshot, forced GC, FreeOSMemory, allocator tuning or guest patch.

Run under the maintainer's exclusive measurement lock, with no other heavy build
or benchmark running on the machine:

```sh
GOTOOLCHAIN=go1.26.8 python3 benchmarks/disposable_soak.py \
  --work /absolute/disposable-work/soak --databases 16 --generations 50
```

The runner builds the harness and the existing OS-counter helper. `metadata.json`
records source/toolchain/binary identity; `checkpoints.jsonl` is flushed after
every generation so an externally terminated diagnostic retains partial evidence.
On macOS, primary memory is `phys_footprint`; on Linux it is PSS. RSS and Go heap
are separate fields. `/dev/fd` or `/proc/self/fd` enumeration counts the observer's
directory FD consistently; comparisons use the same observer at every checkpoint.
Counters sample ready/after Close, not the transient maximum between checkpoints.
Parent observer overhead is included in CPU; short-lived counter-helper CPU is
not. No DB subprocess is created by this harness.

## Predeclared safety and interpretation

- Stop immediately on any SQL/start/close/counter failure.
- Start/SQL contexts are 30 seconds; the external diagnostic-process watchdog is
  15 minutes. This is not forced in-process guest reclamation.
- Stop after ready physical footprint exceeds 12 GiB, or after-Close HeapAlloc
  exceeds 10 GiB, to protect the 16-GiB reference machine.
- Stop after three consecutive after-Close samples exceed baseline by 16 FDs or
  64 goroutines, or three consecutive generations take at least 10 seconds.
- Compare ten-generation windows, including the first and last; do not discard
  warm-up or slow generations. Resource plateau requires stable FD/goroutine
  counts and absence of sustained growth in the late memory envelope. Latency
  degradation is a sustained late-window increase, not a single legal startup
  tail. Physical footprint alone does not prove reachable-object retention.
- A 50-generation pass is bounded evidence for this workload and machine, not a
  proof for arbitrary workloads, failure paths or indefinite runtime.

No fix is implemented by this lane. Product resource budgets remain a human
decision after the independent lane results are compared.
