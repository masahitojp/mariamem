# Controlled traps + mmap: small integration experiment

Exact basis: `2d633531acd7f81f7abb3ed613435b5d4a090342`.
The earlier mmap spike is implementation evidence. Its join/release sequence
cannot be copied unchanged: `SpikeWait` now relays retained worker failures and
can panic. Release uses the non-panicking cooperative join before unmap instead.

`correctness.py` applies the pinned shared-memory owner callback, regenerates,
and runs the unchanged reviewed memory32 fixture on heap and mmap. It runs the
controlled-trap suite, mapping ownership/failure tests, actual initial/max/grow/
TLS/futex tests, SQL/auth/reconnect/sessions/Snapshot/Fork/Close, focused runtime
race checks, independent regeneration, license-symbol evidence and canonical
checks. No performance work occurs until that gate passes.

`measure.py` requires a clean committed candidate and the matching passing
provenance. It archives exact sources for v0.4.1, the controlled-traps heap
basis, and the mmap candidate. Identical probes run 12 fresh processes per state
with rotated order, then one process with 20 generations per state. Each does
Start → SQL → 1,000-row fixture → 200 CRUD statements → Close. CPU samples omit
the post-Close observation helper. Every complete observation is retained.

`summarize.py` produces medians/p95, blocks of five, first/last generation,
resource ranges, complete JSONL and per-generation CSV. No tail filtering,
forced GC, helper inlining, startup-tail adjustment or workload expansion.

Use the external experiment-workspace tooling: minimum free 16 GiB, workspace
budget 6 GiB, descendant RSS 6 GiB / physical footprint 8 GiB, CPU 180/200 s,
FD 256 and phase timeout guards. Prepare a new workspace for each phase. Pass
checksum-bound `MARIAMEM_CACHE` and `MARIAMEM_RELEASE_GUEST` inputs. Use shared
Go caches outside owned scratch. Performance holds the measurement lock.

Stop after the small comparison. Real Ubuntu execution, longer/multiple-DB soak,
repeated Snapshot→Fork disposal measurement, installed consumer acceptance and
canonical benchmarks remain separate gates. Non-cooperative root/worker forced
termination is not implemented; a live agent keeps the mapping owned.
