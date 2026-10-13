# v0.5.0 bounded correctness fixes and shared-memory feasibility

**Three requested fixes: COMPLETE within the supported private-DB/WASI runtime
boundary. General shared-memory correctness: NOT ESTABLISHED.** Stop here for
Human review. This is not v0.5.0 RELEASE READY; final Qualification, Product
Validation, publication and integration into main have not been performed.

The following guarantees are deliberately separate: logical file allocation,
exact-width load implementation, tested concurrent patterns, and general
shared-memory translation soundness. Native logical growth coordinates the
WASI operations in this process; it does not protect against arbitrary external
writers or promise physical storage reservation. That limitation is explicit,
not a claim that process-local locking implements a universal native fallocate.

## Starting evidence and source identity

A–D baseline: `808df8b614906a9cd918229e2754d33a5a76dc4b`.
Judgment/fixture baseline: `f14764cee0aa90dadf9c624cfeaf59c04b6c740f`,
[prior judgment](v050-correctness-judgment.md). Before implementation all saved
oracle/evidence hashes were verified. The original 26-case diagnostic fixture
was rerun: 18 PASS, 8 FAIL, with the same allocation/bulk/subword findings and
heap/mmap visibility difference. [Before results](v050-correctness-fixes-evidence/before-results.json)
and preserved failure logs are in the evidence directory.

Work is on `experiment/v050-correctness-fixes`, starting from the judgment commit.
Main remains `098b0144ed50835da792ba811d11e0a1c8b000b2`. Independent review units:

| Change | Initial owner/test commit | Follow-up |
| --- | --- | --- |
| fd_allocate | `f8f9036` | `d797303`, `f645085`, `a4bf7af`: formatting, emitter retention and explicit zero-length policy |
| zero-length bulk | `46fed58` | Canonical regeneration, template binding and negative ownership checks |
| exact-width loads | `4c07801` | `8fb7895`, `a4bf7af`: readonly mapping, publication and last-halfword regressions |
| bounded feasibility/owner templates | `28ef1ca` | Small real-opcode fixture; source templates excluded from package discovery |
| canonical source | `ae80130b0ea7d20e86b132538d23eabf13660186` | Actual clean-source native host identity; later tooling/evidence commits do not relabel it |

[Fixed input identities](v050-correctness-fixes-evidence/fixed-input-identity.json)
record byte hashes, patch order, generated delta and actual host/recipe origins.
The [A–D report](v050-ad-integration.md) owns MariaDB source/recipe/toolchain
acquisition; they remain unchanged here. No converter/dependency version bump,
new guest series, API, platform or Go minimum change is included.

## Implementation and boundaries

### Logical allocation

[fd-allocate-preservation.patch](../../benchmarks/spikes/wasm2go/fd-allocate-preservation.patch)
changes the pinned converter's WASI source, not emitted Go by hand.
Unsigned start/count are checked before addition against the File interface's
signed representable end; overflow/unrepresentable ranges return EFBIG without
mutation. An empty allocation is a validated no-op, including an offset beyond
current EOF: valid/writable FD checks still run, but size/content/position remain.

MemFS records the access mode at normal and directory-relative opening. Its
Allocate capability checks write access and grows only while holding the same
node/filesystem lock used by WriteAt and Truncate. The existing resize helper
preserves original bytes and zero extension. All handles to that node share the
lock; no Stat→unconditional-Truncate race exists. A smaller legitimate concurrent
truncate may itself discard data; the allocator never adds a subsequent shrink.

Native raw os.File fallback uses a process-wide native size lock shared by WASI
write, pwrite, set-size and native truncate-open (both write layouts are wired to
the guard). Separate WASI instances/FD aliases therefore coordinate. Under that
lock it validates access by a zero-byte write, stats, and truncates **only to grow**.
This is logical-size compatibility for native WASI operations, not disk block
reservation. MemFS materializes a Go byte allocation; native Truncate can be
sparse. No ENOSPC-prevention/durability guarantee is inferred from success.
An unknown File implementation must provide the grow-only Allocate capability;
otherwise ENOTSUP is returned instead of silently invoking destructive Truncate.

**Native coordination scope:** arbitrary host code calling raw os.File methods,
other processes, or filesystem operations bypassing the WASI shim do not acquire
this lock. They are not covered by its growth guarantee. The supported product's
mutable database backing is private MemFS; no native mutable database filesystem
option was added. If a broader concurrently mutable native backend is required,
use a kernel grow-only allocation primitive or an ownership-enforced backend;
a Stat/Truncate shim cannot be advertised as that stronger contract.

[FD tests](../../scripts/runtime_correctness/fd_allocate_test.go.txt) cover inside,
growth, zero/beyond-EOF, unsigned wrap/signed limit, contents/position, readonly
and invalid FDs, and two concurrent handles/independent WASI instances performing
size changes/pwrite/allocation. Tests run on MemFS and native macOS files.

### Bulk zero-length boundaries

[zero-bulk-bounds.patch](../../benchmarks/spikes/wasm2go/zero-bulk-bounds.patch)
moves zero-length return after unsigned nonwrapping logical/source bounds checks
in memory.fill, memory.copy and memory.init. Dropped segments have an empty
source range; `(src=0,n=0)` is permitted, while an out-of-range source still traps.
The canonical profile is memory32; this is not a new memory64 support claim.

[Bulk tests](../../scripts/runtime_correctness/bulk_bounds_test.go.txt) distinguish
exact-end from past-end, unsigned addresses/lengths, positive valid effects,
positive invalid ranges, dropped empties and attempted reads from a dropped
segment. Empty/trapping operations must leave all bytes unchanged. The original
zero-length failure oracle now passes without rewriting it.

### Exact-width atomic loads

A standalone [candidate](../../benchmarks/spikes/v050-narrow-atomic/) was tested
before installing the method. Ordinary values, independent adjacent-byte writes
and publication passed on arm64. Its plain-Go publication observer under -race
reported a conflict because assembly synchronization is not recognized; that
failure is preserved and not interpreted as successful detector coverage.

The production [adapter](../../scripts/runtime_atomic_loads.py) changes exactly
the two checked memory32 load helpers during deterministic installation, rejecting
changed/duplicate/missing converter shapes. It uses handwritten primitives owned
by [source templates](../../scripts/runtime_correctness/); emitted canonical Go
bodies were never manually edited. The generic converter stays portable and
unchanged in its pin; the supported native specialization belongs to mariamem's
installer. All stores/RMW/cmpxchg retain their existing lowering.

| Target | Effective load instructions | Ordering |
| --- | --- | --- |
| macOS arm64 | LDARB / LDARH, returning uint32 | DMB ISH before and after |
| Ubuntu x86_64 | MOVBLZX / MOVWLZX, returning uint32 | MFENCE before and after |

A requested byte/halfword is read directly. There is no identity CAS, whole-word
masked read, or plain compiler byte load substituted for the atomic operation.
Natural alignment, unsigned effective address bounds and zero extension remain
at AtomicEA/the wrapper. Full fences are deliberately conservative: their cost
is unmeasured and belongs to later Product Validation. The caller uses a normal
opaque assembly call; no pure/readonly annotation permits compiler reordering
across it. No go:norace or suppression was added.

The ordering rationale uses the [Arm barrier definition](https://support.arm.com/documentation/102336/0100/Limiting-the-scope-of-memory-barriers?lang=en),
[Arm's SC mapping discussion](https://developer.arm.com/community/arm-community-blogs/b/tools-software-ides-blog/posts/armv8-sequential-consistency),
and [Intel's MFENCE instruction specification](https://www.intel.com/content/dam/www/public/us/en/documents/manuals/64-ia-32-architectures-software-developer-vol-2b-manual.pdf).
[arm64 machine code](v050-correctness-fixes-evidence/narrow-arm64-disassembly.txt)
and [cross-compiled amd64 machine code](v050-correctness-fixes-evidence/narrow-amd64-disassembly.txt)
confirm the operand widths and fences. Stack argument/result traffic is separate
from the guest-memory read. Machine operand width is not a cache-line/bus-transfer
measurement. The unsupported-platform source fails explicitly; supported scope
remains the original two targets.

[Native tests](../../scripts/runtime_correctness/narrow_load_test.go.txt) cover
all byte lanes and naturally aligned halfword lanes, high-bit zero extension,
last valid byte/halfword, out-of-range/wrapping addresses, misalignment, read-only
mmap (including contended mode), and publication using atomic payload controls.
The readonly page would reject a guest-memory write; the primitive succeeds.

**Detector scope:** assembly loads are not instrumented by Go's detector even
on heap backing. A missing report cannot certify an overlapping atomic/ordinary
access. The earlier ordinary-payload publication diagnostic exposes missing
instrumented synchronization as well. These are additional observation limits,
not reasons to omit tests or infer synchronization from silence.

## Bounded feasibility results

[Runner and matrix](../../benchmarks/spikes/v050-shared-feasibility/)
generate a small real WASM fixture containing load/store/add/cmpxchg opcodes at
both widths using the canonical patched converter. NOP padding selects its
ordinary multi-package helper path; no address/function whitelist or fake
production patch is used. The same production exact-load adapter and memory
mapping owner are then applied deterministically. Input Wasm and converter hashes
are recorded in [study results](v050-correctness-fixes-evidence/shared-study-results.json).

80 commands cover two widths, heap/mmap, ordinary neighbor/target overlaps,
load/store/RMW/cmpxchg, an instrumented ordinary-read control and SC store-buffering.
Value outcomes, effective operand spans and detector reports are recorded separately.
The span metadata describes the inspected lowering, not a dynamic bus trace.
All normal commands passed. All eight store-buffering commands passed (1,000
trials each); publication also passed. These are finite litmus/functional checks,
not an exhaustive memory-model proof.

| Pattern | Effective target access | Heap -race | mmap -race | Meaning |
| --- | --- | --- | --- | --- |
| Exact load vs adjacent-byte write | 1 / 2 bytes | No report | No report | Disjoint operand ranges plus ISA/readonly proof; detector cannot observe ASM load |
| Exact load vs ordinary target write | 1 / 2 bytes | No report | No report | ASM/mmap observation gaps; do not call this safe mixed access |
| Store vs neighbor or ordinary target read | Existing 4-byte masked access | Reports at both widths | No reports | Store footprint remains widened |
| Add/RMW vs neighbor or ordinary target read | Existing 4-byte CAS | Reports at both widths | No reports | RMW footprint/ordinary overlap remain unresolved |
| Cmpxchg vs neighbor or ordinary target read | Existing 4-byte CAS | Reports at both widths | No reports | Same residual width/overlap issue; no complete cmpxchg repair claimed |
| Ordinary read/write control at target | 1 byte | Reports | No reports | Demonstrates backing-specific detector visibility |

There are 14 intentionally detected heap conflict command failures. They remain
in the report/logs. Nonrace values and masked counter/CAS outcomes are tested in
these limited schedules; they do not prove all interleavings, absence of tearing
for every mixed-size range, or preservation of all ordinary-access observations.
The historical 149 signatures are not treated as a current-guest census.

### If proceeding to a broader design

A load-only repair is insufficient. A broader design must define exact byte-range
semantics for store/RMW/cmpxchg and ordinary accesses, overlapping/unaligned ranges,
compiler lowering/reordering, host imports/bulk/SIMD operations, and ownership of
shared data. Native exact-width writes/RMW/CAS or another sound overlap mechanism
need their own design; changing only nearby optimistic reads is not enough.

Verification should include positive/negative lane/alignment/boundary cases,
adjacent and overlapping byte/halfword/word operations, source alias/ownership
analysis, MP/SB/IRIW and mixed-size ordering tests against the intended WASM
model, both native target executions, and independent reproducible generation.
Detector capability must itself have positive controls. Do not infer coverage
from mmap silence or assembly silence; keep instrumented diagnostic counterparts
and explicitly model their differences. Do not hide conflicts, make all accesses
atomic by default, use static function/address lists, or redesign backing merely
to make the current report count zero.

## Generation, provenance and verification

The official fixed-input guest was rebuilt twice. Linked Wasm remains
`3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba`;
optimized guest remains `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
The real guest origin is f14764c; it is not relabeled as the later host/recipe SHA.
[Guest receipt](v050-correctness-fixes-evidence/guest.json) keeps actual toolchain,
source, two builds and historical canonical-manifest identity at build time.

The goccy pin/archive remain unchanged. The original nine patches are byte-identical;
FD and bulk add two ordered patches, for **11**. Native load specialization is a
separately registered installer/handwritten ownership boundary. Raw translation,
adapted inventory, canonical generated provenance and license mirrors are updated.
Only generated `code/base/base.go` and `code/base/relative.go` differ from A–D;
all guest function bodies and initial data identities remain unchanged. Seven
new handwritten primitive/test files expand the explicit ownership list from
14 to 21. Cheap canonical verification also binds those copies to their templates.

Two full Go generations through translate → memory32 fixture → source adapter →
installer were compared byte-for-byte, including ownership files. The final
[regeneration receipt](v050-correctness-fixes-evidence/regeneration.json) records
PASS; the memory32 fixture passes 2,472 cases and 1,693 expected guest traps.
Exact-source host `ae80130` was built in a clean independent .git-directory clone
and checked with scripts/git_identity.py; worktree VCS stamp limitations were
not used to mislabel a host. Fresh [library attribution](../../release/generated-license-evidence.json)
retains positive definitions for all 12 groups against that actual host/source.
The unchanged function map is referenced from A–D rather than duplicated.

| Check | Outcome | Evidence |
| --- | --- | --- |
| Original 26-case oracles | 18 PASS / 8 FAIL before; 24 PASS / 2 diagnostic FAIL after | Before/after results. Remaining failures are rejected wide-read alternative and ordinary heap conflict, not adopted fixes |
| Allocation/bulk/narrow positive and negative boundaries | PASS | [Final boundaries](v050-correctness-fixes-evidence/final-boundaries.txt) |
| Canonical base race gates | PASS | [Base race](v050-correctness-fixes-evidence/base-race.txt); no full-memory correctness inference |
| Canonical check | PASS | [Log](v050-correctness-fixes-evidence/canonical-check.txt): source-owner cases, Go tests/vet, 582 Python cases, 18 subtests; 37 ordinary opt-in/environment SKIPs are not qualified runtime claims |
| SQL/transaction, sessions/isolation, Snapshot/Fork/LoadSnapshot, cleanup | PASS | [Go lifecycle](v050-correctness-fixes-evidence/native-go-lifecycle.txt), [default/OOB suites](v050-correctness-fixes-evidence/native-go-integration.txt), [28 Python cases](v050-correctness-fixes-evidence/native-python-integration.txt) |
| Source/provenance/template bindings and license mirrors | PASS | 19 focused source-owner cases, canonical verification and fresh attribution |
| Heap/mmap reduced operations and SC litmus | Functional outcomes PASS; 14 expected heap conflict failures | Study report and individual logs; detector failures preserved |
| Ubuntu24.04 x86_64 native execution | SKIP | No native runner available; amd64 compile/disassembly only, not runtime PASS |
| Minimum macOS15 / alternate Go matrix | SKIP | Local macOS27.0.1 arm64, Go1.26.8; support scope unchanged |
| Full guest race census | NOT RUN | Deliberately excluded; observation gaps invalidate a zero-count safety inference |
| Final Qualification / Product Validation | NOT RUN | Required Human decision boundary; no release-ready or performance claim |

Reproduction commands use a fresh owned workspace and fixed source, task caches
and Go1.26.8: formal scripts/build_generated_guest.py; the A–D adoption chain with
the now-fixed recipe; scripts/regenerate_release_guest.py; scripts/verify.py check;
original probe.py; and shared-feasibility/run.py --converter <the checksum-bound
translation/wasm2go> --output <new-dir>. Source and results are not guessed from
stale binaries. Evidence-hashes.json records normalized copies and original bytes.

Recovered issues were engineering/harness issues, not erased failures: the
converter initially stripped new native guard declarations, the ownership fixture
needed its new template sources, the old nine-count assert became an exact
ordered 11-patch assert, a Go integration invocation omitted its required opt-in
environment flag, and direct vet required its standard underlying-tool variable.
A test ownership addition during a generation changed exactly narrow_load_test.go;
that mismatch was identified, then the final frozen owner recipe was regenerated.
Missing wat2wasm prevented two unrelated upstream fixture invocations; the existing
helper tests passed and our real-opcode byte fixture needs no WAT compiler. These
missing-tool cases are not claimed PASS. No product guard or oracle was weakened.

## Remaining v0.5 limitations and Human decision

The three defects are repaired for the tested supported private-DB execution
boundary. Exact-load operand/ISA properties and bounded lane/ordering patterns
are established; general shared-memory correctness is **not** established.
Widened store/RMW/cmpxchg, mixed ordinary accesses, compiler/alias/lifecycle
reasoning and detector observation limits remain. Native external file mutation
and physical storage reservation are separate explicit limitations above.
Heavy resource/performance comparison, native Ubuntu and final exact-candidate
qualification remain unexecuted. Persisted snapshots for this same guest retain
their identity/format; old 13.1.0 guest snapshots remain incompatible as recorded
in A–D. No snapshot identity check was weakened.

Stop for the human to choose: proceed toward v0.5 with these shared-memory
limitations stated, or require the broader design and verification before release.
Neither choice is inferred from these local PASS results. No main merge, tag,
release/publication or qualification submission is part of this task.
