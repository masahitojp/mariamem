# Direct-link futex precheck race: origin and decision boundary

**MEMORY-MODEL ADAPTER WORK REQUIRED**. Classification:
**WASM↔GO MEMORY-MODEL MISMATCH**, for the single conflict traced here.
No production/generator/generated-source change was made. No canonical benchmark
was run. Other full-guest reports remain unclassified.

## Inputs and reproducibility

- Investigation source: `a427b83078071e4cee5d6aebe16d0ee55fb73041`, branch
  `v0.4/generated-go-integration`.
- macOS arm64, Apple M1 / 16 GiB; Go 1.26.8.
- Canonical legacy-EH guest SHA-256:
  `5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`.
- Pinned wasm2go fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`.
- Generated provenance SHA-256:
  `99092e99f196253f7b0f0c18a5ef9b90734a670e8ae1676161c38953fed9af7e`.
- WASIX libc `v2026-07-03.1`, source archive SHA-256:
  `55091ce6af5b549b3c97f61592bd2506e6a7e5da3588cb2f77a64388468ad231`.
- Source-to-IR probe: pinned build image
  `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`,
  LLVM 23.1.0 commit `ea7d852a70e8bdfaf601d6626a760f9771b2c4b4`;
  `WASIXCC_WASM_EXCEPTIONS=legacy`, `WASIXCC_RUN_WASM_OPT=no`.

The archived libc was checksum-verified before extraction. The final guest has
no retained name/debug section: C function correspondence below is a structural
match of signatures, branches, error constants, imports and synchronization
layout, not recovered DWARF. The fresh IR probe verifies the pinned source's
lowering; it is not presented as the original full-build IR.

## One stable full-guest report

Command, with no NativeDir/runtime override:

```sh
GOTOOLCHAIN=go1.26.8 MARIAMEM_TEST_DEFAULT=1 GORACE=halt_on_error=1 \
  go test -tags integration -race -count=1 \
  -run '^TestPublicLifecycle$' ./tests/gointegration
```

The single-DB startup fails with the following first conflict:

| Agent | Generated operation | Go location | Address |
| --- | --- | --- | --- |
| Main agent, goroutine 15 | expected-value precheck, normal `int32` load | `code/p7/p7_pure.go:356`, `p7.Fn88` | `0xc000b7c584` |
| Spawned worker, goroutine 27 | barrier CAS, old value → 0 | `code/p6/p6_pure.go:9035`, `p6.Fn219` → `base.AtomicRmwCmpxchg32`, `base.go:1836` | `0xc000b7c584` |

Read chain: `Fn88 ← Fn218 ← Fn18103 ← Fn18115 ← Fn18114`, during startup.
CAS chain: `Fn219 ← Fn18108 ← Fn18113 ← Fn216 ← ThreadSpawn ← ThreadLaunch`.
The report does not include the full guest's memory-base pointer; its **linear
offset is not recovered**. The exact offset is independently known in the
reduced test below. Worker module copies deliberately share their owning DB's
linear memory. This is not accidental sharing between DB instances.

The source operation sequence is a condvar waiter reading its barrier value
while the signaling agent atomically clears that same barrier. The race detector
records unordered overlapping accesses; it does not establish an exact wall-clock
interleaving. No additional startup tracing/ordering changes were used.

## Exact guest instructions and translation

The isolated [decoder](spikes/direct-link/race-instructions.go.txt) uses the
pinned converter's parser, including its immediate decoder. There are 65 imported
functions (66 imports including memory); function import **42** is
`wasix_32v1.futex_wait`. Offsets below are from the start of each function body,
**including its locals declaration vector**, not whole-file offsets.

| Function / body offset | Bytes | Instruction / purpose |
| --- | --- | --- |
| Fn88, `0x004d` | `20 00` | `local.get 0`, futex address |
| Fn88, `0x004f` | `28 02 00` | **ordinary `i32.load`**, alignment exponent 2, offset 0 |
| Fn88, `0x0052` | `47` | `i32.ne`, compare with expected argument |
| Fn88, `0x0064` | `10 2a` | call imported futex wait |
| Fn88, `0x0078` | `28 02 00` | second ordinary load, timeout/result check |
| Fn219, `0x0143` | `28 02 00` | ordinary old-value read in barrier exchange loop |
| Fn219, `0x014e` | `fe 48 02 00` | **`i32.atomic.rmw.cmpxchg`**, alignment exponent 2, offset 0 |

Fn88's body is 152 bytes, signature `(i32, i32, i64) → i32`; Fn219's is
366 bytes, signature `(i32, i32) → i32`. Fn88 has neither atomic load nor
`memory.atomic.wait32`. The CAS uses a computed waiter address +12 (barrier
field for the wasm32 waiter layout), compares the previously read value and
replaces it with zero; it retries on mismatch.

The converter's `internal/lower/lower.go` maps `OpI32Load` to `OpLoad32`.
`internal/codegen/emit_memops.go:66–84` emits an ordinary typed-pointer
dereference for that operation even for shared memory. Explicit atomic load,
wait and CAS opcodes have separate atomic lowering. Thus wasm2go did **not**
misdecode an atomic wait/load into this ordinary precheck.

## Pinned source synchronization primitive

The reader structurally matches WASIX libc
[`__wasilibc_futex_wait_wasix`](https://github.com/wasix-org/wasix-libc/blob/v2026-07-03.1/libc-bottom-half/sources/__wasilibc_futex.c):
aligned-address validation; volatile expected-value precheck; imported WASIX
futex wait; volatile value recheck if not woken. The builtin atomic-wait call in
that source is commented out. The extra `op` parameter is unused and eliminated.

The main-agent chain matches `pthread_cond_timedwait → __timedwait_cp →
__wasilibc_futex_wait_wasix`. In musl's
[`pthread_cond_timedwait.c`](https://github.com/wasix-org/wasix-libc/blob/v2026-07-03.1/libc-top-half/musl/src/thread/pthread_cond_timedwait.c),
a private waiter has a `barrier` initially set to 2. Its address is passed to
the timed wait. `__private_cond_signal` detaches/signals the waiter list and
unlocks the first waiter's barrier using `a_swap(..., 0)`; previous value 2
causes a wake. That function's control flow and field accesses match Fn219.
The wasm32 `a_cas` macro in `arch/wasm32/atomic_arch.h` uses
`__sync_val_compare_and_swap`; the generic exchange uses a CAS retry loop.

Two small compiler probes used `wasixcc -O2 -matomics -mbulk-memory -pthread
-S -emit-llvm` with the pinned legacy-EH setup:

1. Compile the **unchanged extracted futex source**. IR contains
   `load volatile i32` before the import and again on the timeout branch;
   neither is an LLVM atomic load.
2. Compile a wrapper calling the **unchanged extracted wasm32 `a_cas` macro**.
   IR contains `cmpxchg ... seq_cst seq_cst, align 4`.

These converge with the exact final WASM: the ordinary read originates in the
libc source, the atomic CAS remains atomic through LLVM/WASM/Go. No evidence
supports a toolchain dropping an originally atomic read.

## Contract and classification

This target libc intentionally polls a synchronization word with a volatile
ordinary load. The precheck is advisory: correctness of sleeping depends on the
import rechecking the value while registering the waiter. WASM shared-memory
execution constrains even unordered ordinary reads, including aligned reads
against same-width writes; it does not make every such trace undefined as
portable C11 would. See the [threads memory-model draft](https://webassembly.github.io/threads/core/exec/relaxed.html).
This is **not** a claim that C `volatile` is a portable atomic operation or that
all MariaDB accesses have been proven safe.

Go's ordinary unsafe read concurrently with a CAS has no happens-before edge
and is a genuine Go data race. The [Go memory model](https://go.dev/ref/mem)
requires synchronization for concurrently modified data; hardware coherence
alone does not supply it. Therefore the faithful opcode-by-opcode translation
fails to provide an appropriate **Go memory-model adapter** for this target
libc synchronization idiom. The detector report is not dismissed as false positive.

The actual wait helper is already atomic: `main.go`'s WASIX import adapter calls
`base.AtomicWait32At`; `base.go:1887` uses `atomic.LoadUint32` under the parking
lock, with comparison/registration serialized against notify. This agrees with
the [atomic wait contract](https://github.com/WebAssembly/threads/blob/main/proposals/threads/Overview.md).
Changing that helper cannot synchronize the earlier Fn88 read.

## Minimal reproducer and validation

The [existing reproducer](spikes/direct-link/futex-precheck-race.go.txt) imports
canonical generated Fn88 and the actual CAS helper. It allocates **one** 64 KiB
module, with target linear offset **64 (`0x40`)**. A second agent CASes 0→2→0;
Fn88 expects 1, hence always returns mismatch (-6) before calling any host import.
No MariaDB/SQL/FD/server/instance adapter is involved. A shared launch gate and
final join do not synchronize accesses inside the two loops. No sleeps are used.

| Check | Result |
| --- | --- |
| Reduction, ordinary `go test -count=1` | PASS |
| Reduction, `-race`, first independent run | FAIL: goroutines 8/9, base `0xc000180000`, target `0xc000180040` |
| Reduction, `-race`, second independent run | FAIL: goroutines 8/9, base `0xc0001c6000`, target `0xc0001c6040` |
| Single full-guest `TestPublicLifecycle -race` | FAIL: same Fn88/Fn219 conflict above |
| `go test -race -count=1 ./internal/generatedgo/code/base ./internal/generatedgo` | PASS (2.379 / 1.288 s): existing filesystem, TLS/thread/futex and adapter reductions |
| `python3 scripts/verify_generated_runtime.py` | PASS: canonical inventory and guest/image bindings unchanged |

Initial full-guest invocation omitted the integration build tag and did not run
tests; only the corrected command above is counted. No fix was applied, so an
after-fix reduction/full-guest result does not exist. Prior ordinary SQL,
Snapshot/Fork, SQLAlchemy44/GORM32 acceptance remains historical evidence; this
investigation does not claim a new successful full-guest race gate.

## Smallest fix boundary / stop decision

An atomic load is the natural **operation-level** replacement for this aligned
futex-word precheck, retaining the imported wait protocol and timeout/wake
behavior. But it is not an established **generic generator fix**:

- The precheck is an ordinary WASM opcode, without a futex annotation; the final
  guest has no source names. Editing Fn88 or matching its index/address would be
  artifact-specific, not a maintainable lowering rule.
- The same barrier exchange loop already contains a second ordinary load
  (Fn219 `0x0143`). Patching only a wait helper/precheck cannot make the traced
  synchronization object race-clean.
- A generic adapter must identify **all conflicting accesses to synchronization
  words**, preserve alignment/access-width semantics and deal with aliases;
  proof for this primitive would not classify all remaining guest reports.

No blanket atomicization, suppression, address/function patch, guest source
change or memory representation redesign was attempted. A bounded generic
recognition/adapter strategy has **not yet been demonstrated**. Work stops here
at the user's memory-model/translator scope gate. The next decision is whether
to authorize a separately bounded shared-memory adapter investigation; benchmark
and release acceptance remain blocked until the full guest is race-clean.

**Final verdict: MEMORY-MODEL ADAPTER WORK REQUIRED.**
