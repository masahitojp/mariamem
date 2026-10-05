# v0.4.2 bounded generated-Go memory correctness spike

Decision: **MULTIPLE BOUNDED MEMORY RULES REQUIRED**.

A common effective-address predicate covers the tested scalar, SIMD and atomic
memory32 accesses in mariamem's `-pure` generation mode. That predicate alone is
insufficient: atomic alignment, wrapping integer arithmetic before a memory
instruction, and observable trapping loads require additional bounded rules.
The prototype demonstrates those rules without a translator redesign. It is
experiment-only, not a production integration or a full translator correctness
proof. No mmap backing, performance benchmark, soak, merge or release was done.

## Identity and evidence

- Released base: `v0.4.1`, `547fb1a6c01e5edb0daa27de273a2e94e66eb098`.
- Experiment branch: `experiment/v042-generic-memory`, created from that exact tag.
- wasm2go fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`, with the three existing
  release patches (`imported-memory`, `import-function-index`, `relaxed-madd`).
- Archive SHA-256: `1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f`.
- Released guest SHA-256: `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
- Actual execution: macOS arm64, Go 1.26.8; Wasmer 7.4.2 semantic reference.
- [Prototype patch](spikes/generic-memory/generic-memory.patch),
  [compact summary](spikes/generic-memory/evidence/summary.json),
  [fixtures](spikes/generic-memory/evidence/fixtures),
  [phase logs and receipts](spikes/generic-memory/evidence),
  [checksums](spikes/generic-memory/SHA256SUMS).

The receipt's `base_sha` is `d492e52`, the external workspace-tooling checkout;
`released_base` in the campaign records identifies the actual runtime source.
Full guest regeneration used the pinned input, the existing MemFS transformation
and existing data embedding. Handwritten runtime/ownership code stayed at the
tag. The Go-heap backing, initial 256 MiB, maximum 2 GiB and stable base model
were retained. Generator-emitted `sharedimage_mmap.go` is an existing upstream
artifact, not integration of the linear-memory mmap experiment.

## Required semantics

The [WASM memory instructions specification](https://webassembly.github.io/spec/core/exec/instructions.html#memory-instructions)
requires a non-wrapping effective address from the unsigned dynamic memory32
address plus the instruction's static offset. The entire accessed byte range
must be inside the current logical memory. Ordinary `i32.add` still wraps modulo
2^32: folding that arithmetic into a non-wrapping memory offset changes semantics.
The [threads specification](https://webassembly.github.io/threads/core/exec/instructions.html#memory-instructions)
also requires naturally aligned atomic accesses. Guest OOB must trap before
an unsafe host dereference; backing capacity and host signals are not bounds.

The reduced shared-memory fixture has one initial page, three maximum pages,
153 exported functions, and 1,960 cases before and after a one-page grow:

| Family | Cases | Coverage |
| --- | ---: | --- |
| Scalar | 457 | 8/16/32/64-bit loads/stores; offsets 0, 4, 65536, 0xffffffff; last valid, crossing, negative/high addresses; positive/negative wrapping i32.add; dropped load |
| SIMD | 891 | v128 load/store; splats; load32/64_zero; load8x8_u; 8/16/32/64-bit lane loads/stores; coalesced two-load path |
| Atomic | 612 | Full/subword load/store and add RMW at 8/16/32/64 bits; natural alignment, logical boundary and large static offsets |

The runners check valid values, complete logical-memory SHA-256 before/after,
and unchanged memory on trapping stores/RMW. They also assert grow(0), multiple
grow, old-data preservation, zero-filled new range, stable base, grow to maximum,
and unchanged state after over-maximum/unsigned-minus-one failed grow. The small
fixture tests the algorithm at three pages; this is not a new physical 2 GiB
stress test. The actual guest smoke additionally checks its 256 MiB initial
logical boundary and growth without moving the base.

## Responsible lowering and runtime paths

Paths below refer to the pinned converter source, rather than to individual
MariaDB functions. Original source line numbers are approximate; functions are
stable identifiers and the patch records exact edited contexts.

| Location | Current behavior / problem | Prototype |
| --- | --- | --- |
| `internal/codegen/emit_memops.go`: `emitMemLoadExpr`, `emitMemStoreStmt`, `unsafeDerefExpr` (~147), `memOffsetExpr` (~215), load/store specs (~380–460) | Scalar typed `unsafe.Add` dereferences bypass logical bounds. Dynamic `uint32(base)+offset` can wrap; constant handling differs. Header assumes validation/C++ already supplies bounds, which does not establish dynamic safety. | Preserve typed access and extension behavior; compute/check unsigned dynamic address, separate static offset and actual access width before dereferencing. |
| Same file: `emitAtomicInline` (~531) | Full-width inline atomic loads/stores bypass the checked helper and omit natural alignment. | Keep Go atomic intrinsics, but obtain the pointer through checked `atomicEA`/`atomicEA64`. |
| `internal/codegen/helpers/helpers.go`: `atomicEA` (~1278), `simdEA` (~2605), `simd_v128_load_rng` / `_nc` (~2630) | Subword/RMW atomic and normal SIMD helpers already check effective address and width; atomics also check alignment. Coalesced SIMD loads check the covering range once. | Share the overflow-safe bounds predicate; retain atomic alignment, family trap paths and checked covering-range behavior. |
| `internal/ssa/pass/memaddr.go`: `FoldMemAddend` (~60); `internal/codegen/translate.go`: `compileBodyViaSSA` (~3392–3473) | Folding wrapping i32.add into a static offset relies on uint32 wrap. A new non-wrapping EA helper makes this transformation unsound. | Disable this fold in checked mode; keep i32 arithmetic separate. Conservatively disable nonshared memory forwarding in that mode too. |
| `internal/ssa/op.go`: `Value.HasSideEffect` (~442), `internal/ssa/pass/dce.go`, `internal/ssa/ssa.go` | An unused scalar load is removable, despite its required observable trap. | Mark scalar loads `MemoryMayTrap` before optimization; side-effect handling retains the access. |

The non-pure ARM64 SIMD splice has its own bounds preamble in
`internal/gcasm/simdsplice_mem_a64.go` (~140–187): zero-extension, 64-bit addition
and access-width checking before pointer access. Fused `simd_scalar_*` helpers
and non-pure code generation need their own audit. This campaign does not claim
coverage of every non-pure optimization or memory64, nor a full guest race census.

## Generic prototype

Six converter files changed: **79 added / 14 removed lines**, 8,060-byte patch.
An experiment-only `-checked-memory` option controls the checked scalar/inline
atomic lowering and conservative SSA behavior. There are no handwritten patches
to generated functions or special addresses.

The common predicate is:

```go
bound := m.memSize.Load()
return addr <= bound && offset <= bound-addr && size <= bound-addr-offset
```

Short-circuit subtraction avoids overflow. Only after success may `addr+offset`
be formed and applied to the stable base. Scalars use a common panic path
`wasm: memory access out of bounds`; SIMD and atomics retain their existing WASM
OOB/alignment panic paths. Atomic natural alignment remains a separate rule.
The host-survival harness recovers expected WASM panics; this does not add a new
product-wide trap recovery policy for every possible guest execution context.

## Before / after and compatibility

| Check | Released lowering | Checked prototype |
| --- | --- | --- |
| Reduced matrix vs Node WASM reference | 1,547 safely executed cases; **300 mismatches** (240 scalar, 60 atomic) | **1,960 cases, zero mismatches**, including 1,353 expected traps |
| Host survival | 413 unsafe cases deliberately skipped, not counted as passes | One generated-Go fixture process survives all expected traps, exit 0 |
| Wasmer native reference | Eight representative scalar/SIMD/atomic valid, OOB, overflow and unaligned cases | All eight agree with reference expectations |
| Actual generated guest | Known unsafe initial-boundary/static-offset lowering | Fn68 initial OOB and crossing, and Fn80 static-offset overflow recover as WASM traps; after grow the formerly OOB zero-range read succeeds |
| Focused runtime/base tests | Not redefined | `go test -race -p 1 -count=1 ./internal/generatedgo/code/base` passes, including thread/TLS/futex tests |
| Worker/shared memory | Retained architecture | Shared grow/base/atomic visibility and private TLS/stack globals pass using real generated Fn66/Fn68 |
| Product | Retained runtime/guest behavior | SQL create/insert/update/delete/select, two distinct held sessions, Snapshot and two sequential isolated Fork/use/Close cycles pass |

The baseline is the unchanged pinned release converter plus its existing release
patches. Unsafe cases outside its whole backing and some unaligned native atomic
cases were skipped to avoid crashing the host. Baseline SIMD was correct in the
tested forms; adding one scalar check would still leave inline atomic and SSA
semantic gaps. No new baseline host-signal result is claimed here.

An initial broader existing test invocation passed
`TestDefaultNoBundleAndForkIsolation`, then the resource guard stopped
`TestDefaultRepeatedConcurrentLifecycle`. That is **not an acceptance pass**.
Rather than raising the budget, the requested focused tests were run in separate
fresh processes and passed. Their elapsed test times are smoke durations, not
performance results.

## Budgets, cost and remaining work

Workspace guards: 16 GiB free-space floor and 4 GiB allocated-output budget per
workspace. Process guards: sampled descendant RSS 6 GiB / macOS physical memory
8 GiB, per-process CPU soft/hard limits 180/200 seconds, FD limit 256, no core
dumps, phase and outer timeouts. Initial workspace peak output was 1,463,873,536
bytes; minimum observed free space 61,606,916,096 bytes. The initial stop's memory
peak was not persisted by that harness version; console/test evidence preserves
the stop, and the saved harness now persists stop counters before raising.

Static Go compiler analysis found `memoryInBounds` inlineable (cost 29), but
`memoryEA` not inlineable (cost 100, budget 80). Therefore the current prototype
adds a helper call on scalar valid paths as well as logical-size checking.
Atomic inline paths add checked address/alignment helper work. Disabling
`FoldMemAddend` and conservative optimizer exclusions can increase code size,
compile cost or execution cost; that fold also addresses ARM64 large-immediate
literal-pool pressure. Full guest compilation succeeded here, but these risks
require assessment before integration. No throughput/latency claim was measured.

Recommended human decision: continue with bounded production-quality correctness
hardening for the released pure backend, **before** reconsidering mmap. Retain
fixture/reference cases; audit optimizer preservation of trapping operations and
atomic alignment across the supported lowering paths; replace conservative pass
exclusions only with proven-safe rules; then separately authorize a small cost
comparison. Memory64/non-pure support must be explicitly scoped or validated.
Do not merge the experiment wholesale or interpret this as mmap approval.

Compact evidence, checksums and unique prototype/harness source are preserved;
regenerated guest copies, converter/build binaries and owned temporary sources
are reproducible disposal targets. Existing caches and unrelated worktrees remain
untouched.
