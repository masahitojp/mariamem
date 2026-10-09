# v0.4.5 — Approved runtime/artifact responsibility migration

## Decisions and scope

The maintainer approved [checkpoint Decisions A/B](v045-infrastructure-checkpoint.md):
runtime-only qualification in the existing Product workflow; full final-artifact
GORM/SQLAlchemy/pytest; narrower publication smoke only with proven identities.
The [six audit decisions/inventories](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
remain inputs. Branch: `experiment/v045-infrastructure`, parent `1063440d48010487bca6bd3d96a1882a6415ef43`,
released baseline `8ede4ad65def07436b64801076004ff80aec0799`.
No production SDK/guest/generated source changes, merge, version bump or release.

## Replacement, not another framework

| Invariant/evidence | Canonical owner after migration | Change |
| --- | --- | --- |
| ordinary change verification | Development local Git diff + check/integration | no remote evidence dependency |
| native runtime correctness, including restored wire cases | existing Product workflow becomes Runtime qualification (v1); full check/integration on macOS15 arm64 + Ubuntu24.04 x86_64 | removes mandatory old performance campaign and wheel rebuild from runtime owner |
| source/guest/platform/toolchain/command identity | `runtime_validation.py`, intent v2 + runtime-qualification-v1 receipts | all tracked files + Git tree/modes; both exact native job/artifact identities; checksums; no v0.4.4 AST special-case allowlist |
| final artifact consumers | `generated_release_acceptance.py` candidate mode + generated release guard | retains GORM32, SQLAlchemy44, installed pytest/xdist and external Go lifecycle |
| actual public distribution | same harness, published mode, via `release_generated_ci.public_smoke` | accepted READY/provenance/assets, public module origin AND library bytes, installed wheel/package/host bytes, minimal Start/SELECT1/Snapshot/Fork/Close |
| order-balanced ORM case completeness | `consumer_acceptance.py` shared modes/count/failure oracles | local adapters and artifact adapter share 8/11 checks; release dependency pins come from existing requirements file |
| readonly cache disposal | existing experiment helper's authorized-tree removal | repairs directory permissions within owned trees; external symlinks not followed; protection/classification still precedes cleanup |

The registered workflow filename remains `v044-product-validation.yml` so an
experimental branch can use the existing Actions entry. Its display name, native
job names, artifact names and versioned receipts change. Old successful runs,
artifacts or bare PASS flags do not become new evidence. The v0.4.4 intent's
original bytes are archived; there is no active reuse intent for this branch.
Without an intent, the normal full Release CI path remains. Invalid explicit
intent still stops before build, never silently falls back.

Runtime source inventories include every tracked file, including guidance and
historical tracked build metadata. Restored corresponding-source trees omit only
existing repository-only/ignored paths; their actual public bytes must still
match the exact candidate Git inventory. Only documented non-executable docs,
README/guidance, intent and five version constants are exempt between runtime
basis and release source. Build recipes, consumer harnesses, workflows, tests and
arbitrary tooling changes invalidate reuse. Long retention (90 days) is convenience;
missing, expired, invalid, mixed-platform or changed evidence rejects reuse.

## Public smoke narrowing conditions

Publication first compares downloaded assets with the exact publication hashes.
Provenance must carry the same two READY platform records as publication, with
accepted consumer receipt hashes and the exact wheel/source identities. The Go
public module must resolve the requested tag/source commit through direct remote
origin and match accepted non-test library `.go`/`.s`, module metadata, license and
input-lock bytes; changed or extra library sources reject it. The installed Python
package inventory and bundled host must match the downloaded accepted wheel.

Unknown identity stops; it does not skip a test or mark ORM cases passed. Published
reports use `published-distribution-smoke-v1` and two minimal stages; they cannot
satisfy the candidate guard's full `generated-go-v1` stages/32/44 requirements.
Candidate mode still executes all full suites. Unit orchestration verifies this
split, including rejection before consumer execution when accepted proof is absent.
Actual final/public distribution qualification remains a future release gate;
local mocked orchestration is not reported as installed artifact execution.

## Verification and handoff

Focused negative/orchestration tests cover old schemas, origin/source/tag objects,
wrong/missing native jobs, expired/changed artifacts, checksum/inventory/harness/
command substitution, executable docs/recipe/consumer changes, partial runner
failure, accepted provenance, module bytes, installed files and cleanup.
Generated inventory/input identity and existing installer/handwritten inclusion
checks remain. See [compact local results](v045-p1-evidence.json).

Fresh native qualification is necessary because the qualification runner/receipt
and canonical wire owner changed. It proves the new commands actually execute on
both required native OSes; it does not rerun the v0.4.4 performance campaign or
rebuild the guest from upstream merely for infrastructure edits. No old native
receipt is relabelled. Source/tooling Development CI deliberately does not repeat
that native runtime job for this explicitly classified infrastructure boundary.

After push, CI owns qualification. Return candidate/run and stop per AGENTS;
resume on the human's completion/failure handoff. Native CI durations are part of
the forthcoming feedback-latency measurement, not guessed from local unit timing.

## Remaining P1/P2 work

Native qualification is pending at submission. Reconcile its actual evidence and
feedback latency before declaring P1 complete. Full fresh WASM rebuild/regeneration
has not been claimed for this branch; upstream/generated inputs are unchanged and
source-inventory/inclusion oracles run now. Release's reproducible build remains
required. Historical native adapters with retained regression/import consumers
have not been blindly deleted; complete their call/evidence-owner migration before
retirement. The active runtime runner and special-case reuse logic are simplified.

Then use existing OwnedPrepared capture/payload, internal timing and process-cost
helpers for full-public Snapshot decomposition, suite crossover and bounded product
controls. No competing performance runs. No Snapshot optimization without Human
Review. No automatic merge/release or v0.5 guest migration.
