# Issue134: 13.3 LTS direction and 13.2.0 evaluation input

Human direction,2026-11-09: intended next13-series product adoption is13.3 LTS.
Use13.2.0 (or the nearest verified13.2 source) to evaluate the common upgrade
path before formal generation/binding/public acceptance. Published12.3.3 remains
the stable reference;13.0.2 inputs and evidence remain historical comparison
vectors, not the next intended product engine. No13.3 binary is approved here.

Question: can the existing registered preparation handle the nearer13.2 source,
and which real patch/proof/producer edits remain before the formal cohort?
Contribution: measure adding another upstream version without replacing the
previous engine's scripts or disguising metadata-only PASS as net savings.
Base source_commit5af5b78690d14cdf11ab28ee058ea76bc2416407;
branch experiment/issue134-1320-input.

First establish published archive/source-commit identity; retain tag_object_sha
only for a real annotated tag. Do not manufacture one from a branch SHA. Then
compare affected source/patch/proof inputs; preserve exact images and contracts.
If the target identity or a semantic repair cannot be established, report that
boundary and the concrete remaining work; continue version-independent formal
producer planning. No speculative controller relocation or#138 restart.

Budget: initial active2h, tooling30min, heavyCI0; source scratch6GiB/freefloor12GiB,
source preparation wall60min if identity resolves. No guest/Go build before the
new source and shared formal producer/binding plan are fixed. Preserve compact
source identities/diff findings, commit/push, delete owned downloads/trees and
worktree. Unrelated user changes are preserved.

Primary sources checked:
- https://mariadb.org/about/ (13.3 LTS roadmap)
- https://mariadb.org/mariadb/all-releases/ (13.2.0 Preview,2026-09-23)
- https://jira.mariadb.org/browse/MDEV-41087 (preview-13.2-preview preparation)

## Formal producer handoff after target preparation

The next cohort must use the13.2 evaluation source and the shared input path;
do not pay for a new13.0.2 public producer solely to later replace its engine.
Old13.0.2 results remain source/runtime reference evidence, never13.2 PASS.

| Boundary | Required change and retained detector |
| --- | --- |
| Producer invocation (`build_generated_guest.py`) | Pass a registered selection and fresh run directory into common preparation. Keep one fresh producer/SDK environment, exact archive and compiler pins, allocator checks, canonical-builder success, independent regeneration requirements. Stable default remains12.3.3. |
| Prepared/guest receipt (`dev_guest.verify_guest`) | Distinguish selected receipt from the legacy contract explicitly; bind resolved input, effective lock, every selected overlay/proof and actual producer inventory. Reject missing/unknown schema, mixed version/profile, modified source and stale artifacts. No optional fallback to root lock or an old guest. |
| Translation/install (`dev_guest.py`, `generate_runtime.py`) | Carry actual guest/translation/module hashes, review whole worker bodies and TLS/ABI. Existing13.0.2 function numbers/addresses are discovery hints only; they are never accepted as13.2 binding. |
| Public source composition (#132/#129/#130) | Reuse f4507b5's254-item source inventory and fd7 fixture ownership map. Compose the host/factory/lifetime/configuration/failure fixtures with the selected producer before one public cohort. Update only engine-version assertions justified by the actual new source; keep oracle semantics. |
| Cost (#128) | Record descriptor/proof edits, semantic patches, binding review and machine wait as separate costs in that same cohort. Adding a second evaluation version is evidence about the common mechanism; don't infer13.3 compatibility from it. |

Before invoking a heavy producer, fix source_commit, archive identity, complete
ordered patch/proof inputs, actual producer commit, required outputs and budget.
#138 remains stopped/unwaived; no new archive branch probe is introduced here.
Candidate adoption and13.3 LTS release qualification remain separate decisions.
