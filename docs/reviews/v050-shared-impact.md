# v0.5.0 real-guest shared-memory impact: Human decision material

**Decision remains open.** In the fixed MariaDB 12.3.3 guest, narrowed 8/16-bit
atomic **writers** still operate on aligned 32-bit words in Generated Go. The
bounded parallel SQL scenarios executed several of those paths, including
adjacent fields used by different guest agents. All observed SQL outcomes passed;
no wrong result, hang, error, or crash was reproduced. Address-footprint overlap
is established for selected sites, but simultaneous conflicting instructions,
happens-before, and general shared-memory correctness are **not** established.
This investigation makes no release-ready determination and requests the Human
choice described below before final Qualification or Product Validation.

This is a follow-up to [the three correctness fixes and limited feasibility
study](v050-correctness-fixes.md) at
`82f3c2bcef1518dadf5138a03e11dcfeb3db2de6`. The original failure oracles,
canonical guest, converter, and Generated Go are unchanged. Work was confined to
`experiment/v050-shared-impact`, disposable copies, spike tools, and this report;
it does not change product behavior. It is not a race census or an mmap redesign.

## Exact inputs and interpretation

The baseline commit was checked as a **commit object** with
`scripts/git_identity.py inspect HEAD` before builds; `git status` was clean.
The canonical source check passed before instrumentation. The fixed-input
development guest build returned Wasm SHA-256
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`,
equal to the release guest pin; linked Wasm was
`3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba`.
The source archive is MariaDB source commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, archive SHA-256
`36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845`.
The preparation manifest shows that the MariaDB headers cited below were not
guest-patched. See [identities](v050-shared-impact-evidence/identities.json) and
the [A–D fixed-input report](v050-ad-integration.md). The build is explicitly
`development-unqualified-v1`, not a release qualification.

The same Wasm was disassembled using pinned Binaryen `version_133`. The
[checksum-bound scanner](../../benchmarks/spikes/v050-shared-impact/scan.py)
checks both the guest hash and canonical function-map hash before joining Wasm
function indexes to source names and Generated Go call sites. Its
[site-level Wasm map](v050-shared-impact-evidence/wasm-sites.json),
[Generated Go map](v050-shared-impact-evidence/generated-sites.json), and
[comparison](v050-shared-impact-evidence/wasm-go-comparison.json) are the
reproducible scope record:

| Fixed guest | Wasm instructions | Generated Go helper sites |
| --- | ---: | ---: |
| 8-bit atomic store | 110 | 132 |
| 16-bit atomic store | 4 | 4 |
| 8-bit atomic exchange | 9 | 9 |
| 8-bit atomic add | 2 | 2 |
| 8/16-bit atomic cmpxchg | 0 | 0 |
| **Total** | **125** | **147** |

This absence of narrow cmpxchg is limited to this fixed guest; the generic
converter still has the residual helper. The larger Generated Go count reflects
control-flow and callee expansion, not a different guest: for example Wasm
Fn17218 calls Fn17221 (one store8), while Generated Fn17218 contains two store8
sites; Wasm Fn18570 calls Fn17437, while Generated Fn18570 contains a store8.
Direct caller edges are in the [call evidence](v050-shared-impact-evidence/candidate-wasm-calls.json).
Indirect calls and field ownership are not proved by this map.

The existing [helper](../../internal/generatedgo/code/base/base.go) computes
the aligned 32-bit word at `ea &^ 3`. In an uncontended module it performs a
plain 32-bit read and masked write; in a contended module it uses an atomic
32-bit load and masked CAS retry loop. A requested 1- or 2-byte writer thus
reads four bytes and may write four bytes, including adjacent lanes. A successful
CAS uses the last observed word and preserves the adjacent *bit values*;
therefore sharing a word alone does **not** prove adjacent-value corruption.
The semantic differences are extra reads/writes, possible failed CAS retries,
and changed overlap/ordering with truly narrow atomic or ordinary access.
The previous bounded fixture found heap `-race` reports for widened
store/RMW/cmpxchg, while mmap had none, and assembly loads were invisible to the
detector even on heap. Mmap silence here cannot establish safety.

## Parallel execution and how it was observed

[The scenario driver](../../benchmarks/spikes/v050-shared-impact/scenarios.py)
used the existing Python consumer with PyMySQL 1.2.3 against the real host:
four connections doing 120 total updates/reads/commits; a competing update
blocked until rollback then committed; a repeatable-read view across another
commit; 32 connection start/select/update/rollback/close cycles; and 1,000
iterations of point plus secondary-index reads across four workers. The default
run kept `innodb_adaptive_hash_index=OFF`. A second run explicitly turned it
`ON` to reach the index-maintenance paths; this is an alternate configuration,
not a claim that default workloads use AHI. Control and observed hosts ran the
same final driver in each configuration.

[The disposable observer](../../benchmarks/spikes/v050-shared-impact/instrument.py)
wrapped all 147 Generated Go narrow writer call sites and selected ordinary/
atomic effective-address checks in 24 functions; it recorded a CAS-loop retry
hook. Each wrapper delegates to the original checked helper, and it records
before the actual access without reading guest bytes. `Module` pointers identify
guest agents in one run. The complete change and source hashes are in the
[instrumentation manifest](v050-shared-impact-evidence/instrumentation-v2.json).
The instrumented copy appropriately **failed** canonical source verification;
the unmodified source passed. Neither copy was installed as a canonical
artifact. The observer perturbs scheduling, may miss ordinary accesses outside
selected functions, and cannot prove simultaneity or happens-before. Its row
limit was not reached; no rows were dropped.

The [scenario receipts](v050-shared-impact-evidence/scenario-results.json)
record all five cases as PASS for uninstrumented and observed hosts, both AHI
settings. Each reported four committed values of 30, final contested value 1,
read-view sequence `[0,0,1]`, and expected rollback behavior. The control and
observed versions both returned `12.3.3-MariaDB-embedded`. No functional
difference was reproduced in these finite executions. Startup and case timing
varied with instrumentation and cold starts; they are not performance evidence.
One sandboxed local-port attempt failed, then the same scenario passed with
localhost permission; an initial AHI driver indentation mistake was corrected
before the successful paired runs. These setup failures are not guest defects.

The [trace receipts](v050-shared-impact-evidence/trace-receipts.json) record
8,237 narrow writer calls in 19 functions with default AHI and 11,068 calls in
24 functions with AHI on. They contain the complete selected purge timeline and
address examples. The address-pair numbers (default: 10 ordinary, 26 adjacent
atomic; AHI on: 10 ordinary, 922 adjacent atomic) are **combinations of
aggregated site/agent rows sharing an aligned word over the entire run**, not
simultaneous events or race counts. No CAS retry was observed in these two
instrumented traces; that does not exclude retries on other schedules.

## High-priority real-guest examples

| Source and path | Requested / effective width | Execution and adjacent access | What the record supports |
| --- | --- | --- | --- |
| `trx_purge_t` flags in `storage/innobase/include/trx0purge.h:141-158`; Fn18231 initialization, Fn17161 purge worker, Fn17461 shutdown | atomic byte / 4-byte CAS or plain word; ordinary byte and 16-bit stores retain their own width | Executed at default and AHI-on. The word at `24020808..11` contains ordinary `m_initialized` at +0, atomic `m_enabled` at +1, `skipped_rseg` at +2, and atomic `m_active` at +3, as corroborated by generated addresses. Separate agents access this word. | The strongest observed **ordinary/atomic spatial overlap**. The timeline places ordinary startup accesses before purge-worker accesses and ordinary shutdown accesses after; it does not establish a concurrent collision. No error or wrong result reproduced. |
| Index search information in `storage/innobase/include/dict0mem.h:1072-1091`; Fn17888 `btr_cur_t::search_info_update`, Fn17950 `btr_cur_t::search_leaf` | atomic bytes / 4-byte masked CAS; `n_hash_helps` store16 / 4-byte masked CAS at Fn17888 +220 | With AHI on, Fn17888 recorded 628 writes and Fn17950 2,180 narrow operations across several agents. Generated offsets +68/+69/+70 are adjacent in one aligned word; source declaration order identifies `hash_analysis`, `n_hash_potential`, `last_hash_succ` (exact field-to-offset mapping follows generated offsets, not a DWARF layout proof). Default-AHI scenario did not execute these two functions. | Separate agents touched adjacent requested bytes in the same object address in one run. We did not prove instruction simultaneity, unprotected ordinary access to these fields, or SQL impact. The 16-bit `n_hash_helps` adjacent bytes appear to be padding by source layout; that layout/ownership claim is **inference**, not proof. |
| Read-view `m_open` in `storage/innobase/include/read0types.h:165-181`; Fn16684 `ReadView::open` | atomic byte / 4-byte masked CAS | Fn16684 recorded 2,156 narrow calls in each final run, including calls from different agents to the same requested byte. Source explicitly allows a non-owner to inspect `is_open()` alone. Adjacent `m_mutex` follows in the source; the observed requested address is word-aligned, so whether the extra three bytes are only padding requires layout proof. | High-frequency executed path, but no observed ordinary adjacent-byte hit or resulting SQL anomaly. An overlap with `m_mutex` is **not proved**. |
| C++ one-time initialization guard in pinned libc++abi `cxa_guard_impl.h`; Fn4053 acquire, Fn4054 release | guard byte0 atomic store / 4-byte masked CAS; byte1 ordinary initialization state | Fn4054 ran 21 times in six agents. The generated release path also has a normal byte1 write under the guard mutex. Each observed guard address was released once, and the sample did not show agents contending on the same guard. | Real mixed-width layout and executed calls. Concurrent overlap or harm on one guard remains a static concern; source mutex/guard protocol cannot be replaced by an address-only inference. |
| Thread-pool `m_thread_creation_pending` in `tpool/tpool_generic.cc:229,527,708`; Fn16535 worker clear, Fn16537 add-thread exchange | atomic byte / 4-byte masked CAS | Both ran (8 each default; 12 and 15 AHI-on). Other accesses to the same byte are expected by design. Neighbor layout and ordinary access were not established. | Executed lifecycle route, no verified adjacent-value victim or failure. |

The page-cleaner and buffer-LRU routes also executed (Fn18010/Fn18136).
Generated Go accesses global bytes `15209756` and `15209757` in one aligned
word from different agents. MariaDB defines `buf_page_cleaner_is_active` in
`buf0flu.cc:56`; its exact association with each generated global byte and
neighbor ownership were not proved from symbol/layout evidence. This is an
observed adjacent atomic address footprint, not a source-field or failure
claim. The Fn18136 store16 at object offset +220 corresponds to the
`buf_block_t::n_hash_helps` route and executed even with AHI off.
Fn18241 (`trx_t::commit_persist`) was the highest-count writer function at
4,834 calls per final run; its two generated writer offsets are +1384 and +192
on the transaction object. This study did not establish a neighboring ordinary
field for either offset, so its high call count is priority evidence rather
than an overlap finding.

The bounded default run reached 19 of the 65 functions with a narrow writer;
the AHI-on run reached 24. The other functions are **unobserved in these
scenarios**, not unreachable. Ordinary-access instrumentation covered selected
functions plus literal accesses to the purge word; it is not exhaustive for
indirect, bulk, SIMD, or host accesses. The actual guest has no narrow cmpxchg
instruction, but generic converter cmpxchg remains relevant for future guests.

## Decision categories and residual limits

1. **Reproduced harm:** none in these real-guest scenarios. This does not assert
   absence of harm in other schedules or workloads.
2. **Execution and address-footprint overlap, harm unreproduced:** purge flags
   have ordinary/atomic overlap across lifecycle phases; AHI-on index metadata
   and page-cleaner flags have cross-agent adjacent atomic footprints. Read-view
   flags execute frequently across agents at the same requested byte. No
   simultaneous collision or broken SQL behavior was established.
3. **Static concern:** one-time-init guard byte0/byte1 protocol and potential
   padding/neighbor relationships for ReadView and `n_hash_helps`; thread-pool
   neighboring fields; generic narrow cmpxchg outside this guest. Their precise
   concurrent ordinary overlap or victim ownership is unproved.
4. **Unobserved:** 41 narrow-writer functions even with AHI on; other MariaDB
   workload/configuration paths, indirect or uninstrumented ordinary accesses,
   allocation-generation aliasing, all relevant schedules, and Ubuntu x86_64
   actual-guest execution (SKIP: no runner in this workspace). This macOS arm64
   experiment is not a full guest race census. Mmap-backed guest memory and
   assembly loads remain detector blind spots; heap `-race` fixture conflicts
   from the prior study remain valid evidence but are not guest-wide reports.

The Human may either **proceed with v0.5.0 while explicitly documenting the
shared-memory limitation** (the three bounded fixes remain, but general
shared-memory correctness is not claimed), or **require a broader store/RMW/
cmpxchg and ordinary-overlap design before release**. This report supports the
choice by showing real use and a concrete mixed-layout exposure; it cannot
certify either option as safe. A broader path would need exact-width writer
semantics, ordinary/mixed-size access ownership and ordering, complete guest
source/alias tracing, positive race-detector controls for heap and mmap, and
native macOS arm64 plus Ubuntu x86_64 validation. The present code does none
of that. **Stop for Human decision before final Qualification and Product
Validation.** No merge to main, tag, or publication is part of this work.

## Reproduction and evidence limits

1. From the exact baseline commit and a clean source, run
   `scripts/git_identity.py inspect HEAD` and the A–D guest build's
   `scripts/build_generated_guest.py --development-output <scratch>` in the
   pinned WASIX builder. Confirm `guest.json`'s guest and linked hashes above.
   The first Docker attempt in this study covered the tracked `build/go.mod`
   with an empty mounted build directory and failed the clean-source guard;
   copying that unchanged tracked module file into the mount resolved it.
2. Disassemble *that* guest with Binaryen `version_133` `wasm-dis`, then run
   `scan.py --root <baseline> --wasm <scratch>/mariamem.wasm --wat <scratch>/guest.wat --output <scratch>/scan`.
   The WAT SHA-256 was
   `5a2a644add6c538180c83762b8973775e261ddf662ba6027ae497ae276fe855c`;
   function map SHA-256 was
   `9072658996738894b86effc9b60911db92b413d35cb3c7863f3851666bb645b6`.
   The scanner rejects changed guest or symbol-map input.
3. Build an unmodified host from the baseline with Go 1.26.8. Use
   `instrument.py <baseline> <scratch>/observed` to create a disposable copy,
   then build its host. Both study host builds used `-buildvcs=false` because
   worktree VCS stamping was not reliable; source commit, modified-file hashes,
   and binary SHA-256 are separately recorded in the evidence. Re-run
   `scenarios.py <host> <out> [--observe] [--enable-ahi]`, then
   `summarize.py <out>/events.json` for observed runs. The observer's
   environment output path triggers recording, and its build must **not** pass
   canonical source verification. `export_evidence.py` extracts compact
   receipts; raw event SHA-256 hashes allow comparison with fresh runs, but
   scheduling and raw addresses will naturally vary.

Only spike tooling, source maps, manifests, bounded scenario results, and
selected trace receipts are retained. Generated Go and canonical provenance are
not edited. The prior failure oracle remains in force. Final Qualification,
Product Validation, and any release decision are separate work.
