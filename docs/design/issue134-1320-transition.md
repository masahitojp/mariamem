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

## Result,2026-11-10

Continue the formal producer/binding/public handoff on the verified13.2.0 input.
The decisive evidence is actual shared preparation without patch-body repairs,
while retaining all old version entries and exact source checks. The strongest
objection remains the untested generated binding and runtime behavior at14
changed upstream contact files. Source patch application does not resolve that
risk; the planned formal cohort must do so before adoption.

Implementation/preparation source_commit:
`ad7fbe2572331bc4aa10838fa8b9434d051a4a5f`.
Upstream source_commit:`c9f28ba0afec6d29e4688255dce8caaf7e91233d`.
The published source tar records that revision; all27,551 tracked Git blobs
match its contents, with no missing or different blob. Bundled submodule and
generated extras are counted separately. The official tar SHA256 is
`5b6a588e86f1169fef44760846b6e9e96b08d7a7e52fb4b887c5feb06ca39f3a`.
No matching annotated release tag was observed; tag_object_sha is null. The
Preview descriptor has an explicit schema requiring the published archive and
revision evidence, while old tagged descriptors retain their original checks.

The common pipeline uses the exact-commit Git archive plus the existing reviewed
dependency lock, rather than importing the distribution's bundled dependencies.
All seven patch bodies are reused byte-for-byte. Fourteen complete source files
changed upstream and their pre/postimages were rebound from actual application.
The native unchanged C API function expectations pass. Routine SQL and Unicode/
UCA numeric source are byte-identical; m_ctype.h changes are comments and new
unrelated str2int templates. The exact rendered UCA header remains checked.
Actual common preparation including profile/TIME/UCA/DDL/hooks/vendor checks
passes.32 resolver/context/preview tests pass; a first overly broad unittest
selection also collected a pytest-only module unavailable in that interpreter.
The corrected focused unittest selection is the reported32-test run.

The incremental recurring cost observed here is metadata/source-proof review;
patch-body repairs were0. A one-time untagged-preview identity representation was
needed. No new version-specific branch was added to preparation. This is favorable
source-maintenance evidence, not a human-hours or total-cost victory: the14 source
contacts, fresh generated worker bodies/TLS/ABI and public behavior still need
checking. No guest/Go build, runtime suite, CI or performance run was performed.
#138 remains stopped and unwaived.13.0.2 historical results are not13.2 results.

[Machine results](issue134-1320/evidence/result.json),
[distribution-to-Git comparison](issue134-1320/evidence/distribution-source-comparison.json),
[actual preparation receipt](issue134-1320/evidence/prepared-source.json).

Reproduce source contact/distribution checks with the pinned upstream Git object,
the published SHA256-checked archive, and fresh owned paths:

```sh
python3 docs/design/issue134-1320/probe.py --upstream <upstream-git> \
  --output <fresh-source> --downloads <owned-downloads> --evidence <evidence> \
  --published-archive <mariadb-13.2.0.tar.gz>
python3 scripts/prepare_guest.py --engine 13.2.0 --profile native-text \
  --work-dir <fresh-run> --archive-cache <owned-downloads>
```

The prepared result is evaluation-only and release-ineligible. Source identity,
producer receipt, translation and exact binding must be wired together before
running the single planned formal/public cohort. Full13.3 LTS adoption will use
its actual released source and repeat the affected verification; it is not
pre-approved by this Preview result.

The final input identity also includes the published-preview provenance itself.
A focused negative check verifies that changing the publication hash changes
resolved identity. Source preparation was repeated after that identity change;
all32,835 prepared members have the same complete tree hash. This follow-up
changed no patch/body or runtime behavior.
