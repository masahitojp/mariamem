# Evidence retention — decisions survive, obsolete payloads do not

Status: Human-approved direction for #158, 2026-11-14.

Keep continuing decisions in `docs/decisions/` (ADRs), current direction in
`docs/project-status.md`, and actionable work in its existing Issue. Once a
review has informed a decision, transfer its rationale, rejected alternatives,
material objections, limitations and reopening conditions to the relevant ADR.
An investigation that failed or was rejected must not become an accepted claim.
Then delete obsolete reviews and raw evidence from the current tree.

No permanent evidence branch, separate repository or release-asset archive is
required. Existing Git history remains available for historical context; do not
rewrite it or copy its payload into a new archive. A fixed-commit link identifies
old context, not a promise to rerun that source or a new PASS at current HEAD.
Product release assets and legally required provenance/license inputs are outside
this cleanup.

## What remains

- Active oracles belong in `tests/fixtures/` or their maintained tooling owner,
  not in review prose. Move their consumers and preserve contract values, source
  identities and mutation checks before deleting the old path.
- Keep compact unique measurements and failures when they still inform a live
  decision. Preserve the workload, exact source, environment, samples/outcomes
  and limitations needed to interpret them. Do not preserve repeated generated
  inventories, full CI REST responses or successful console transcripts.
- Keep a small acceptance receipt if current provenance or a continuing decision
  requires it. Distinguish source commit, CI run and later integration identity.
  Artifact expiry must not erase the essential facts supporting a retained claim.
- Routine CI output belongs in CI artifacts with their configured retention.
  Durable external storage is exceptional, for an explicit consumer and retention
  need; it is not the default replacement for deleting obsolete logs.

The strongest cost is losing convenient local access to old debugging detail.
That cost is accepted for obsolete evidence. Preserve the indispensable unique
observation before deleting, rather than preserving an entire job bundle in case
it might be useful. Reopen retention only for a named ongoing consumer or a
missing fact needed to assess a current decision.

## Completion and recurrence

Review the source diff before Ready. State evidence bytes added/removed, verify
remaining references and necessary checksums, and explain any retained large
payload. Do not introduce new base64 CI archives. Keep review trees outside the
root Go module via `docs/reviews/go.mod`; that module boundary does not justify
retaining junk on main. Architecture experiment branches continue to own
unadopted prototypes, not permanent stores of review logs.

This policy changes storage and documentation ownership, not guest SHA,
provenance, license, security, runtime, public API or release contracts. #177,
#179 and #180 keep their separate work; #158 does not weaken their guards.

## Benchmark inventory disposition — Issue213 C

The cleanup source is `80bd4332f757b5f72b2dcffc5a7f9a97d779e7f8`.
The entire tracked benchmark tree was inventoried, including maintained code,
prepared generation inputs, measurement data and historical receipts. This
cleanup removes rebuildable logs/listings and repeated source inventories in
buffer-zero, the largest redundant payload. Its saved-result verification still
covers both complete measurement series; the canonical previous-build record and
current CI harness remain byte-identical. The campaign's retention record pins
the original payloads in Git history and distinguishes old hashes from current
checksums.

Other retained groups have specific continuing purposes:

| Group | Retention purpose |
| --- | --- |
| ucapreparedinput, lexerpreparedinput | Current generation inputs and hash-bound source contracts |
| ownedprepared, goisolation, competitive, sharedhost, memorylifetime, snapshotallocation | Maintained benchmark/fixture tooling; preserve executable inputs |
| main-product-evidence, ubuntu-product-evidence, ubuntu-product | Historical finite matrices and all observations; historical Ubuntu oracle reads two main-product cells directly |
| v043-release/retirement, v045-measurements, v046-usability, v047-upstream, v050-product | Version-bound measurements, failures and acceptance receipts; preserve source, environment and full samples rather than relabel as current acceptance |
| v060-latency-evidence, modelcase | Historical comparison samples and pinned raw-record identities used by retained reports |
| timer-product, memoryea-product, prepared-output-20261114 | Continuing adopted-change rationale, measurements, tradeoffs and failure controls |
| dictionary-installed, platform-cache, ubuntu-startup, spikes | Reproduction tooling and archived experiment source; source/fixtures are not disposable logs merely because they live under benchmarks |
| Top-level reports, values and boundary records | Original-source numeric observations, interpretation, rejected alternatives and limitations linked by historical release/design records |

These retained groups were not proven redundant. Some are larger than the new
per-file budget because they hold full numerical samples or existing receipts;
the immutable A1 baseline binds their exact identity. In particular, large
v043/v045/direct-link/boundary JSON records contain trial/observation arrays,
not only generated file inventories. This disposition retains them deliberately;
it does not create an automatic exemption for additions or edits. New retention
needs require review. Current review/source/provenance/fixture consumers remain
with their existing owners, and `docs/reviews/` is unchanged by this cleanup.

Dynamic consumers cannot be exhaustively proven absent by text search. For this
reason C confines deletion to the inspected generated transcript/listing and
inventory fields, preserves the previous canonical record, and checks the
existing saved-result reducer. Further historical numeric reduction needs a
specific equivalence/retention proposal rather than blanket JSON deletion.
