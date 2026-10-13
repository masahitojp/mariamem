# v0.5.0: reduce adjacent-access uncertainty before adoption

Follow-up: the maintainer approved formal adoption. The
[integration report](v050-exact-writers-integration.md) records canonical
generation, independent byte equality and final-runtime local regressions.
Native Ubuntu verification is handed to CI and remains pending in that report;
the results below retain their original isolated-spike scope.

**Human direction:** request additional design and verification instead of
accepting the unquantified shared-memory limitation. Starting point:
`753a015b9affa9fd8d19cff34e68feec7eabe5ae` and the
[real-guest impact study](v050-shared-impact.md); bounded fixes remain at
`82f3c2bcef1518dadf5138a03e11dcfeb3db2de6`.

**Design result:** an isolated exact-width native writer candidate passed the
bounded native tests and the existing real-guest parallel SQL comparison.
Its machine operands access the requested one or two bytes. This removes the
additional neighboring-byte exposure from the candidate's narrow operations.
**Production adoption is not performed in this design/verification task.**
General shared-memory correctness and v0.5.0 release readiness remain unproved.
Following the repository's Explore → Challenge → Human decision → Implement →
Verify cycle, this report presents a concrete candidate for the implementation
decision. No canonical generated source, provenance, failure oracle or guest
input was changed.

## User consequences, with uncertainty kept explicit

| Concern for the user | What this design changes | What is still unknown |
| --- | --- | --- |
| Unrelated internal state interferes with an update because it happens to share a four-byte word | Candidate narrow loads, stores and CAS touch only their requested bytes. The extra neighboring read/write is structurally removed, including for purge/guard/read-view layouts. | This does not repair an actual same-byte ordinary/atomic conflict. Source ownership across every other guest path is not proved. |
| Parallel operations wait or retry unnecessarily | Candidate stores use a native narrow store (arm64) or narrow exchange (amd64), rather than a widened CAS loop. Adjacent-byte changes no longer enter a four-byte software comparison. | RMW contention still retries. ARM exclusive reservation granules can include neighbors and trigger internal retries. No latency bound or performance improvement is established. |
| Wrong SQL result, crash or stalled connection | Candidate and control passed the same four real-guest runs: default and AHI-on, five scenarios each. Outcomes matched. | Finite runs do not exclude rare schedules. No pre-existing SQL corruption was reproduced, so these are regression checks, not proof that a previously observed SQL defect was repaired. |
| A defect is missed by the tests | Positive heap detector controls still fail as expected, while mmap and assembly blind spots are recorded separately. | Assembly makes even heap atomic accesses invisible. Fewer race reports after substitution are not evidence of race elimination. |

The [span analysis](v050-exact-writers-evidence/span-reduction.json) applies the
candidate's machine operand widths to the **selected prior address examples**.
Sixteen of seventeen saved pair examples become disjoint. One remains a
same-byte ordinary initialization versus later purge access, with simultaneity
unproved. These numbers describe the retained examples only; they are not a
risk percentage, complete pair census, or fresh candidate address trace.

## Chosen candidate and rejected shortcuts

Use exact-width native operations plus conservative ordering, preserving the
existing logical bounds and natural-alignment checks. A standalone candidate
supports store, add/sub/and/or/xor/exchange and cmpxchg at 8/16 bits. RMW uses
an exact-width load and CAS loop; values wrap to the requested width and old
values return zero-extended. Ordinary neighboring accesses remain ordinary.

| Target | Load / store | Compare-exchange | Ordering rationale |
| --- | --- | --- | --- |
| macOS arm64 | LDARB/H; STLRB/H | LDAXRB/H + STLXRB/H retry; mismatch clears the exclusive reservation | DMB ISH before and after each primitive, with acquire/release instructions |
| Ubuntu x86_64 candidate | MOVBLZX/WLZX; memory XCHGB/W | LOCK CMPXCHGB/W | Fenced loads; locked memory operation ordering |

The operand-width rationale follows the [Arm synchronization instruction
families](https://support.arm.com/documentation/ddi0487/md/-Part-B-The-AArch64-Application-Level-Architecture/-Chapter-B2-The-AArch64-Application-Level-Memory-Model/-B2-12-Synchronization-and-semaphores)
and [Intel instruction reference](https://cdrdv2-public.intel.com/782156/325383-sdm-vol-2abcd.pdf).
The [Wasm threading proposal](https://github.com/WebAssembly/threads/blob/main/proposals/threads/Overview.md#atomic-memory-accesses)
requires requested widths, truncation/zero extension, natural alignment and
sequentially consistent atomic operations. These references provide the design
contract; finite litmus tests supplement them rather than proving a complete
mixed-size/native/Go mapping. On x86, failed CMPXCHG can issue a target-width
write-back of the observed value; logical value preservation is not a claim
of no physical write or readonly-memory support for CAS.

The [native](v050-exact-writers-evidence/native-writer-disassembly.txt),
[cross-built amd64](v050-exact-writers-evidence/linux-amd64-writer-disassembly.txt)
and [actual candidate host](v050-exact-writers-evidence/guest-writer-disassembly.txt)
disassemblies confirm operand widths. The amd64 16-bit CAS includes LOCK byte
`f0` in its encoding even where Go objdump's printed mnemonic omits LOCK.
Stack/argument accesses are distinct from guest-memory operands; hardware
cache-line/bus traffic and exclusive monitor granules are not measured.

Keeping a masked 32-bit CAS would retain the extra neighboring footprint.
Adding a mutex only around atomics would fail to coordinate ordinary accesses.
Serializing all guest accesses would be a much larger engine/performance change.
Neither shortcut is used. The candidate introduces no race suppression and
does not make all ordinary accesses atomic.

## Verification and actual identities

The baseline was checked with `scripts/git_identity.py inspect HEAD` as a commit
object before builds. Its canonical generated-source check passed. The guest
hash remains
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
The unchanged guest was compiled from existing canonical source; this task did
not rebuild the MariaDB Wasm or update converter inputs.

The [spike runner and templates](../../benchmarks/spikes/v050-exact-writers/)
construct isolated modules and copy the production mmap memory owner with its
hash recorded. Native testing uses Go 1.26.8 on macOS arm64, both Go heap and
production-style mmap backing. The [results](v050-exact-writers-evidence/results.json)
and [saved-file/binary identities](v050-exact-writers-evidence/identity.json)
retain outcomes separately from detector reports.

| Check | Result and evidence |
| --- | --- |
| Values, wrap, zero extension, success/mismatch cmpxchg, all valid byte/halfword lanes, exact logical end, misalignment and unsigned address wrap | PASS; `heap.txt`, `mmap.txt` and corresponding `-race.txt` receipts |
| Ordinary adjacent-byte writes against each candidate operation | PASS value/sentinel checks at both widths/backings; machine operands establish disjoint ranges, detector silence alone does not |
| Four-agent same-target increments; overlapping atomic byte/halfword stores | PASS in bounded runs; many legitimate same-target CAS retries remain |
| Store buffering, IRIW, publication, and narrow-RMW versus Go 32/64-bit atomic ordering | PASS in bounded tests; 1,000 trials per width/configuration, not an exhaustive memory-model proof |
| Normal target overlap diagnostic | Executed; no detector report even on heap because ASM is hidden. No same-target safety verdict |
| Plain-payload publication diagnostic | Values passed normally; heap `-race` FAIL with one report, demonstrating missing detector-visible ASM synchronization |
| Instrumented ordinary race and widened-CAS neighbor positive controls | Heap `-race` FAIL as expected (one report each in the final run); mmap has zero reports |
| Native go vet; native and linux/amd64 compile | PASS |
| linux/amd64 instruction execution on this arm64 Docker host | PASS heap/mmap under emulation; [receipt](v050-exact-writers-evidence/linux-amd64-emulated.json) identifies the pinned arm64 image and amd64 binary |
| Native Ubuntu x86_64 runtime / race validation | **SKIP:** no native x86_64 runner. Emulated execution is supplementary |
| Existing base-package tests in the isolated candidate | PASS; [receipt](v050-exact-writers-evidence/candidate-base-tests.txt), including previous bounded runtime tests |
| Real guest default / AHI-on control versus candidate | PASS five cases in each of four runs; [comparison](v050-exact-writers-evidence/guest-comparison.json) |
| Independent construction of the isolated adapter output | PASS identical adapted base and added native source hashes; both installation manifests saved |
| Canonical source unchanged / candidate copy rejected by canonical checker | PASS / expected rejection; ownership was not relaxed and candidate provenance was not refreshed |
| Public-source check for new/touched study files | PASS with the unchanged checker on a scoped copy; full checkout check still FAILS on pre-existing tracked correctness-evidence `.log` files, not changed here |

The three intentionally failing heap detector diagnostics remain in saved
results and logs. They are not recategorized as successful correctness tests.
The widened-CAS positive control is a standalone equivalent of the previous
footprint, not a new real-guest corruption oracle. The original converter/Wasm
failure fixtures remain unchanged. Timing differs across cold starts; this
study does not compare product performance.

The hash-bound [experimental adapter](../../benchmarks/spikes/v050-exact-writers/install_candidate.py)
changes only the disposable copy's two store bodies and its shared subword
helper, using the native source templates. All 147 current-guest writer sites
still call the same named helpers. It rejects a changed input or repeated
installation. Independent copies matched adapted-base hash
`cd9d121cfe654ea4185f6b47ef657a62a9926eaca4644c397bad9087461d1779`
and added native-file hashes. The first host construction's test-only template
hash predates the extended diagnostic tests; the independently repeated
runtime source/ASM identities still match. This is **prototype reproducibility**,
not canonical Wasm→Go regeneration or a release provenance receipt.

## Remaining decision and implementation boundary

The evidence favors implementing exact-width native writers through the
existing platform-bound owner/installer. That removes the added neighboring
exposure at the known 8/16-bit sites without changing guest data layouts or
ordinary access behavior. It does not establish general shared-memory safety.

Before production adoption, the implementation step must:

1. Move the selected primitives and narrow-writer lowering into canonical owner
   templates/adapter, retaining full-width operations and explicit unsupported
   platform behavior. Cover real converted Wasm opcodes for all affected narrow
   store/RMW/cmpxchg families, including i64 wrappers, rather than relying only
   on this guest's four helper shapes.
2. Independently regenerate through the formal route, inspect output/provenance
   and distribution inventories, and preserve negative ownership checks. The
   disposable-copy method here is not a substitute.
3. Run focused lifecycle/session/SQL/Snapshot/isolation and consumer regression
   checks tied to the changed runtime, and native Ubuntu x86_64 checks. Obtain
   performance evidence separately once correctness and source identity hold.
4. Continue source/ordering analysis for real same-target ordinary access,
   wider/misaligned/bulk/SIMD/host overlaps and compiler lowering if claiming
   general shared-memory correctness. No full guest race census was performed.

**Production status:** the earlier limitation remains until this candidate is
formally adopted and verified. This task reduces uncertainty about a concrete
remedy and its bounded user-visible regressions; it does not claim that every
shared-memory risk is gone. No final Qualification, Product Validation, main
merge, tag or publication was performed.
