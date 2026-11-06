# Prepared UCA integration preparation

The Human adopted the bounded candidate on2026-11-05; the
[decision](../decisions/prepared-uca-tables.md) records scope and the measured
tradeoff. Protected main integration is prepared; no main merge or release is
claimed. Current main0c4e75dc is included, preserving the published0.6.2 guide
reconciliation and CI path selector. Its single status-file conflict was resolved
with the current published-release record and a new adopted/pending section.

[Byte-equivalence proof](uca-prepared-integration-equivalence.json) compares the
working candidate to CI source `cbd25f027e804bbd529a85208589ba2dd2899b86`:
all Go runtime/root API, guest source, Python package, maintained numeric inputs,
source preparation/generation scripts and input/translation/toolchain pins are
unchanged. The only script delta is the already-main CI selector. Fixture and
canonical ledger changes are acceptance labels/actual CI attestation, leaving
expected bytes, functions, offsets and TLS unchanged. Receipt member hashes pass.
No compiled host-binary identity is equated across source commits.

The canonical ledger now records the actual two-build result and sourceCBD,
preserving the incoming UNQUALIFIED275c1807 origin and the authoring ledger hash.
The original CI41961766293 guest/build/native records are not edited. Both current
binding status labels point to that source-bound acceptance. Historical reviews
remain historical. No prior run is a new-head Qualification PASS.

Automatic push runs of the accepted one-off candidate workflow are retired.
Its manual reproduction and all jobs, commands, permissions and failure oracles
are byte/structure-equal. Normal PR checks and the Release workflow are unchanged.
This prevents two redundant C builds for acceptance-record changes without
skipping a required check or changing repository protection.

Validation here is JSON status-field/evidence comparison, runtime-source and
receipt checksums, workflow job comparison/YAML parsing, public-source and clean
diff checks. Runtime was not rebuilt or benchmarked again. Next: normal app-bound
`check`, `integration`, `Live required gate` on the exact integration head, strict
base and the separate main-merge decision. Version/publication remain separate.


## 2026-11-07 integration follow-up

The Human authorized protected main integration. Development run41969231695
failed `test_every_maintained_workflow_has_an_explicit_reviewed_scope`: the
manual-only uca-canonical workflow was absent from WORKFLOW_SCOPES. Its
classification is now explicitly python/tooling, consistent with the other
workflow definitions; changing guest/runtime inputs still selects the full
profile. The inventory test and all required checks remain intact. This changes
only CI-selection metadata and decision/status documentation. Canonical runtime,
guest, preparation/generation and pinned inputs remain at the accepted bytes;
no source build or timing repetition is justified by this correction.

Focused CI-selection/efficiency tests:115 PASS. Accepted runtime/guest/input
byte-equivalence check PASS; public-source and whitespace checks PASS.
