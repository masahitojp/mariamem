# v0.4.6 integration and release qualification

## Decision boundary

PO approved all v046 usability findings and accepted the completed Go performance
comparison. This integration stays on `experiment/v046-release-qualification`.
Main merge/push, final version bump, tags and publication are not authorized.
Canonical metadata therefore remains **0.4.5**; [v046 notes](../../release/NOTES-v0.4.6-draft.md)
are a draft. Verify CI can qualify this exact development source and its newly
built 0.4.5-labelled private candidate artifacts, **not** the public v045 tag or
final v046 bytes. A later approved version change requires exact final-version
artifact/consumer/guard verification; these development artifacts cannot be
relabeled or published as v046.

## Integration and smoke audit

Fetched main/origin: `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb`.
Released v045 source: `d992e26a6d110ceeb54f69d71acd1358c72abb1b` (peeled commit; annotated
tag object `3f7b45164770cb8ca278c531884b14cfa91af2c7`). Integration prep: `8b1dfcadf465fd4c00de065c340f38a5fd254a72`.
Main is its ancestor; fast-forward into the work branch had no conflict.
Existing main history is preserved, including:

| Commit | Change | Carry-forward |
| --- | --- | --- |
| `973a6741876052ff9d8ca7374bee11436ad88d37` | Go public smoke waits for server COM_QUIT/session drain before Snapshot | exact program unchanged |
| `67ff77470bb88504ca844b6c7b5130692e0a8634` | bounded recovery design/evidence | retained historical report |
| `135b791e3153cf02081b053337ec298a16e0c7ae` | authenticated read-only Ubuntu smoke recovery using pinned repaired program against immutable published bytes; tests | workflow/recovery scripts retained unchanged |
| `0fef33c752053d3bd1e180f9e46f4a301cfcd5eb` | successful recovery record | retained |

Actual Actions run `38014576300` published v045 and passed macOS public smoke but
failed Ubuntu public smoke; recovery `38021032245` succeeded on Ubuntu without
rebuilding/republishing. Git diff and Actions jobs agree with the
[v045 report](v045-public-smoke-recovery.md). No duplicate cherry-pick was needed.
The report's historical last statement about not yet being on main predates the
current main integration; the Git ancestry above records today's state.

This qualification adds execution of the same repaired Go smoke program to
candidate acceptance, before publication (still external module, no replace).
Failure leaves the acceptance receipt FAIL. Two old workflow tests incorrectly
asserted the operation list omitted recovery; their expectations now match the
already-shipped workflow without changing permissions or publication gates.

## Approved contents and exclusions

- Go LoadSnapshot: existing validated OwnedPrepared import wrapper; 31 added
  production lines in snapshot.go. Ownership, validation, format and child
  isolation are unchanged. Existing persisted lifecycle test moved from
  gointegration to godefault, so native integration **and external Go module**
  acceptance run it; no duplicated test body. The integration build tag is the opt-in boundary;
  the moved test no longer skips in the external consumer environment.
- Accepted Go/Python guides, executable examples, representative type probes and
  bounded Product Validation harness fixes/evidence are retained.
- Performance source `1e203d2c25d751e199de3c90194fc2142cf6517d`: import report,
  485 checksum-bound evidence files and reproduction recipes only. No changes to
  benchmarks/ownedprepared/main.go or toolchain_compare.py are integrated.
  Reproduction uses pinned measured source `80a37385f9d1eda6604358dd5ba2235feb0b26ca`.
- Consumer-library source inventory is byte-identical to approved usability source
  `2432abd5439d8daa2ead9676c8c2561ad807b280`. Go1.27 compatibility and performance
  evidence are accepted at that unchanged product boundary, not new native
  final-artifact evidence.
- go.mod Go1.26.0, mysql v1.9.3, Python SDK, generated source/provenance, guest,
  mmap, Snapshot format and notices/licenses are unchanged against main.
- No VFS/resizeMemData, translator, Snapshot/Fork or guest optimization; no new
  API beyond the approved LoadSnapshot. No performance-speedup claim.

## Verification status at CI handoff

| Boundary | Status | Evidence / owner |
| --- | --- | --- |
| Exact source/ancestry/smoke carry-forward, clean diff | PASS | Git objects/diffs, Actions history, git_identity helpers |
| Performance evidence | PASS | 485 SHA256SUMS entries recomputed |
| Focused artifact/consumer/planner/license/source tests | PASS | 125 tests, including controlled smoke failure |
| Canonical Python/source checks | PASS | verify.py check --scope python: 515 PASS / 35 opt-in SKIP; version/public-source/diff |
| Generated source/input/guest identity | PASS | verify_generated_runtime.py |
| Go LoadSnapshot unit regressions (Go1.26.8 local compiler) | PASS | go test -p 1 . -run TestLoadSnapshot -count=1; 1.261s test execution |
| Actual repaired v045 Go smoke program (local canonical compiler) | PASS | Start/SELECT 1/Snapshot/Fork/SELECT 1/Close; external module execution also required in CI |
| Persist→Load→source deletion→two Forks→parent Close→commit/rollback/isolation (local Go1.26.8) | PASS | moved godefault regression; 1.717s test execution |
| macOS15 arm64 and Ubuntu24.04 native Go unit/vet, focused races and runtime/Python integration | PENDING CI | Release CI full candidate path |
| Newly built wheels + external Go/default/LoadSnapshot + GORM32 + SQLAlchemy44 + installed Python | PENDING CI | Release CI immutable artifact acceptance |
| Two independent guest rebuilds, generated reproduction, corresponding source/licenses/NOTICE/provenance, aggregate guard | PENDING CI | existing full verify route, no gates removed |
| Final 0.4.6 metadata/artifacts and public-tag/public-wheel smoke | NOT YET | final Human Decision; public smoke follows authorized publication |

Local host is newer macOS27 arm64; it cannot stand in for macOS15 acceptance.
Prior Go1.27.2 Ubuntu consumer ran under Rosetta, not native Ubuntu qualification.
Native Release CI uses canonical Go1.26.8; no unperformed native Go1.27 matrix is
claimed. Accepted macOS1.26.8/1.27.0/1.27.1/1.27.2 product results remain valid at
the unchanged library boundary. Full generated-guest race cleanliness and forced
non-cooperative containment remain known limitations, not silently skipped gates.
No new benchmarks or competing measurements ran.

## Release readiness / next Human Decision

BLOCKED pending native artifact verification and final metadata approval.
After CI handoff, Codex stops rather than polls per AGENTS.md; CI result is not
predicted in this document. Review the exact candidate and CI receipts before
main integration. Version preparation will set only PATCH=6 in canonical metadata,
update current release examples/intro to derived 0.4.6, and promote the draft to
NOTES-v0.4.6.md. Do not change guest, dependencies or compiler support minimum.
The later one-shot release remains a separately authorized transaction.
