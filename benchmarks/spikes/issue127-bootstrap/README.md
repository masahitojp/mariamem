# Issue127 — bootstrap separation spike

Decision now: carry this isolated candidate into **#128's real MariaDB update
comparison**. I recommend continuing: the native build can exclude the legacy
resident/prepared entry and JSON exports while preserving bootstrap and the
existing finite native oracles. The strongest objection is material: preparation
still applies the same upstream prepared patch, and changing link roots required
manual worker-binding review. **Lower total MariaDB update cost is unproved**;
this is neither an adoption recommendation nor completion of parent #65.

## Result and identity

Base `source_commit`: `a5ee1ed9cc2c6932d317fba77c339b364acd48df`, matching local
`experiment/issue65-bootstrap-reachability`, checked before edits with
`scripts/git_identity.py`. Work is on `experiment/issue127-bootstrap-spike`.
Corrected guest/host fixture origin:
`8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`.
UNQUALIFIED guest SHA256:
`873c9daf38f6e7f5005dbdbdf8e920b396fe5591ab74bfedcad37b436c50d3dc`.

The initial fresh canonical development builder failed at controller compilation
at `dd33d84e6ca50f18b762450a341b90efbf4c11a0`: removing `mysql.h` also removed
live `mysql_thread_init/end` and `COM_QUIT` declarations. The corrected candidate
retains that shared header. The same build continued incrementally: **30,877
freshly prepared source files matched the compiled tree, and all 859 pre-existing
object hashes remained unchanged**. Only the corrected controller compiled;
link/postoptimization succeeded with the locked tools and unchanged build recipe.
This is **not a successful fresh invocation of the corrected canonical builder**.
[First failure](evidence/first-build-failure.txt),
[complete development guest record](evidence/guest.json),
[prepared inventory](evidence/prepared-source-files.json).

Native macOS arm64 executes **79/79 original Go cases**, no skip/failure, and
**701 named observations**: compatibility 88, limits 38, G1 234, G2 241, all PASS,
no mismatch/missing. This includes fresh/restore and invalid restore, routine
CALL/result chains, text/prepared execution, ordinary/fatal stop, capture/debt,
ownership and profile3 timeout cases. The approved 1043 handshake adaptation is
unchanged; no oracle or decoder repair is included.
[Raw execution](evidence/native-suite.txt), [result](evidence/native-result.json).
The combined log initially confused a suite-specific accounting helper because
several suites share its marker. Existing analyzers pass after splitting the
**unchanged** log by top-level test group; this is accounting repair, not a new
runtime execution or changed expectation.
[Accounting record](evidence/accounting-repair.json).

## What actually separates

| Surface | Candidate / remaining dependency |
| --- | --- |
| `g_mysql`, `g_open`, `ensure_dir`, `l4m_open/close` | Retained; complete open/close and native bootstrap/shutdown bodies unchanged. Embedded text API is still required. |
| `startup_timing.inc` → `init_diagnostics.inc` | Retained, including FS/allocator/pthread wrappers. |
| `routine_bootstrap.inc` → generated routine schema | Retained for fresh creation and restore validation; no restore shortcut. |
| `prepared_auth_keys.inc` → generated test key header | Retained for required auth setup. |
| `wire_api.inc` → wire core / prepared API / resident | Excluded from native compilation by `MARIAMEM_BOOTSTRAP_ONLY`. |
| Resident's `snapshot_fs.inc`, slots/workers and typed envelope | Excluded from native compilation. |
| Controller dead connect/query/embedded-prepared examples | Removed, along with its routine include; `mysql.h` remains for live thread/command declarations. |
| Seven `l4m_*` linker exports | Removed. `malloc/free` exports remain. |
| Native Manager, frame/session/capture code | Complete bodies unchanged, with original decoder/ownership gates preserved. |

The actual compiler dependency files confirm the bootstrap/auth/diagnostic
includes and exclusion of resident/prepared/wire/snapshot includes.
[Dependencies](evidence/compiler-dependencies.json).
Only three of the 61 prepared-file hashes differ from the base: CMake selection,
bootstrap glue and controller cleanup. Engine files, canonical `source.patch`,
existing prepared patch, input lock and preparation script stay fixed.
[Comparison](evidence/prepared-comparison.json),
[source check](evidence/source-check-corrected.json).

The linked module has 32,103 named functions and no legacy `ps_call`,
`ps_dispatch`, `ps_prepare`, `ps_execute`, resident worker/old main or old JSON
query names. Both linked and optimized modules have no `l4m_*` exports. Bootstrap
`l4m_open` remains internal. The native shared upstream
`mysql_stmt_execute_common` remains; this is not removal of MariaDB prepared
execution. Linked/optimized sizes are 24,656,745 / 21,181,659 bytes; no old binary
was rebuilt for a size/performance comparison.
[Linked inventory](evidence/linked-inventory.json),
[optimized inventory](evidence/guest-inventory.json).

## Binding cost and preserved ABI

The supported development installer accepts a newly reviewed exact binding;
canonical binding/guards are unchanged. Binding SHA256:
`35fb98fda9d89c0a6010b32f6be63446d2684b73d69837322fd905e3aeb478f0`. New roles: free **Fn151**, yield **Fn129**,
entry **Fn520**, with offsets **16/40/44** unchanged. Entire bodies match after
recorded function/address relocations, TLS-copy length and one no-op destructor
function-table relocation. All other small constants, offsets and instructions
remain fixed. The raw new bodies/hashes are saved in [binding](binding/identity.json).

TLS initialization is 489 bytes (previous P1-b 497, canonical reference 505).
The table pointer changes from 12 to 94; both entries resolve to identical no-op
bodies after rename. Entry static addresses relocate in four explicitly pinned
regions rather than the former review helper's single-delta assumption. The
review records every address mapping and checks alignment/injectivity, plus
whole-body equality. These are reviewed changes, not blanket numeric masking.
[Review notes](evidence/binding-review-notes.json).
This additional investigation and rebinding is an observed maintenance cost, not a
benefit inferred from fewer bridge lines.

The separate existing `TestWireCaptureWaitsForFailedWorkerPeer` check also passes
in the staged host. It is focused adapter/ownership evidence, not an additional
real-guest execution or broad production index-bound qualification.
[Focused check](evidence/runtime-peer.txt).

## Budget, environment and failures

The question, finite evidence/exit and inconclusive exit were recorded in this
plan before investigation. Initial ceilings: active 2h, measurement tooling
30min within it, **heavy CI 0**, one candidate/full engine compilation with an
ordinary incremental header correction. macOS arm64 observer uses Python3.14;
the native Linux arm64 Docker producer uses locked LLVM23, WASIX SDK/sysroots and
Binaryen. The existing image's LLVM21 was not used as the guest compiler.

Before building: **12GiB free floor / 12GiB owned ceiling**, 60min build timeout;
preparation 15min. The initial owned sample was 0.12GiB with 20.64GiB free; an
observed later sample was about 6GiB owned. These are samples, not a measured
exact peak. The first SDK mount failed freshness preflight before compilation.
The fresh compile's real header error is preserved above.

A host filesystem stat error interrupted the first continuation guard. Docker
outlived the host CLI group; the owned container was explicitly stopped and
inactivity confirmed. The unchanged guard then ran inside the container on the
verified host-backed build filesystem, with the same floor/ceiling and timeout.
No guard/source patch was relaxed. [Guard failure](evidence/host-guard-failure.txt).
The failed raw builder is not relabeled PASS; `guest.json` explicitly records
`fresh_canonical_builder_success=false` and the incremental method.

Python tooling compilation and diff checks pass. Full public-source validation
still finds the six unchanged historical P1 evidence files already handled by
#133's separate branch; no historical result is rewritten here. This branch does
not adopt that other branch or claim full public qualification.

## Handoff and remaining conditions

- **#128:** select and actually try another MariaDB version; record patch/binding
  repair, investigation, generation, build and verification work. The complete
  existing prepared patch still applies: TIME width, embedded unsigned flags,
  dynamic result metadata, parameter metadata helpers and old type handling.
  Native conversion rollback still depends on internal Item_param/prepared
  layouts. Removal of those patches is not established by this spike. Fixed-base
  spike observers are not new prerequisites for arbitrary upstream versions;
  their adaptation cost must be distinguished from runtime repair.
- **#129/#130/#131:** no public factory/core change is made. Source preserves
  frame33, profile3 positive nanoseconds, 16 slots, epoch/slot/generation,
  INSPECT9→REPLY102 timeout values and ABI16/40/44. Their new settings/lifetime
  fixtures were not run. C2's old guest/origin/binding pins and source preimages
  must be explicitly rebound to this candidate using a fresh producer receipt;
  copying/relabeling old C2 receipts would be invalid.
- **#132/#134:** fresh corrected full-source build, same-candidate public routes,
  supported-platform repetition and formal generation remain. One fresh producer
  plus translation/host compilation is concrete remaining work: the observed
  full compile/tool acquisition took about 20min, continuation about 5min and
  native host compilation about 5min on this setup; these are planning evidence,
  not a promised clean-rebuild time or a new approved budget.
- No C2 `public-source.json`, raw public-binary receipt, wheel or installed Python
  consumer is produced. Saved guest/source/binding/native manifests are compact
  evidence; they are not substitutes for the complete guest/linked/translation
  bundle that a future C2 producer must rebuild and authenticate. Performance,
  integration, adoption and release remain separate.

## Reproduction and storage

Use exact guest origin `8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3` and verify it
with `scripts/git_identity.py`. On a fresh root Linux arm64 builder, empty `/work`,
absent SDK and external `/output`, `build_checked_guest.py` invokes the unchanged
canonical development builder and checks prepared source. It is the preferred
future clean-rebuild route; a fresh PASS/hash match has not been observed here.
`resume_checked_guest.py` preserves the actual historical incremental method.

The `runtime_driver.py.txt`, `review_binding.py.txt`, `wasm_inventory.py.txt` and
`account_completed_run.py.txt` files preserve task tooling. Copy runtime tools to
`build/issue127/` so their relative owner-root calculation matches the observed
layout. Prepare an owned `runtime` workspace there, place an exact clean source
copy at `runtime/worktree`, and the complete guest bundle at
`build/issue127/output/artifact`. Translate with the driver; reuse the committed
873c9daf binding (new bytes require separate review), compile, then run its finite
test stage. The standalone accounting script reproduces the repair over the
saved combined raw execution. Operational paths are reconstructed; normalized
sidecars are explicitly **not raw C2 receipts**.

Builder source/SDK/download scratch has been disposed after preserving inputs,
hashes and diagnostics. [Builder cleanup](evidence/builder-cleanup.json).
Runtime scratch cleanup is pending final evidence checkpoint; the Orca worktree
and its lifecycle remain with the coordinator.
