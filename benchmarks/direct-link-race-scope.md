# Direct-link shared-memory race scope

**GENERAL SHARED-MEMORY MODEL WORK REQUIRED.** The observed conflicts are not
one futex-precheck idiom. There are useful local experiments, but no small sound
rule demonstrated to cover the full observed set. This is a scope conclusion,
not a proposal to make all linear-memory accesses atomic or replace direct-link.
Production, guest source, libc and generator behavior were **not changed**.
No canonical performance benchmark was run.

## Inputs and method

Investigation HEAD: `7220cdcb460ce66b1ca9d8e10813179a49bc205f`; runtime/generated
source is unchanged from `a427b83078071e4cee5d6aebe16d0ee55fb73041`.
macOS arm64 / Apple M1 / Go 1.26.8. Guest and source pins are the same as the
[origin investigation](direct-link-futex-race-origin.md), notably guest SHA-256
`5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`, converter
`ac98bcf00c17d8531f0c071a9836d0b50975e7ff`, WASIX libc `v2026-07-03.1`, and
lite4mariadb `24be9371a2f6c71250a2356631ad6feab2280b02`.

The [census script](spikes/direct-link/race_census.py) normalizes a report to an
unordered pair of R/W access frames, nearest generated guest call sites and
the actual `sync/atomic` operation. Addresses, goroutine numbers, stack depth
and report order do not split signatures. Atomic calls in optimized stacks
must be retained: some store reports name an outer caller, not the inner
allocator function. Treating such frames as ordinary writes overcounts that
category. A signature is an observed conflicting PC pair, **not a distinct bug**.

The compact [evidence](direct-link-race-scope.json) contains every signature,
both generated Go locations, generated expressions, WASM function identities,
opcode inventories, source evidence/confidence and per-log/phase occurrence
counts. Large raw logs remain disposable work output, identified by checksums.
Reduced tests are excluded from the full-guest signature count.

| Campaign | Reports | Unique signatures |
| --- | ---: | ---: |
| Historical default/concurrent lifecycle campaign | 4,443 | 142 |
| Three historical first-error confirmations | 3 | 1 each, already in the set |
| Fresh **one-DB** Start → SELECT 1 → Close | 927 | 76 |
| Union | **5,373** | **149** |

In the fresh one-DB test, phase markers attribute 491 reports / 39 signatures
to startup, 24 / 8 to ready/SQL, and 412 / 59 to Close. Phase signature sets
overlap. These are coarse logical phases, not timed causality traces. The
application reaches SQL and closes, but the test fails because races are
reported. **Do not call all 149 signatures startup-only or cross-instance races.**

## Concrete counts and confidence

| Count | Value / meaning |
| --- | --- |
| Access-pattern groups | **7**, below; not proof of exactly seven underlying semantic defects |
| Atomic vs ordinary signature pairs | **118** |
| Ordinary vs ordinary pairs | **29** |
| Wide SIMD vs wide SIMD pairs | **2** |
| Generated guest functions / corresponding WASM functions | **53 / 53**, access frames only, excluding deep callers |
| Guest PC/call-site locations | **139**; some are optimized call attribution, not direct memory instructions |
| Observed ordinary dereference sites | **81** |
| Ordinary sites observed conflicting with atomics | **50**, a subset of those 81 |
| Exact constant-base ordinary sites | **46**, resolving to **12** distinct guest global addresses |
| Exact constant-base mixed sites | **23**, resolving to **7** globals |
| Other ordinary/mixed sites | **35 / 27**, parameter/heap expressions, including constant field offsets |
| Structurally mapped WASIX function groups | **11**, representing **8** source primitive families |

Those fixed addresses are diagnostics for the checksummed artifact, not a
proposed address whitelist. Parameter/heap expressions may alias those globals
or each other; the count is not a disjoint runtime object census. No count of
all guest loads is used as an adapter-candidate estimate.

Ownership is deliberately non-exclusive:

- **79/149** have both nearest guest frames in structurally mapped WASIX groups.
- **111/149** involve at least one such WASIX group.
- **32/149** involve a generated function containing InnoDB source-file/assertion
  evidence; **3** overlap the preceding 111. This confirms compilation-unit
  provenance, not that every instruction in it originated in InnoDB rather than
  an inlined libc primitive.
- **9/149** have neither of those direct source anchors. Further inline-library
  attribution is possible. Complete alias/lock ownership is not established for
  all remaining scalar accesses.

For the earlier **bug-classification** vocabulary, use a stricter confidence
partition rather than treating every detected race as a proven guest defect:

| Classification | Confirmed signatures | Further assessment |
| --- | ---: | --- |
| TRANSLATOR LOWERING BUG | **1** | Subword atomic **load** becomes a writing, wider CAS. The reduced read/read and adjacent-byte tests prove this distinction. |
| WASM↔GO MEMORY-MODEL MISMATCH | **15** | Eight direct Fn88 precheck pairs plus seven direct Fn212 CAS-retry pairs have explicit source, WASM and reduced-contract evidence. |
| GUEST DATA RACE | **0** | No original guest synchronization violation is proved by these Go reports. |
| TOOLCHAIN LOWERING BUG | **0** | No demonstrated lost source atomic operation. |
| Source-contract classification not completed | **133** | Includes **96** additional WASIX-associated signatures likely requiring adapter/lifecycle work, and **37** other scalar/vector/source-unresolved signatures. Do not automatically label these harmless, guest bugs, or translator defects. |

The first two confirmed buckets total 16; the 133 pending signatures include
the tentative assessments, not extra reports. The seven access-pattern counts
remain useful even where source guard/alias correctness is not yet settled.
This per-signature uncertainty does not prevent the scope conclusion: already
proven patterns differ in access kind, width and mutation, so one precheck rule
is not a complete solution.

### Source mapping correction

The previous report's claim that the guest had no debug sections was incorrect.
It has `.debug_info`, `.debug_line`, `.debug_loc`, `.debug_ranges`, `.debug_str`
and `.debug_abbrev`, but no `name` section. Reading them with pyelftools 0.32
found **6,289** subprogram/inlined ranges with low/high both zero: no usable PC
mapping. This does not recover MariaDB instruction source lines. Structural
matching, the prior unchanged-source IR probes and embedded assertion strings
are the mapping evidence used here. No repaired/guessed DWARF mapping is claimed.

## Categories and source/WASM/Go mapping

These are diagnostic classifications of observed expressions/control flow.
Function numbers identify evidence only; they are never runtime matching rules.

| Group | Signatures | Representative mapping and confidence |
| --- | ---: | --- |
| Wait precheck / join polling | **23** | Fn88 normal `i32.load` → `p7_pure.go:356` before import 42; Fn94 `__wait`; Fn221 and likely inlined join paths. Imported wait rechecks atomically. Source family mapping strong for low-index primitives; inline callers less certain. |
| CAS retry / waiter counters | **21** | Fn212: `i32.load` → `p8_pure.go:4451`, `i32.atomic.rmw.cmpxchg` → `:4466`; matches `pthread_rwlock_tryrdlock`. Fn218/Fn93 counter loads preceding CAS are also observed. |
| Lock polling / wake hints | **46** | Fn93: mutex word / waiter-count loads, e.g. `p6_pure.go:1357/1385/1393`; Fn130 `:2699` and allocator Fn152/Fn153 polls. Competing CAS, exchange or atomic store. Includes a likely inlined rwlock poll. |
| Thread lifecycle / registry | **22** | Fn216 thread-list links, lock/count globals and detach-state stores; AtomicWait comparison vs ordinary release store; Fn216 writes vs Fn216 writes. Source maps to `pthread_create.c` thread-start/exit/list management. Not all ownership invariants proved. |
| Other scalar shared state | **34** | Ordinary i32/i64 fields/globals and some inlined synchronization whose identity is unresolved. Fn18240 LRU heuristics reads vs Fn18239/18242 state updates; Fn18097/Fn16719 counters; buffer-flush and purge state. **Not 34 confirmed independent InnoDB bugs.** |
| Wide-memory overlap | **2** | `v128.load` / `v128.store`, Fn18278 ↔ Fn17299, lowered via `Simd_v128_load` / fused store helper. Reads/writes span 16 bytes. InnoDB purge-file source evidence on Fn17299; exact shared-object/lock ownership not recovered. |
| Subword atomic-load widening | **1** | Fn18300 ordinary `i32.load8_u` ↔ Fn18328 `i32.atomic.load8_u` (`fe12`). Generated `AtomicLoad32_8u` calls `AtomicSubword32`, performing a **32-bit identity CAS**, i.e. a physical write for a guest read. Source-file evidence: `os0file.cc` on the ordinary reader. |

The WASM decoder parsed all 53 observed functions with the pinned parser. The
JSON records ordinary memory and atomic/SIMD prefixed opcode counts (including
non-memory SIMD), plus representative exact body offsets/bytes; these are not claimed to identify every Go PC's unique WASM instruction offset.
Ordinary typed Go dereferences map through `emitMemLoadExpr`/store emission to
the corresponding ordinary opcode. Explicit helper names map to their atomic
opcode; optimized outer call frames retain an unresolved inner instruction PC.

Examples validating the distinctions:

- Fn88 has two `i32.load`s and **no** atomic wait instruction; its wait is a WASIX
  import. Fn212 has one `i32.load` and one `fe48` CAS.
- Fn93 has ordinary loads and CAS; Fn130 has ordinary loads, stores and CAS.
  Fn152/Fn153 contain ordinary polls, `fe41` atomic exchanges and `fe17` stores.
- Fn216 has **17 ordinary `i32.store`s** and a separate `fe17` atomic store:
  treating every lifecycle store as one atomic operation would be incorrect.
- Fn18239 has ordinary loads/stores without an atomic opcode in its own body.
  Fn18240 has plain field/global reads alongside atomic `access_time` operations.
  A call to another function is not a proof that every preceding plain read has
  an atomic validation boundary.
- The subword helper changes physical access **kind and width**. This is
  independently reproduced as read/read and different-byte cases; it is not
  evidence that the guest deliberately writes when performing an atomic load.

## Are these all optimistic prechecks?

**No.** Five synchronization/lowering idioms have reduced tests with a clear
contract: expected-value precheck, CAS retry, mutex polling/hints, ordinary
release vs atomic wait comparison, and subword lowering. Two additional
observable payload groups (scalar state and wide copying) still require more
source ownership analysis; there may be further subpatterns inside them.

| Primitive/pattern | Effect of stale ordinary read | Correctness boundary / promotion assessment |
| --- | --- | --- |
| Futex expected-value precheck | May take mismatch/retry instead of entering the import; may enter the import with an outdated value. The import must reject a changed current value before parking. | The unchanged `AtomicWait32At` compare/register protocol is the blocking boundary. Atomic precheck can strengthen ordering for aligned words; it does not replace that protocol. The post-timeout value read is a result check, not just an optimistic precheck. |
| `__wait` / join polling | May spin longer, proceed to an atomic wait, or exit a polling loop when state is observed changed. | Atomic wait validates sleeping; final lifecycle visibility/ownership must also hold. Atomicizing one read cannot synchronize a competing ordinary store. |
| CAS retry / rwlock try-read | An outdated expected value makes CAS fail and retry; state is acquired/incremented at successful CAS. Early EBUSY/EAGAIN branches can observe a stale state. | CAS is the linearization boundary for successful acquisition. SC load promotion for an aligned word narrows allowed observations; alias coverage and early-return behavior still need proof. |
| Mutex spin / waiter hints | Lock-state polling controls spinning vs attempting acquisition. Waiter-count hints control whether/when to wake, not ownership acquisition. | Acquisition depends on CAS. Wake-hint and `libc.need_locks` reads are not all interchangeable optimistic CAS operands: the latter can gate locking itself. Source lifecycle invariants matter. No sticky wake, shortened timeout or forced ordering is justified. |
| Thread release/list management | Plain writes to synchronization state and linked-object metadata are the mutation itself. | No later atomic precheck makes a racing write harmless. Need release/acquire and object-lifetime contracts, not merely a precheck-load rule. |
| LRU heuristics/statistics/fields | Can affect eviction heuristics/statistics; normal list/counter fields can also be protected data. | `buf0buf.inl` reads `freed_page_clock`/`old` and may increment statistics; no futex/CAS validates those values. `buf0lru.cc` mutates these fields. Full alias/guard attribution remains incomplete. Do not infer transaction safety or prescribe atomic increments from the race report alone. |
| Subword atomic load | Guest operation is only a byte read, but the Go helper writes the containing word. | Guest atomic-load semantics are the boundary. Identity CAS introduces writes and overlap with adjacent bytes; not an optimistic-read idiom. |

An SC atomic load on an aligned full-width word can be a refinement of WASM's
permitted shared-memory observations, but **not an unconditional rewrite of any
ordinary load**: ordinary WASM loads can be unaligned; Go atomics have alignment
requirements, access widths matter, aliases/overlaps must agree, and changing a
sequence into atomic RMW can change lost-update behavior. Promotion is not a
proof that the original Go race is harmless. Relevant contracts:
[WASM threads memory model](https://webassembly.github.io/threads/core/exec/relaxed.html),
[atomic wait semantics](https://github.com/WebAssembly/threads/blob/main/proposals/threads/Overview.md),
[Go memory model](https://go.dev/ref/mem).

## Adapter candidates (not implemented)

| Strategy | Soundness / false promotion / semantic risk | Complexity and maintenance | Independent testing / coverage |
| --- | --- | --- | --- |
| A. Source primitive aware | Strongest route if build preserves semantic identities for each synchronization word, width, alignment and all reads/writes. Recognizing an entire function does not cover inlined primitives or payload aliases. Must not turn thread/list ownership errors into apparently synchronized code. | Medium/high: build-to-translator metadata or stable intrinsic boundaries; high sensitivity to WASIX ABI/inlining. No function-number or field-address table accepted. | Test mutex/condvar/rwlock/lifecycle reductions. **111/149 is an involvement ceiling, not proven adapter coverage**; some opposite sides are unresolved. |
| B. Import/operation boundary aware | Import alone is too late for preceding loads. A backwards SSA rule needs same-word proof, alignment and control-flow constraints; also cover result rechecks. Promoting unrelated nearby loads is unsound. | Low/medium for a proven local load→CAS/expected-wait pattern; high when aliases, loops, after-call loads and inlined pthread code enter. Moderate version sensitivity if semantic SSA rules replace names. | Candidate pair coverage **38/149 (25.5%)** where classified optimistic/CAS reads oppose actual atomics. Conditional on proving every alias/alignment; **no implemented coverage**. It misses ordinary writer, hint, payload and widened-load cases. |
| C. Static shared-word classification | Find words participating in atomic operations and route **all conflicting accesses** through an abstraction. Needs access-size/range analysis, dynamic allocation aliases, initialization/lifetime phases. Ordinary-only LRU/statistic words are not discoverable from atomics alone. False promotion can add alignment traps or turn partial-word operations into destructive whole-word changes. | High: interprocedural alias/range analysis plus an explicit policy for unknown addresses. A fallback treating all memory as candidate is prohibited. Less symbol/version dependent, but not a small existing emitter rule. | Pointer aliases, overlaps, unaligned accesses, lifecycle and scalar/vector fixtures. At most **118/149** observed atomic/ordinary pairs are an initial target, not a proved fix; 29 ordinary/ordinary and 2 wide pairs remain. |
| D. No one bounded rule for the set | This is the present scope result, not proof that no finite future design exists. A word-only optimistic-load rule cannot cover ordinary writes, payload-only words and read→CAS widening. | A broader contract separating synchronization words, payload sharing and byte/range operations is needed unless remaining ownership analysis removes categories. | The independent reductions prevent a precheck-only fix being mistaken for full acceptance. |

Even the 38-pair candidate is a **diagnostic potential** count, not verified
race-clean whole-guest coverage. Other signatures can disappear after a correct
release/acquire fix, but that transitive effect has not been demonstrated or
included in the fraction. Conversely, runtime workloads can expose new sites.

## Reduced reproducer inventory

The [preparer](spikes/direct-link/prepare_race_patterns.py) makes a fresh disposable
module, pins/verifies the converter archive and lowering/helper source, builds a
small shared-memory WASM fixture, and invokes the actual pure-Go converter.
Templates are `.go.txt`, outside normal package discovery. No generated output
is manually edited. Tests use actual canonical Fn88/Fn93/Fn130/Fn212 and helpers
where practical; the fixture uses the same ordinary/SIMD lowering for other
instruction shapes. Synthetic payload tests demonstrate the instruction pattern,
**not the original object's lock ownership**.

| Test | Pattern | Ordinary test | Separate `-race` test |
| --- | --- | --- | --- |
| Existing `TestGeneratedFutexPrecheckRace` | Canonical Fn88 vs canonical CAS | PASS | FAIL, expected conflict |
| `TestCASRetryRace` | Two canonical Fn212 read-lock acquisitions; successful CAS count 2,000 | PASS | FAIL |
| `TestMutexPollRace` | Canonical Fn93/Fn130, two private stacks/TLS contexts, unchanged wait/notify helpers, protected counter | PASS, correct count | FAIL at lock poll vs unlock CAS |
| `TestReleaseStoreWaitRace` | Generated ordinary i32 store vs canonical atomic wait comparison; mismatch path only | PASS | FAIL |
| `TestScalarCounterRace` | Generated ordinary i32 read/add/store | PASS | FAIL |
| `TestSIMDRangeRace` | Generated v128 read/store helpers | PASS | FAIL |
| `TestAtomicByteReadRace` | Generated ordinary byte read vs canonical atomic byte-load helper: **two guest reads** | PASS, byte unchanged | FAIL: helper CAS writes |
| `TestAtomicNeighborByteRace` | Generated ordinary store at byte 65 vs atomic load at byte 66 | PASS, target byte unchanged | FAIL: widened CAS overlaps adjacent byte |

The final two are one width/kind pattern with two essential subcases, not two
claimed guest bugs. All eight diagnostics passed normally and independently
reported their intended race. Two fresh generations produced identical WASM
SHA-256 `e1970f9980dac7cd71c9775514b7993a07a8878f3cb15e6525ae2a6d4ed82f6d`
and identical 20 generated files; the replay's ordinary tests also pass.
Existing canonical generated base/adapter race tests and provenance checks pass.
Full-guest race gate still fails. No after-fix result is claimed.

## Smallest next experiment and decision

First isolate **atomic subword load must not perform identity CAS** in a disposable
generator/runtime patch. Replace the load-only helper's CAS with a read-only
atomic extraction where semantically valid; verify both read/read and adjacent
byte regressions, bounds/alignment and stores/RMW independently. This is a small
helper-contract experiment, not the proposed solution to all 149 signatures:
it directly targets **one observed signature (0.7%)**. Read-only extraction still
reads a wider word, so adjacent-byte writes may remain a distinct width problem.

Separately, the smallest SSA adapter prototype would require proven aligned,
same-word ordinary reads feeding a CAS or expected-value wait path, preserving
the wait/CAS boundary. Use the 38-pair candidate set as a scoped target, **not a
function whitelist**. Do not begin full integration on a successful subset.

The decisive nonlocal signals are ordinary-only InnoDB fields, dynamic/overlapping
word accesses, lifecycle writes and subword/wide physical accesses. Correctness
needs a shared-memory contract beyond one optimistic-load emitter change. This
task does not implement that contract, change source synchronization, suppress
instrumentation, switch execution architecture or benchmark.

**Final verdict: GENERAL SHARED-MEMORY MODEL WORK REQUIRED.**

## v0.4 scope decision

The full generated guest is currently not Go race-detector clean. This was
investigated, not suppressed: 5,373 reports, 149 distinct conflict signatures,
seven broad access-pattern groups, and no small sound adapter rule demonstrated
for the whole set. The verdict remains **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**.
These are not 149 independent bugs, and the observed races are not called harmless.

For v0.4 this is a known limitation, not a requirement that the full generated
guest `-race` integration pass as a release gate. Do not suppress `-race`, add
`//go:norace`, patch generated addresses/function indexes, make all accesses
atomic, redesign the shared-memory adapter, or switch to subprocess execution
because of this finding. Keep the reduced reproducers and investigation evidence.
Focused handwritten/runtime FD, filesystem, thread, TLS and futex race tests
remain enabled and must pass. Re-evaluate broader shared-memory adaptation after
the planned v0.5 MariaDB/WASIX/toolchain update.

This scope decision permits the normal functional acceptance and canonical
v0.4 direct-link performance baseline; it does not establish race correctness.
