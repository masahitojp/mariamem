# v0.4.2 controlled traps + mmap: bounded integration review

Decision: **MMAP + CONTROLLED TRAPS READY FOR PLATFORM/SOAK VALIDATION**.
This is an experiment branch, not approval to integrate, merge or release.

## Exact basis and scope

- Released v0.4.1: `547fb1a6c01e5edb0daa27de273a2e94e66eb098`.
- Controlled-traps heap basis: `2d633531acd7f81f7abb3ed613435b5d4a090342`.
- Committed, measured mmap runtime: `88e9f397e57ada7b0e4268d8775af4d0a134230e`.
- Branch: `experiment/v042-mmap-controlled`, directly descended from that heap basis.
- Execution: macOS 27.0.1 arm64, Go 1.26.8. No Ubuntu execution in this task.

The earlier mmap spike supplied implementation evidence, not a cherry-pick.
The controlled-trap lowering, SSA retention and worker panic capture remain
unchanged. Scope is the released pure-memory32 backend. No CoW, forced worker
termination, memory64, guest race adaptation or helper optimization was added.

## Backing and ownership

`code/base/memory_mapping.go` reserves one contiguous 2 GiB anonymous mapping
with `PROT_NONE`, then enables the initial 256 MiB with read/write protection.
Pages are demand backed; read/write protection does not mean physical RAM was
eagerly committed. The original mapping slice and base pointer never move.
Generated accesses retain their non-wrapping, width-aware logical `MemSize`
checks and controlled trap path; OS protection is not the trap mechanism.

`memory_backing_unix.go` passes the mapping to the existing `NewWithMemory`
constructor. The two-file converter patch adds an optional grow callback. Under
the existing shared memory lock it enables the new range before publishing
`MemSize`; failure returns -1 without changing logical size. Old pages remain
untouched and new anonymous pages are zero filled. Module/worker copies share
the owner callback, logical size and stable base. Guest bytes contain no Go
pointers; Go ownership objects stay outside the mapping.

The execution owner registers release immediately after constructor ownership
transfers. `memory_lifetime.go` uses non-panicking `WaitThreads` before unmap:
using `SpikeWait` here would relay a worker trap by panicking and skip release.
Retained worker failure becomes an error after cooperative join. The exact
original mmap slice is released once; repeated Close succeeds without another
unmap. Partial initialization closes before ownership transfer. Constructor
initialization does not launch workers. A failed `munmap` retains its owner in
`MemoryReleaseError`, exposed through preserved error wrapping for an explicit
Close retry; counters never label failure as successful release.

Non-cooperative root/worker termination remains out of scope. A live worker
keeps ownership alive; memory is not forcibly unmapped underneath it.

## Correctness gate

[Compact gate](v042-mmap-controlled-correctness.json) records all passing phases.
The unchanged reviewed memory32 fixture passes on heap and mapped backing:
2,472 cases, including 1,693 expected traps, plus seven max-boundary traps.
Values, trap outcomes and partial effects match the reviewed semantic reference.
Coverage includes scalar widths, SIMD, atomic loads/stores/RMW and alignment,
static-offset overflow, crossing OOB, observable dropped loads, valid accesses,
multiple grow, preservation, zero fill, maximum and failed grow.

The real generated module verifies initial 4,096 pages / maximum 32,768 pages,
stable base, worker visibility, TLS, futex and failed protection/grow state.
Constructor Go allocation was 284,112 bytes, not a 2 GiB heap array.
The mapped fixture made and released 2,473 mappings, leaving zero active.

Controlled root/worker scalar, SIMD and atomic guest failures all survived in
the host. Ten failed executions released ten mappings and a subsequent valid
instance worked. A worker trap with a live cooperative peer retains the mapping
until that peer exits. Deterministic owner tests cover reserve/protect failure,
partial constructor panic, startup failure after worker launch, repeated and
concurrent Close, failed unmap retaining ownership, and retry exactly once.

SQL/CRUD, authentication/rejection/reconnect, multiple sessions, independent
Snapshot/Fork results, repeated Start/Close and failure cleanup pass. Focused
runtime/base/thread/TLS/futex tests and mapped controlled-failure tests pass
with `-race`; this is not a full generated-guest race census. Canonical Go
test/vet, Python checks (432 passed, six skipped), public-source checks and
byte-identical independent regeneration pass. Guest/source/notices remain
unchanged; generated provenance and positive license-symbol evidence are updated.

## Small three-way comparison

Each fresh trial is a new process. Twelve trials per state ran in rotated order,
then one process per state ran exactly 20 generations. All execute Start → SQL →
1,000-row fixture → 200 representative CRUD statements → Close. CPU is process
user + system time for that lifecycle, excluding the post-Close observer.
No forced GC, FreeOSMemory, profiling or tail exclusion was used. The repeated
campaigns ran sequentially in released/heap/mmap order, so this is a bounded
local comparison, not a randomized canonical benchmark.

All table entries are medians; milliseconds unless stated otherwise.

| Metric | v0.4.1 | controlled heap | controlled + mmap |
| --- | ---: | ---: | ---: |
| Fresh Start → SQL | 44.35 | 61.67 | 60.12 |
| Fresh Start → 1,000-row fixture | 47.81 | 69.43 | 67.81 |
| Fresh CRUD, 200 statements | 32.12 | 39.34 | 40.92 |
| Fresh CRUD CPU, seconds | 0.03649 | 0.05197 | 0.05368 |
| Fresh lifecycle CPU, seconds | 0.07889 | 0.11719 | 0.12235 |
| Fresh Close | 2.37 | 1.96 | 2.99 |
| 20-generation ready | 296.20 | 254.62 | 60.87 |
| 20-generation Start → SQL | 297.04 | 255.60 | 61.77 |
| 20-generation lifecycle CPU, seconds/gen | 0.27903 | 0.30717 | 0.12489 |
| 20-generation Close | 2.77 | 2.11 | 2.65 |

Against controlled heap, mmap reduces repeated Start → SQL by **193.83 ms
(75.8%)** and CPU by **0.18228 s/gen (59.3%)**. Repeated CRUD CPU remains
approximately unchanged (+0.00046 s / +0.9%), locating the large benefit outside
the CRUD execution cost. Fresh mmap versus controlled heap is -1.55 ms / -2.5%
for Start → SQL, +1.58 ms / +4.0% CRUD, +0.00516 s / +4.4% lifecycle CPU and
+1.04 ms Close. These small fresh differences should not be overinterpreted.

Against released v0.4.1, fresh mmap adds **15.78 ms / 35.6%** Start → SQL,
20.00 ms / 41.8% Start → fixture, 8.80 ms / 27.4% CRUD and 0.04346 s / 55.1%
lifecycle CPU. Most of this correctness cost is already present in controlled
heap. Startup remains about 60 ms and repeated disposal removes a much larger
heap-generation tax. This supports proceeding to validation, not a zero-cost
claim or broad performance approval. No helper-cost profile was taken.

Fresh Start → SQL nearest-rank p95: 74.74 / 1,068.40 / 72.64 ms. The heap
outlier is retained. Repeated mmap has a 135.87 ms first-generation Start → SQL
outlier; p95 is 66.14 ms and all 20 observations remain in the evidence.

| Generation block | v0.4.1 ready / CPU | controlled heap ready / CPU | mmap ready / CPU |
| --- | ---: | ---: | ---: |
| 1–5 | 51.92 ms / 0.09497 s | 62.64 ms / 0.12484 s | 62.81 ms / 0.13284 s |
| 6–10 | 318.52 ms / 0.29163 s | 252.50 ms / 0.30730 s | 60.84 ms / 0.12434 s |
| 11–15 | 305.37 ms / 0.28351 s | 304.67 ms / 0.31132 s | 62.68 ms / 0.13092 s |
| 16–20 | 295.10 ms / 0.28182 s | 256.74 ms / 0.31181 s | 58.75 ms / 0.12450 s |

Mmap shows no worsening trend over these 20 generations. This does not establish
long-run, multi-DB or repeated Snapshot/Fork stability.

## Accounting, release and guards

Post-Close generation-20 observations, MiB:

| Counter | v0.4.1 | controlled heap | controlled + mmap |
| --- | ---: | ---: | ---: |
| HeapAlloc | 2,200.32 | 2,200.31 | 152.29 |
| HeapSys | 6,302.78 | 6,306.72 | 365.97 |
| RSS | 3,169.31 | 3,639.98 | 326.00 |
| macOS physical footprint | 4,337.19 | 4,337.00 | 276.34 |
| FD / goroutines | 5 / 1 | 5 / 1 | 5 / 1 |

Go heap counters exclude mmap. Post-Close heap objects can await normal GC;
these observations do not prove retained-object leaks. Mapping counters are
virtual/protection counters, not physical footprint. All 20 mmap observations
have zero active/reserved/read-write mappings after Close; creates/releases
finish at 20/20, release failures at zero. The OS accounting above independently
shows that removing the Go array improves actual process resource cost.

External experiment-workspace tooling enforced 16 GiB minimum free and 6 GiB
owned disk budgets, plus descendant RSS 6 GiB / physical 8 GiB, CPU 180/200 s,
FD 256 and phase timeouts. No observed budget violation occurred. Correctness
peak owned disk was 1.59 GiB; measurement peak 1.33 GiB. Measurement minimum free
was 37.85 GiB, sampled peak RSS 3.57 GiB and physical footprint 4.24 GiB.
Guard receipts and log checksums are retained with the compact evidence.

Cleanup dry-run marks the completed measurement scratch (about 0.97 GiB) REVIEW
because its archived source contains a `benchmarks` directory. It remains intact,
along with correctness raw evidence, the experiment worktree, shared Go caches,
converter cache and released guest. No uncertain legacy residue was deleted.

## Implementation size, risk and remaining gates

The runtime commit adds 201 lines of handwritten owner/factory/lifetime code,
six generated base lines and small common constructor/driver changes. The owner
converter patch affects two shared files, not generated functions or addresses.
All generated function packages remain byte-identical to the controlled heap
basis. The runtime commit is 28 files, +1,493/-19 including regression tests,
mechanical recipes, provenance/license evidence and the measurement harness.
The final review commit adds evidence/documentation and a ready-stat summary;
it does not change the measured runtime.

The implementation is bounded enough to validate further. OS mapping/protection,
ownership error recovery and cooperative shutdown need careful review. The
generated instruction contract is validated; malformed host-import buffer
arguments are a separate coverage gap. In particular, `base.AccessMemory`
still passes the maximum-sized slice to host helpers. Their logical-buffer
validation must be audited before production approval; this report does not
claim malformed-import survival, nor an observed failure in that untested path.

Before v0.4.2 integration:

1. Real Ubuntu 24.04 x86_64 execution of memory/trap/ownership/product acceptance;
   cross-compilation and historical mmap results are not acceptance of this SHA.
2. Longer 1-DB 50/100 generations and bounded multi-DB runs with resource guards.
3. Repeated Snapshot → Fork → use → Close measurements, preserving correctness.
4. External Go consumer, installed Python wheel, SQLAlchemy and GORM acceptance
   on both supported platforms, and the host-import logical-buffer audit above.
5. Later canonical performance comparison and production review of exact source,
   provenance/notices, lifecycle errors and supported-platform behavior. Release
   CI, merge, tagging and publication remain separate human decisions.

No larger campaign was started. Non-cooperative forced termination is an explicit
existing limitation, not a feature implemented or promised by this candidate.

Evidence: [campaign/source/binary hashes](v042-mmap-controlled-evidence/campaign.json),
[summary](v042-mmap-controlled-evidence/summary.json),
[all 96 observations](v042-mmap-controlled-evidence/measurements.jsonl),
[all 60 repeated generations](v042-mmap-controlled-evidence/generations.csv).
