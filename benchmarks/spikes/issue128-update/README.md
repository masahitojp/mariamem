# Issue128 — initial MariaDB update-cost slice

Decision now: **continue only to a separately budgeted real build/binding
comparison; lower total update cost remains inconclusive**. The same three
shared source repairs make the original legacy and native patch stacks apply
to 13.0.2 with fuzz=0; neither native stack then needs a native-specific edit.
That supports continuing a finite comparison, not claiming a maintenance win.
The strongest objection is that native still carries every shared prepared
repair plus internal THD/Item/Protocol/session dependencies and the binding
review cost already observed in #127. Source application cannot show that wire
simplification pays those costs back. If the real comparison increases total
work, reconsider the placement/approach rather than accept fewer bridge lines.

This initial slice is complete; **#128 and parent #65 remain open**. No guest or
host build, translation, runtime test, benchmark, CI, adoption or release occurred.
No product source, original guard or runtime oracle was changed. The files in
`adaptations/` are source-only trial inputs, not a production upgrade patch set.

## Actual target and comparison identities

| Input | source_commit | tag_object_sha |
| --- | --- | --- |
| MariaDB 12.3.3 base | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` | `bd852bcd567fedc89ad4521e2f1a64c7a1e0d0f0` |
| MariaDB 13.0.2 target | `620a4b5624222048fece7fe1789978ae0675cae2` | `308a50778fb4916ddde0d2923feea3d11dcc92c8` |

Both official annotated tag objects were fetched shallowly, inspected with
`scripts/git_identity.py`'s `inspect_ref`, and their commits checked with
`require_commit`. Both entire downloaded source archives were checked against
the Git blob identities of their official tag trees: **26,928 / 27,071 files**,
zero missing/extra/mismatching blobs. Target archive SHA256:
`f4aee0d043f844d287a9b6b0a1ae9a103d6dda407d807b80358943416da7d37e`.
[Identities](evidence/source-identities.json),
[official tag discovery](evidence/official-tags.txt),
[archive/tree check](evidence/archive-tree-check.json),
[download hashes/timings](evidence/download-commands.json).

The comparison uses the three immutable mariamem inputs named in the plan below.
All three use the same 12.3.3 engine and identical four portability/redo/prepared/
alignment patches. The native canonical `source.patch` is the legacy patch plus
prepared UCA; it equals the older native's canonical patch. UCA therefore
belongs to the shared prepared-base work when comparing a future legacy/native
candidate with equal inputs, not to native wire's maintenance cost. The shipped
legacy baseline itself did not yet contain UCA. No runtime comparison between
those unequal bases is claimed. [Input comparison](evidence/candidate-comparison.json).

## Source trial and first failures

We fetched full archives, extracted a fresh full target engine for each path,
and copied the exact locked WASIX recipe. These are partial preparation trials:
dependency submodules, wire overlay assembly and the remaining full canonical
preparation/build pipeline were not completed. The original archive lock would
reject the different source archive before extraction. On the diagnostic tree,
the original full preimage guard rejects `configure.cmake`; UCA rejects
`include/m_ctype.h`; routine preparation rejects the target server version.
Those failures remain failures. Applying patches after them is explicitly an
independent diagnostic, never canonical preparation success.

| Shared work on the same target | Observed result / required adaptation |
| --- | --- |
| Portability preimages | `configure.cmake` and `fil0fil.cc` changed. Original portability patch applies fuzz=0. Review and repin complete before/after files; configure checks were removed upstream, not relaxed here. |
| Redo portability | Original patch rejects. `log_t::attach` now takes `log_access` and the `mprotect` call moved outside the PMEM conditional. The trial rebase guards that new call for WASIX while retaining the target mapping lifecycle. This needs real build/recovery acceptance. |
| Prepared API patch | Original patch reports success, but its zero-context EOF insertion at old line6641 lands **before the final closing brace** on target line6642. It nests the adapter inside `mysql_embedded_connect`, an invalid placement. Rebase EOF insertion by one line under the exact new full-file preimage. Other zero-context insertions precede upstream changes and were inspected. |
| Alignment | Complete `buf0buf.cc` preimage changes (upstream error text); original patch applies fuzz=0. New complete hashes still require review/registration. |
| Page-cleaner wake fix | Original `source.patch` rejects. The target added `create_spare_archive` and a `timed_wait` branch. Trial rebase wraps **both original target waits** in the existing sync-LSN recheck while preserving that branch/label. This is a real concurrency adaptation requiring runtime verification. |
| Prepared UCA input | `ctype-uca.c` and the Unicode data are byte-identical; `m_ctype.h` adds an unrelated inline helper. A separate exact-target fixture rebind passes unchanged numeric/table/header oracles and emits the same `ce55cdcc…` header. No new table producer/runtime equivalence test ran. |
| Routine schema | Exact-target source/version fixture rebind passes original DDL hash, column/key/engine metadata checks. The generated header changes its source provenance comment; no schema semantics were changed. |
| Initialization/auth hooks | Original strict anchor-based helpers apply on all three diagnostic trees; this is source evidence only. |

The first original native patch reports one failed `sql_prepare.cc` hunk, adding
`mariamem_spike_decodes`. **This is fallout from the misplaced shared adapter,
not a demonstrated native-specific upstream conflict.** After the three shared
source repairs above, both the old and #127-separated native experimental
patches apply completely unchanged with fuzz=0 and no rejects. The adapter is
then outside the preceding function and the original counter declaration lands
at EOF. There was no need to alter the native decoder/capture/rollback gates.

The original prepared function-body fixtures pass even on the initial malformed
diagnostic tree. They do not check surrounding lexical placement; patch success
and this component oracle alone are insufficient. The unchanged complete
preimage guard **does** catch this update, so this is not a silently accepted
canonical build. Original function-body/runtime oracles were not rewritten.
The misplaced/corrected EOF placement was independently replayed on the
target's pristine prepared implementation, with full resulting hashes and tail
lines saved in [the placement proof](evidence/prepared-placement-proof.json).

[Initial observations, raw patch output and rejects](evidence/trial-initial.json),
[corrected observer replay](evidence/trial-results.json),
[shared-rebase application](evidence/trial-adapted.json),
[exact rebase preimages](adaptations/review.json),
[target UCA/routine rebind](evidence/shared-input-rebind.json),
[target fixture diff](adaptations/shared-input-rebind.patch).
The first observer incorrectly called the keyword-only routine helper and a
replay initially found the existing recipe extraction directory. Both tooling
failures are preserved; the corrected replay observes the real version guard.
Neither was treated as a MariaDB runtime defect or used to change an oracle.

## What remains dependent on MariaDB internals

Of the 12 upstream engine files touched by the native patch, six are unchanged:
Vio declaration, embedded `lib_sql.cc`, client transport, NET and both Protocol
files. Six changed: Item, THD implementation/declaration, ACL, parser and
prepared implementation. Eight additional files are recipe/platform or newly
added glue/policy/controller files. Patch applicability is favorable evidence,
but it does not test these interfaces. [Complete surface hashes](evidence/surface-inventory.json)
and [upstream diffs](evidence/upstream/).

Specific remaining checks are conversion snapshot/restore over `Item_param`
and `PValue_simple`, descriptor/type handlers, THD/NET/Protocol initialization,
authentication bootstrap and session stop/join/rollback/capture ordering.
Upstream added an Item base field, changed THD's inheritance by removing
`MDL_context_owner`, and extended `mysql_open_cursor` arguments. These are
concrete layout/interface changes even where hunks still apply. We have not
observed a compile/runtime failure from them. Regeneration and exact worker
binding review must discover relocations, TLS changes and relevant offsets;
#127's binding cannot be assumed valid for this new engine.

Native bootstrap separation reduces the linked legacy entry surface, but still
prepares the same embedded TIME/unsigned/dynamic-result/parameter-metadata/type
patch. It has not reduced that update work in this trial. For #131, prioritize
actual internal contact reduction and unnecessary retained repairs; moving
source into a different file alone does not remove these dependencies. Maintain
guest authority over SQL/capture and native stop/join, and the original D1–D3
contract; no new host parameter decoder is justified by these results.

## Cost and next decision

Measured command wall time: official identity fetch **1.79s**; three cold archive
downloads **27.29s** (147,459,317 bytes total). Original source trials take
**26.88s** in total, corrected observer replay **27.48s**, shared-adapted replay
**26.99s**. Each path is about9s, largely extraction. These source-only numbers
are not complete update cost or a statistically meaningful native/legacy speed
comparison. Acquisition, human inspection and tooling are shared work; native
incremental runtime/binding repair remains unknown.

The observer session began around04:43 UTC. Active time is an estimate, not a
stopwatch measurement; final accounting is in [timing](evidence/timing.json).
No SDK, toolchain, compiler, generated Go, host, runtime or heavy CI ran. Sampled
owned usage remained below1GiB with more than19GiB free; the existing guard used
the agreed2GiB ceiling/12GiB floor. Samples are not an exact continuous peak.

Proposed **next** comparison, requiring a new explicit budget: allow **2h active
including at most30min tooling**, two clean guest builds, two translations/host
builds, finite original compatibility/lifecycle/limits/G1/G2 and binding review,
0 heavy CI initially. Plan **60min timeout per cold guest build**, **30min per
translation/host build**, and **30min per finite runtime suite**, with stop at
the first unresolved shared or semantic failure. #127 observed roughly20min
for initial compile/acquisition,5min continuation and5min host compile; these
are historical estimates, not measured13.0.2 times or guarantees. Build storage
needs a separately agreed ceiling (the earlier12GiB owned allowance cannot be
spent under this slice's2GiB ceiling); keep12GiB free floor and run candidates
sequentially, disposing each build after compact evidence collection.

First register exact target archive/preparation/patch identities and inspect all
new full-file postimages; complete a fresh full preparation including pinned
dependencies. Put the reviewed shared UCA/prepared base on **both** paths and
use the same locked compiler/sysroot/Binaryen/converter/platform. Do not require
a warmed cache or an old local workspace. Compare end-to-end manual analysis,
patch repair, compiler/linker failures, binding investigation, regressions and
verification wait separately. Stop if the2h active budget cannot resolve the
first failure and return the missing evidence/cost, not an expanded campaign.

Final #128 conditions: real guest builds and regenerated bindings; affected
compatibility and lifetime semantics on the same target; total-cost judgment;
then recheck only differences introduced by the final #131/#134/#135 adoption
candidate. C3 settings/debt/lifecycle and supported-platform/public acceptance
remain owned by their existing tasks. None of the old127/C2 PASS records is a
PASS for13.0.2. Product adoption and any later versioned release are separate.

## Reproduction, verification and retention

On this experiment commit, with an empty owned scratch directory and the stated
disk limits, run the following using Python3.14:

```sh
python3 scripts/experiment_disk.py --work-dir build/issue128-temp \
  --min-free-gib 12 --budget-gib 2 --timeout 1200 -- \
  python3 benchmarks/spikes/issue128-update/trial.py fetch
python3 scripts/experiment_disk.py --work-dir build/issue128-temp \
  --min-free-gib 12 --budget-gib 2 --timeout 1200 -- \
  python3 benchmarks/spikes/issue128-update/trial.py trial
python3 scripts/experiment_disk.py --work-dir build/issue128-temp \
  --min-free-gib 12 --budget-gib 2 --timeout 1200 -- \
  python3 benchmarks/spikes/issue128-update/trial.py trial --adapted
```

The script deliberately records strict failures and then runs diagnostic patch
applications; its exit0 means the observations were collected, never that the
target is prepared/qualified. `adaptations/` rebases only the three shared source
sites, under exact target file hashes; native experimental patches remain the
immutable original inputs. To reproduce the separate input rebind, unpack the
native candidate's guest/scripts/lock/UCA bundle, apply
`adaptations/shared-input-rebind.patch`, extract the target VERSION, UCA inputs
and system-tables SQL, then call unchanged `uca_prepared.prepare(root, source)`
and `routine_schema.prepare(source, root=root)`. Their original numeric and
metadata expectations must pass; new identities do not establish runtime
equivalence. Archive/tree verification hashes each tar file/symlink as a Git
blob against `git ls-tree -r -z` of the official fetched tags.

Only compact evidence, inspected diffs, rebase inputs and reproduction tooling
are retained. Evidence path substitutions are documented with original/normalized
hashes in `evidence/normalization.json`; original patch output/reject content is
preserved. Fetched archives, shallow identity repository, full extracted engines,
recipe, selected files and Python cache are disposable and removed. The Orca
worktree and branch lifecycle belong to the coordinator. No other worktree,
shared cache or parent65 file was touched. Final verification and storage are
recorded in `evidence/verification.json` and `evidence/storage-final.json`.

## Plan recorded before source trial (2026-11-08)

Question: does the bootstrap-separated native candidate plausibly reduce total
MariaDB update work compared with the shipped legacy path on the same target?
Input: #127 result at `46915e50c12795da4787c9d1ee0b73e6c6a829dc`;
native guest `8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`, older native guest
`be244a0bdb510a22417241c2aa2f76a9093aac1b`, legacy release source
`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`.

Target selection: official tag discovery has no successor to 12.3.3 in 12.3.
Use **13.0.2** (Stable rolling, a forward evolution of 12.3), not an RC/Preview
or a reverse move to 12.3.2/11.8.9. This is a larger change than a patch update
and cannot predict the cost of an unavailable 12.3.4. The official
[release announcement](https://mariadb.org/mariadb-13-0-is-now-stable/),
[release notes](https://mariadb.com/docs/release-notes/community-server/13.0/13.0.2),
[release index](https://mariadb.org/mariadb/all-releases/) and
[maintenance policy](https://mariadb.org/about/) identify this as the current
Stable rolling series, with a shorter support window than LTS (Q4 2026).
This is an experiment target, not product adoption or release approval.

Finite evidence: pin annotated tags and peeled commits with git_identity;
download actual official target source; compare unchanged candidate preparation
guards; attempt original patch series with fuzz=0 on disposable trees; preserve
first failures/rejects and inspect affected internal interfaces. Attribute shared
WASIX/prepared/UCA work separately from native changes. A diagnostic patch
application after a failed pin is never canonical preparation success.

Environment: macOS arm64; `/opt/homebrew/bin/python3.14`, system Git/patch;
same source target and patch command for both paths. No shared warmed cache.
Budgets: 2h active including at most 30min measurement tooling, 0 heavy CI,
0 guest/host builds, 0 runtime/benchmarks; 2GiB owned scratch and 12GiB free floor,
guarded command timeout 20min. Initial filesystem sample: about 20GiB free.
Scratch is confined to this worker's `build/issue128-temp`; other worktrees and
shared caches are outside cleanup authority.

Exit: initial continue/reconsider/inconclusive recommendation with contrary
evidence, measured command wall times and honest active estimates, required
adaptations, finite next build/binding/semantic comparison and its proposed cost.
If disk/network/source/guard failures prevent meaningful comparison, preserve
them, clean owned scratch and report inconclusive; do not relax preimages or
oracles, grow the budget or mark #128 complete.
