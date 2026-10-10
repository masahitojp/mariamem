# v0.4.6 integration preparation — approved scope

Approved evidence/source candidate: `2432abd5439d8daa2ead9676c8c2561ad807b280`.
Current main baseline: `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb`.
This branch preserves the accepted candidate and records the PO approval.
It does not merge main, bump version, create tags, dispatch release CI or publish.

## Auditable integration units

- `f13543f4868132f969516f2af3b805cbcb6bb0ae`: public Go LoadSnapshot wrapper,
  focused ownership/lifecycle tests and public-source inclusion.
- `59bdb987471d23090f2b29e9b3b75a35af265660`: accepted language guides, scenario/type
  probes, executable examples and bounded product benchmark adapter.
- `5824ed1f205c84fc67574d6896afba412b57188b` /
  `ff43ffef6ded67b3f37079831acc9f8e5bad8226`: measurement-only harness fixes.
- `2432abd5439d8daa2ead9676c8c2561ad807b280`: compact evidence, compatibility and review.

Only snapshot.go changes production API behavior: 31-line wrapper around existing
OwnedPrepared import. Generated source, runtime, guest, mmap, Snapshot format,
Python SDK, minimum Go1.26.0 and mysql v1.9.3 are unchanged.
Benchmark instrumentation must not be confused with runtime changes.
The new Go1.26/1.27 performance diagnostic instrumentation is not on this branch.

## Verification and later steps

Reuse accepted exact-source API/scenario/docs/type evidence; this approval/preparation
commit changes documentation only. Run canonical docs/public-boundary and diff checks.
Before a later main integration, update main and inspect any new conflict/dependency;
do not silently reuse evidence if relevant source/runtime inputs changed.
Final native platform/artifact/public consumer qualification, version metadata and
one-shot release submission belong to the separately authorized release operation.
Current canonical package version remains 0.4.5.
