# Issue128 — bounded real target comparison

**Decision now: prioritize #131's reduction of real MariaDB internal contacts;
do not advance product adoption on this comparison. Total update burden is
INCONCLUSIVE.** Both paths still need the three shared repairs and exact binding
review, and an additional archive-to-capture regression remains unresolved. The
strongest contrary evidence is favorable to native: both clean producers and
the original finite native suite pass without any new native C++ repair, and
the version update changes its reviewed worker bodies only by static relocation.
That keeps native viable, but does not demonstrate lower total maintenance cost.

The authorized run **stopped at the first unresolved additional semantic
failure**. Builds and original suites are not relabeled failures; the additional
regression is not relabeled PASS. This is not completion of #128, public C3,
adoption, main integration or release. No further build/runtime/CI was started
after the failure. The initial source-only result at `dbf269e3` remains unchanged.

## Exact sources and fresh producers

Engine: MariaDB13.0.2, source_commit
`620a4b5624222048fece7fe1789978ae0675cae2`, annotated tag_object_sha
`308a50778fb4916ddde0d2923feea3d11dcc92c8`, rechecked before compilation with
`scripts/git_identity.py`. [Identity](evidence/target-git-identity.json).

| Route | Actual mariamem producer source_commit | Guest SHA256 |
| --- | --- | --- |
| Legacy, with the shared prepared UCA base | `ecf81035009bd4e353ddee302f73c781c77a3f28` | `1854c8106abf275e67c84b6e43a6035109021d81d3612f54d0f17baa31906214` |
| Native, #127 bootstrap separation retained | `e6502de0781826488c984aa5637dfe593a74799d` | `b7672dcca277ec9a1294b82ec33ab68cab578ba6244c81dc31ffe37586e0486d` |

Legacy guest overlays derive from published source `47121e1b`; bringing that
guest onto the same prepared UCA input is **shared baseline setup**, not a native
benefit. Native's experimental patch is byte-identical to origin `8c8b5f1c`.
Older native `be244a0b` is a historical source comparison input, not a third build.
Neither new producer is presented as a binary built at one of those old SHAs.

Both are successful **single fresh canonical development invocations**: empty
work tree, absent SDK, absent prepared source/unpack at entry, followed by full
preparation, allocator contract, compile/link and postoptimization. There was no
incremental continuation. The receipts explicitly set
`fresh_canonical_builder_success=true` and `fresh_target_producer_success=true`;
this was checked separately from `verify_guest`, which does not enforce freshness.
Fresh prepared inventories contain31,014/31,023 files respectively, saved before
compilation. [Legacy producer](evidence/legacy/producer-result.json),
[native producer](evidence/native/producer-result.json),
[legacy preflight](evidence/legacy/preflight.json),
[native preflight](evidence/native/preflight.json).

Both guest producers ran Linux arm64 with identical verified archive hashes,
LLVM23.1.0, WASIXCC0.4.7, both EH sysroots, Binaryen133 and tool versions. Exact
toolchain records, shared portability series/source overlay, UCA provenance and
routine provenance were compared and are equal. Runtime execution was macOS
arm64 with Go1.26.10. Source is acquired from pinned public inputs; no historical
Orca checkout or warmed SDK is required. Reusing this run's verified downloads
for the second fresh SDK is acquisition reuse, not a native speedup.

Linked WASM SHA256: legacy `1ba5aaa0451df93b7f900fa6c38b5b3844e5a4bedd493cfc379adc56d21d4195`,
native `2e0c205de8c0e43f30810cb52990db64e92a1c19ed140376799083c74c25194d`.
Guest sizes21,215,058/21,237,000 bytes are identities, not a size/performance
claim. [Full guest records](evidence/legacy/guest.json),
[native record](evidence/native/guest.json).

## What was changed and guarded

Full acquisition included actual server, recipe, Connector/C, wolfSSL, PCRE2 and
fmt archives, with checksum checks and local vendoring. The four shared patch
stages have complete before/after file identities (17,1,3,3 entries), and the
target source overlay and native20-file overlay also have complete identities.
The original function-body, UCA numeric/header, routine DDL/metadata, allocator
and source-anchor expectations were retained. [Dependency acquisition](evidence/dependency-acquisition.json),
[full preparation](evidence/full-preparation.json),
[target guard rejection checks](evidence/target-guard-checks.json).

The only functional shared source repairs are the three already reviewed in
the initial slice: the moved redo `mprotect`, the prepared adapter's correct
EOF insertion, and the sync-LSN wait recheck retaining the target's
`timed_wait/create_spare_archive` control flow. No new functional native patch
repair, decoder change, weaker capture gate or second host parameter decoder
was added. Complete target pinning is real preparation work; patch success
alone is not its acceptance.

`guest/source.patch` remains unchanged. Dedicated trial source text is in
`inputs/shared-source.patch`; the experiment branch's preparation registration
selects it with exact full-file pre/postimages. Source acquisition and UCA/routine
pins are explicitly updated to13.0.2. Native remains `guest/experimental.patch`
and release provenance still rejects experiments. The canonical generated guest,
release eligibility/provenance checks and `release/generated-go-*` identities
were not rewritten to accept these UNQUALIFIED bytes. These target registrations
are experiment changes, not a merge-ready product upgrade.

## Binding and finite verification

New exact worker function bindings were reviewed for each guest. Discovery may
normalize shapes, but validation compares the **whole body** after enumerated
function/address mappings; small constants, offsets and instructions must match.
Both retain ABI16/40/44. Legacy roles remain Fn153/Fn131/Fn214, TLS505 bytes,
with recorded static relocation15,296 from its reference. Native roles remain
Fn151/Fn129/Fn520, TLS489 bytes. Its direct comparison with #127's saved bodies
requires only static relocation15,360; no small constant, TLS-size or layout
change. The new exact normalized body hashes and no-op table-entry proof are
saved, rather than copying a binding from #127.
[Legacy binding](evidence/legacy/runtime/reviewed-binding/identity.json),
[native binding](evidence/native/runtime/reviewed-binding/identity.json),
[incremental #127 comparison](evidence/native/runtime/incremental127-binding-review.json).

| Actual execution | Result and scope |
| --- | --- |
| Legacy original dev-guest smoke | 1 PASS,0 skips: fresh SQL, InnoDB writes, commit/rollback, Snapshot, three independent Forks and shared-host/close ownership checks. |
| Legacy original P1 and P2 repair probes | Six P1 checks and all15 P2 repair scenarios PASS. Recorded PREPARE metadata and complete comparable P2 traces also match the unchanged original native-control fixtures. This offline comparison is not a freshly executed standalone13.0.2 native control. |
| Native original suite | **79/79 original Go cases PASS; FAIL0/SKIP0**, including original22 lifecycle coverage, and all88compat/38limits/G1234/G2241 named observations PASS. All79 test names equal the #127 reference; the raw suite was executed, not synthesized from components. |
| Additional native target regression | **FAIL** at capture precondition `1: busy`; capture/restore after archive stress is unverified. This separate test is not included in the79/701 PASS claim. |

The old prepared observers assert a12.3.3 version prefix. Their first target
execution rejected the actual `13.0.2-MariaDB-embedded`. Only that identity check
was rebound, to exact equality with the target string; all protocol/type/error/
schema expectations stay unchanged. Original failure logs and both fixture
hashes are retained. The original G2's already approved1043 handshake adaptation
is unchanged. G2 was included before the one native host compilation; no extra
baseline test-binary build was used.
[Legacy semantic result](evidence/legacy/runtime/semantic-result.json),
[original control comparison](evidence/legacy/runtime/original-control-comparison.json),
[observer rebind](evidence/legacy/runtime/prepared-observer-rebind.json),
[native raw suite](evidence/native/runtime/native-suite.txt),
[native accounting](evidence/native/runtime/native-result.json).

Legacy uses the canonical legacy route in the fixed #127-derived host source;
native uses the existing isolated P1-b/#127 templates. Those are different
verification surfaces, with the same target engine/base, not equal public
consumer programs. No execution evidence is claimed for public integration
`fd7aea91`, C3 precision/fault settings, Linux runtime or both-platform adoption.

## First unresolved failure and its limits

The additional bounded test sets archive ON with configured log size4MiB,
writes256 committed64KiB rows, then sets archive OFF. Actual observations:

- LSN36,889 →16,947,841; last checkpoint16,960,243.
- Row count256 and total payload16,777,216 bytes match before capture.
- `SESSION_RETIRED result=0 decodes=256` is logged.
- Capture returns `consumed=false`, no root, `capture precondition1: busy`.
- Ordinary stop reports started1/joined1/cleanup_failed0.

This exercises real redo/checkpoint/archive transitions beyond source application,
but **does not prove the exact internal pending-archive wait branch was hit**.
The post-stress capture/restore is not completed. The run stopped here, without
retries, guard relaxation or an engine repair. [Raw failure](evidence/native/runtime/target-checkpoint.txt),
[failed result](evidence/native/runtime/target-checkpoint-result.json),
[exact probe source](target_checkpoint_test.go.txt).

Read-only source inspection points to an important alternative explanation:
`tryCapture` rejects any non-IDLE native slot under its gate; the helper `idle`
only observes a point-in-time idle state. `db.Close` and a later native QUIT/EOF
retirement can cross that observation. The original public smoke explicitly
waits for disconnection before snapshot. Thus an insufficient drain precondition
in the new probe is plausible; **we have not established a13.0.2 engine/native
regression, nor proved it is only an observer problem**. No comparison of this
extra archive scenario on legacy was executed. Do not count this failure as a
measured native-specific repair cost.

## Costs, budgets and next bounded work

Measured command/wait durations, not benchmarks or human active time:

| Stage | Legacy | Native |
| --- | --- | --- |
| Fresh producer, including acquisition/SDK/preparation/build/postopt | 1115.91s | 886.02s |
| Converter + translation command | 100.22s | 118.82s |
| Source adapter | 18.19s | 19.66s |
| Checked installer | 20.67s | 19.91s |
| Host compilation | 147.62s | 232.12s |

Do not infer a native speedup from producer totals: the first downloads are
shared setup, and caches/file-system state differ. Host verification programs
also differ. Native's traced compile/link is527.26s and postopt13.84s; the first
producer did not enable per-phase tracing, so an equally precise legacy split
is unavailable. Native original suite's saved file-write window is43.38s, not
exact process wall time; the extra test reports failure after1.09s.
[Native producer phases](evidence/native/phases.jsonl),
[legacy host phases](evidence/legacy/runtime/host-phases.jsonl),
[native host phases](evidence/native/runtime/host-phases.jsonl),
[runtime windows](evidence/native/runtime-windows.json).

Manual investigation and tooling estimates are recorded separately in
`evidence/timing.json`; they are estimates, not stopwatch measurements. Functional
repair is shared; native's additional full patch pinning and fixture assembly
are separate from the shared UCA baseline and reusable measurement tooling.
New native C++ functional repairs:0. Build/link failures:0. Initial operational
failures (inherited GOPATH, missing pytest and obsolete observer version) are
preserved and are not engine regressions. No CI, benchmark or consumer expansion.

Producer guards count all owned Docker mounts: SDK/root, work, repository build,
downloads, temporary files and output. Sampled producer peaks were5.19/5.43GiB,
minimum free16.60/14.72GiB respectively, with12GiB ceiling/floor. There is an
accounting limitation: the first legacy Go translation/host stage used system
temporary storage outside the owned-path counter, while the whole-filesystem
free-floor guard remained active. The combined observer attached after that
compiler exited, so its empty/zero sample record is **not a measured zero peak**.
We cannot claim continuous complete owned-byte accounting for that first Go
stage. Subsequent Go/runtime stages explicitly use owned TMPDIR/GOTMPDIR. No
budget breach was observed; this limitation remains reported rather than hidden.

The practical result is **source/preparation parity with no demonstrated total
update-cost reduction**. Both need shared repairs and binding review; the native
patch applies and builds unchanged but retains internal Item/THD/Protocol and
prepared-repair obligations. Different finite suites, the capture observation
and the accounting gap preclude a convincing normalized total-cost judgment.
This supports #131's contact/placement reconsideration, not automatic later
productization or rejection of native execution altogether.

Remaining #128 conditions: close the archive/drain-to-capture question without
weakening busy/ownership gates, compare the same scenario on both routes, then
check only changed boundaries of the eventual #131/#134/#135 candidate. A useful
next bounded option is30–45min active including at most10min tooling, one fresh
target guest plus one translation/host build (about30–45min wall on this setup),
0CI, to bind explicit full retirement/drain and capture observations. A paired
legacy archive comparison would need its own additional producer/host slot;
agree that scope and cost first. These are new proposed costs, **not approval**
to spend additional builds. Prefer combining the paired verification with the
final contact-reduced candidate instead of rebuilding throwaway baselines merely
to repair an observer. No12.3.3 rebuild is made a prerequisite.

## Reproduction and cleanup

Use a clean public-source checkout at **each actual producer SHA above**, checked
with `scripts/git_identity.py`; do not replay old receipts on final report HEAD.
The initial source-only recipe belongs to immutable `dbf269e3`, not these new
target source locks. For each fresh Linux arm64 producer, create empty owned
`root`, `work`, `output`, `tmp`, `repo-build` directories and copy the tracked
`build/go.mod` into `repo-build`. Mount the source read-only as `/repo`, all owned
storage as `/owned`, and the five owned directories as `/root`, `/work`, `/output`,
`/tmp`, `/repo/build`; optional verified downloads may be separately mounted at
`/repo/build/downloads`. With a normal clone use `GIT_DIR=/repo/.git`,
`GIT_WORK_TREE=/repo`, `GIT_OPTIONAL_LOCKS=0` and trusted `/repo` Git configuration.
Invoke `python3 /repo/benchmarks/spikes/issue128-real/guard_builder.py` in the
Linux environment. It calls the unchanged canonical development builder with
fresh `/output/artifact`, enforces3600s and12GiB/floor12GiB, and records actual
fresh success. The initial Docker environment was `mariamem-wasix-build:0.4.7`;
the exact locked SDK is acquired afresh and does not use that image's LLVM21 SDK.

For host reproduction use an ordinary clean source copy at the matching producer
SHA in an owned workspace prepared by `experiment_workspace.py prepare` without
creating another worker/worktree. The retained `legacy_driver.py.txt`,
`native_driver.py.txt` and `review_binding.py.txt` are copied into owned temp and
run from the owner checkout as in their paths. Use the pinned Python3.14 venv
dependencies in `evidence/python-dependencies.json`. Recreate the exact target
version observer copies using the two single-line substitutions documented in
the rebind receipt. Translation → exact binding review → one host compile →
finite test runs all use the recorded original fixtures and target hashes.
For the additional native regression, place `target_checkpoint_test.go.txt` in
owned temp before assembly. Its first failure is part of the expected evidence,
not a successful acceptance recipe. The original G2 is staged before the sole
native host compilation, as recorded by its assembler adaptation receipt.

All executable/generated/download/cache/source staging is disposable after
compact evidence is saved. The evidence retains input and artifact identities,
full prepared inventories, exact reviewed bodies/maps, commands/phase records,
original failures and reproducer source. Path normalization has raw/normalized
hash sidecars. Read-only Go module-cache permissions were changed only inside
inactive owned cache paths to complete deletion. No shared image/cache, other
workspace or the parent's four pre-existing files was modified. Cleanup,
checksums, source-boundary verification and all retained>1GiB paths are reported
in the final sidecars. Orca/coordinator owns the worker workspace lifecycle.

## Authorized plan, recorded before preparation/build (2026-11-08)

Question: on the same MariaDB13.0.2 engine/prepared UCA base, do native's total
update investigation, patching, generation/binding and semantic verification
costs improve on legacy? Human authorized this follow-up in
[the review](https://github.com/masahitojp/mariamem/issues/65#issuecomment-6717727942).
Initial source-only evidence at `dbf269e38d64e93862bcd5f736876ae5745b7a8b`
remains immutable. This report owns new outcomes, including failures.

Inputs: base127 `46915e50c12795da4787c9d1ee0b73e6c6a829dc`; native guest origin
`8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`, older native
`be244a0bdb510a22417241c2aa2f76a9093aac1b`, legacy source
`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`. Target source_commit
`620a4b5624222048fece7fe1789978ae0675cae2`, annotated tag_object_sha
`308a50778fb4916ddde0d2923feea3d11dcc92c8`. Recheck Git identity before builds.

Workload: full pinned dependency acquisition and exact full pre/postimage
preparation; at most one fresh clean guest build per variant, sequentially;
regenerated Go and exact new worker/TLS/layout binding review; finite affected
common checks and native22 lifecycle/88compat/38limits/G1234/G2241 where runnable.
Preserve original semantics and expectations, label unavailable fixtures, and
do not turn isolated evidence into public C3/platform/adoption acceptance.
Published legacy's missing prepared UCA is shared baseline setup, not a native
benefit. Use identical locked compiler/sysroots/Binaryen/converter/platform.

Budget: **2h active including30min tooling;4h30min total wall;CI0**. At most2
clean guest builds, each60min timeout, at most2 translation/host builds each30min,
finite suites each30min; no benchmarks or consumer expansion. Stop at the first
unresolved shared/semantic failure or budget breach, preserve evidence, clean
owned scratch and report the missing evidence and bounded next cost. Repair
only the already understood three shared adaptations within this budget.

Disk: **12GiB total owned ceiling;12GiB minimum free**, guarding preparation
and run. Initial host free space approximately20GiB, with no observed active
guest/compiler build. Count all owned host/container SDK, downloads, caches,
work, logs and output under `build/issue128-real/temp`; do not delete shared
images/cache or any other checkout. Use a fresh SDK/work tree per clean build,
explicit fresh-producer assertions and raw builder status; incremental success
cannot be called clean. Existing image is an environment, not a warmed SDK input.

Exit: improved/worse/inconclusive total update burden, with actual sources and
artifact digests, reproduction commands, manual/tooling estimates and command
wait durations separated. Inconclusive or unfavorable evidence must not trigger
automatic productization; recommend internal-contact reduction/placement
reconsideration for131 if no convincing benefit. Final128 still needs comparison
against final adoption-candidate differences. No main integration/release change.
