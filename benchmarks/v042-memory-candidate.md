# v0.4.2 checked pure memory32 candidate on v0.4.1 heap backing

**MEMORY SEMANTICS FIX READY FOR MMAP INTEGRATION** — a bounded semantics
prerequisite for the next human-authorized mmap candidate, not a release or
cross-platform mmap approval. The measured cost is acceptable for the tested
Disposable use boundaries; CPU regression is material and recorded below.
No mmap or broad translator/runtime redesign was integrated. No merge, version
bump or release was performed.

## Candidate scope and identity

Base: released `v0.4.1`, `547fb1a6c01e5edb0daa27de273a2e94e66eb098`.
Branch: `experiment/v042-memory-candidate`.
Basis: [generic-memory spike](https://github.com/masahitojp/mariamem/blob/49817bb8c918be6215f6dfe5a4bdce98ab8d77ab/benchmarks/v042-generic-memory.md).
Actual execution: macOS 27.0.1 arm64, Go 1.26.8, Node 26.9.0 WASM reference.

The guarantee is the **released default `-pure` memory32 lowering**, its standard
scalar/SIMD/atomic memory accesses and current guest recipe. It is not a claim
about memory64, non-pure/fused assembly backends, extra opt-in generator modes,
a full race-clean guest or universal host-import/failure containment.
Ubuntu execution remains a subsequent candidate/platform acceptance requirement.

Pinned converter remains `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`; the three
existing release patches are unchanged. Guest SHA-256 remains
`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
The initial 256 MiB / max 2 GiB Go-heap backing, stable base, grow, ownership,
worker model, host adapter and Snapshot/Fork architecture are unchanged.

[Patch](spikes/wasm2go/pure-memory32.patch),
[regression/replay workflow](spikes/memory-candidate/README.md),
[measurements](memory-candidate-evidence/measurements.json),
[all 80 generation rows](memory-candidate-evidence/generations.csv).

## Production-quality change

The converter patch changes **nine files, +211 / −25 lines**: five implementation
files and four unit-test files. The normal translation recipe applies it and
records its checksum. Canonical regeneration now runs the deterministic fixture
gate before source import. Generated Go, raw/candidate input manifests and
provenance were regenerated through the canonical pipeline, without call-site or
function/address-specific edits. The large generated diff is mechanically
produced, not a maintenance patch to individual guest bodies.

The previous experimental CLI option was removed: pure memory32 always checks.
The shared predicate reads current logical size and checks:

```go
addr <= bound && offset <= bound-addr && width <= bound-addr-offset
```

Unsigned dynamic memory32 address, static offset and actual typed access width
remain separate. Short-circuit subtraction prevents overflow; addition and
unsafe dereference occur only after success. Scalar accesses retain typed
loads/stores and sign/zero extension. SIMD uses its existing width-specific EA
helpers. Inline atomic loads/stores now use checked atomic EA helpers while
retaining Go atomic intrinsics and natural-alignment semantics.

Locations in the pinned converter:

- `internal/codegen/emit_memops.go`: `unsafeDerefExpr`, `memOpSpec.accessWidth`,
  `emitAtomicInline`.
- `internal/codegen/helpers/helpers.go`: `memoryInBounds`, `memoryEA`, common
  scalar trap, and existing `atomicEA` / `simdEA` paths.
- `internal/codegen/translate.go`: `pureMemory32`, `compileBodyViaSSA` and the
  checked store-merge gate. Keep wrapping i32.add separate from non-wrapping
  memarg offsets; exclude unsafe address folding/memory forwarding.
- `internal/ssa/{ssa.go,op.go}`: observable `MemoryMayTrap` loads survive DCE.

A final audit also found `MergeF16Stores` explicitly accepts earlier-trap /
no-partial-write relaxation. Checked pure memory32 keeps the original individual
stores: earlier valid stores must remain visible when a later instruction traps.
A real synthetic packed-store group verifies the gate, with the unchecked merge
as a positive control. This is a bounded conservative exclusion, not a redesign.
Current guest output was proven **byte-identical to the measured output** after
adding this guard, so the performance samples remain applicable.

Corresponding-source selection includes the patch/tests. Notices and upstream
archives remain intact. The existing license attribution was rebound to the new
generated inventory only after all **34 retained-function examples** were
rechecked in definitions and the actual measured candidate binary. Historical
host evidence remains explicitly historical; release approval was not invented.
The distribution inventory and Python mirror were synchronized.

## Correctness and compatibility

The final deterministic suite has **2,472 matrix cases**, zero reference
mismatches, **1,693 expected guest traps** in one surviving Go process, plus
**seven maximum-boundary trap checks**. Reviewed reference rows include values
and full logical-memory hashes. The baseline's known failures are documented in
49817bb; unsafe baseline fixtures were not rerun as host-crash experiments.

Coverage includes 8/16/32/64-bit scalar loads/stores, signed extension, floating
bit-preserving paths, dynamic and constant addresses, large static offsets,
32-bit arithmetic wrap, logical-end crossings, SIMD full/splat/zero/extended/
lane loads and stores, coalesced loads, atomic full/subword load/store/add-RMW,
natural alignment, and dropped scalar/SIMD/atomic loads. Fourteen multi-store
sequence cases compare prior partial writes with WASM behavior, rather than
incorrectly requiring the whole function to leave memory unchanged on trap.

Grow checks cover before/after access, repeated grow, old-data preservation,
zero-filled new ranges, stable base, maximum, failed/unsigned-minus-one grow,
and unchanged size/data/base after failure. Reduced fixtures use 64 KiB pages
with three maximum pages; this is not a physical 2 GiB maximum-growth stress test.
Actual generated MariaDB accesses additionally exercise its 256 MiB logical
boundary, crossing, static-offset overflow and post-grow access.

Focused acceptance passed:

- SQL create/insert/update/delete/select and two distinct held sessions;
- current auth contract: local root/empty password accepted; wrong password and
  unknown user rejected with 1045; the existing connection remains usable;
- Snapshot plus two independent sequential Fork/use/Close cycles;
- three repeated Start/SQL/Close cycles and idempotent repeated Close;
- real generated accesses, shared grow/base/atomic visibility, private worker
  TLS/stack globals and join;
- focused base/thread/TLS/futex race tests and adapter/guest/host/snapshot race
  tests. This is not full-guest race acceptance.

Independent canonical regeneration matched the checked-in source byte-for-byte.
The final canonical check passed Go tests, scoped vet, public-source checks and
**432 Python tests, six intentional skips**. Fixtures replay from reviewed
reference data without requiring Node/Wasmer. Initial harness/auth assumptions
and stale license bindings failed visibly and were corrected; they were not
recorded as passing or as completed performance samples.

## Cost against unchanged v0.4.1

Twenty fresh parent processes per mode, alternating order. Identical probe and
workload: Start → SELECT 1 → create/seed/count 1,000 rows → 50 CRUD loops (200
statements) → normal Close. CPU is process user+system across threads, including
client/host/runtime within the stated intervals. Process/module initialization
before Start is excluded. No cache flush, forced GC or removed complete trials.
The table uses medians; raw rows, means and nearest-rank p95 are retained.

| Boundary | v0.4.1 | Candidate | Absolute delta | Relative delta |
| --- | ---: | ---: | ---: | ---: |
| Start → SQL | 46.93 ms | 65.82 ms | +18.88 ms | +40.2% |
| Start → 1,000-row fixture | 50.27 ms | 73.50 ms | +23.22 ms | +46.2% |
| 200 CRUD statements | 31.96 ms | 39.40 ms | +7.44 ms | +23.3% |
| Start → SQL CPU | 32.98 ms | 49.86 ms | +16.88 ms | +51.2% |
| Start → fixture CPU | 40.30 ms | 65.74 ms | +25.44 ms | +63.1% |
| 200 CRUD CPU | 36.93 ms | 53.24 ms | +16.30 ms | +44.1% |
| Whole lifecycle CPU | 80.06 ms | 121.31 ms | +41.25 ms | +51.5% |

One-second startup tails remain: two/20 baseline, four/20 candidate exceed 500 ms.
Start→SQL mean is **148.11→265.29 ms**; p95 **1054.60→1068.87 ms**. These are not
trimmed. Twenty trials do not establish whether the changed execution timing
causes a higher tail probability; that uncertainty belongs in further acceptance.

One 20-generation process per mode also performed the same fixture/CRUD workload:

| Repeated boundary | v0.4.1 median | Candidate median | Delta |
| --- | ---: | ---: | ---: |
| Start → SQL | 315.10 ms | 281.67 ms | −33.43 ms (−10.6%) |
| Lifecycle CPU/gen | 289.18 ms | 315.29 ms | +26.11 ms (+9.0%) |
| Close | 2.79 ms | 3.49 ms | +0.70 ms (+24.9%) |

The first/last-five Start→SQL medians were **60.72→314.56 ms** baseline and
**67.93→280.86 ms** candidate. Allocation/reuse degradation remains in both.
The lower candidate repeated wall time is not evidence that this correctness
change fixes heap degradation: one process per mode does not isolate allocator /
OS scheduling variance. Last-five Start→SQL CPU is almost identical,
**243.96→243.65 ms**. FDs stayed **5→5**, post-Close goroutines **1→1** in every
record. Both retain the same large backing/accounting model; HeapAlloc at Close
is not a retained-object leak diagnosis.

## Attribution, risk and recommendation

Compiler analysis: `memoryInBounds` inlines (cost 29), `memoryEA` does not (cost
100, budget 80). Checks therefore add calls and logical-size reads on valid
scalar paths. Trapping-load retention and the conservative optimizer exclusions
are also part of the combined candidate; none were independently optimized.

Separate 8,000-statement CRUD profiles, excluded from the primary timing table,
show candidate `MemoryEA` cumulative **40 ms / 1.52 s sampled CPU (2.6%)**.
Syscalls, kevent and pthread signal/wait account for most samples. Profiled CRUD
CPU was **1.081→1.654 s**. Non-inlining is a concrete possible bounded follow-up,
but **was not shown to dominate** this cost. The observed syscall/wakeup increase
is not a causal proof of its mechanism; do not assume inlining alone removes the
regression. No automatic helper optimization or scheduler redesign followed.

For the tested Disposable use, +19 ms startup / +23 ms seeded readiness and
+7 ms per 200 CRUD statements are acceptable in exchange for required WASM
correctness. The historical Wasmer [baseline](v04-baseline.md) had ~308 ms
Start→SQL and ~312 ms seeded readiness; those are context, not a new concurrent
Wasmer control. The current candidate keeps a substantial creation benefit.
CPU-heavy/long SQL consumers may judge +44–63% interval CPU differently; this is
not a no-regression or exhaustive workload claim. Monitor tails and CPU in the
next platform/mmap candidate acceptance.

Budget behavior: each owned run used a 16 GiB free-space floor, 4 GiB disk budget,
6 GiB sampled descendant RSS / 8 GiB physical budget, CPU 180/200-second limits
per process, FD 256, no cores and timeouts. No disk/memory budget violation was
needed to obtain these results. Minimum recorded free space stayed above 53 GiB;
source/build peaks remained below budgets. Shared expensive caches are outside
temp and retained. Compact JSON/CSV/reference results/checksums and selected raw
profiles are retained; reproducible generated/build copies are disposal targets.

Human decision: review this bounded prerequisite; if accepted, apply only the
isolated mmap backing abstraction next, validate initial protection/grow/zero/
shared-worker/ownership/teardown on macOS and real Ubuntu, then compare the same
small lifecycle boundaries. No CoW, Fork micro-optimization, broad race adaptation
or v0.5 work is part of this candidate.
