# v0.4.5 — P0 complete, CI responsibility review checkpoint

## State and recommendation

P0 is implemented on `experiment/v045-infrastructure`, from released
`8ede4ad65def07436b64801076004ff80aec0799`. Main/version/release are unchanged.
The [six audit decisions and inventories](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
remain authoritative inputs. No performance optimization or measurement campaign
has begun. v0.4.5 is not yet release-ready.

- Restored supported wire/session oracles to canonical integration, with seven
  real generated-Go tests PASS on macOS. See [each invariant's owner](v045-wire-coverage.md).
- Development selection now uses event before/base versus candidate Git commits,
  never historical Product artifacts. Explicit classified tooling runs Python/source
  checks; unknown inputs/base failures run full check/integration. Release strict
  validation is unchanged, including expired/corrupted/mismatched proof rejection.
- Extracted live published-asset verification and latency/resource reducers from
  old native CLI modules; migrated current callers and preserved historical adapters.
  Exact hash, extra/missing/corrupt/ambiguous manifest negatives remain tested.
- Existing two Skills remain. Local scope table and current cleanup link now live
  in development docs; AGENTS no longer labels architecture branches as only 0.2.
  Project status reflects the actual published v0.4.4 source/tag/run.
- Python check: 466 PASS, 31 skips, 12 subtests PASS. Final focused tests: 143 PASS.
  Wire tests were run separately: 7 PASS. Committed generated inventory and installer
  handwritten carry/repro-tool negatives PASS. Full new source-to-WASM reproduction
  and Ubuntu execution are not claimed. [Compact evidence](v045-p0-evidence.json).

## Historical checkpoint: why work stopped here

The next changes cross the task's explicit review checkpoints: removing required
checks from a stage, materially changing reusable CI evidence, and changing the
canonical qualification entry. They are not ordinary refactors. No release workflow,
runtime receipt schema, release reuse allowlist or public-smoke breadth has been
changed in this checkpoint.

Current `v044-product-validation.yml` combines check/integration, installed pytest
wheel and mandatory v0.4.3 performance comparison. `runtime_validation.py` trusts
this named workflow's complete successful run, both native jobs, artifact IDs/digests,
source inventory and correctness record. Simply deleting its performance step
would change the meaning of the authenticated success without defining a new
contract. Reusing its name/schema for a new runtime-only receipt is therefore unsafe.

The final artifact consumer harness already runs GORM32, SQLAlchemy44 and installed
pytest/xdist on exact candidate bytes. Published mode runs this full set again.
A smaller public smoke is defensible only with exact accepted-byte and public-tag
identity preserved, and explicit acknowledgement of the narrower post-public oracle.

## Decision A — Runtime-only qualification contract

**Recommendation:** create an explicitly versioned runtime-qualification contract
and migrate the existing Product workflow/runner; do not add another competing
full acceptance framework. Keep both native platforms and canonical source check /
integration (including the restored wire suite) in the initial runtime qualification.
Move installed-wheel consumers to final-artifact qualification, where they already
run, and move performance into manual measurement after matching correctness.

**Required receipt:** exact commit object/source tree, guest/input identity,
toolchain/native platform, harness hashes/commands, successful required stages and
both platform artifact identities authenticated through Actions with ZIP SHA256.
Keep full inventories first; no blanket scripts/tests exceptions or new speculative
runtime dependency graph. New harness must reject an old schema as a new proof.

**Lifetime:** Development remains receipt-independent. Explicit release reuse still
fails closed on missing/expired/invalid evidence. A fresh qualification must be an
explicit selected operation; it cannot silently rescue invalid explicit intent.
Archive the v0.4.4-specific intent for v0.4.5 rather than extending its allowlist to
unrelated new source/tests. Without a valid explicit reuse intent, the existing
normal full release qualification route remains available. Long retention is a
convenience, not a substitute for these rules.

**Strongest evidence:** v0.4.4 separated tested runtime `c5f4310` from final source
`8ede4ad` successfully. The current fixed Product workflow couples that useful
proof to an unrelated v0.4.3 campaign and 14-day artifact lifetime.

**Counterargument/downside:** another receipt version/migration adds trust-boundary
code and negative tests; re-running source checks on both native platforms retains
some intentional duplication. This must be simpler than maintaining special-case
v0.4.4 AST exceptions indefinitely. New qualification requires actual fresh native
runs; old evidence must not be relabelled.

**Human question:** Adopt this runtime-only contract, keeping source check/integration
on both OSes while moving installed artifacts and performance to their own owners?

## Decision B — Public smoke scope

**Recommendation:** retain full installed consumers before publication, then reduce
post-publication to public download/hash/provenance, actual installed wheel,
public Go module resolution with exact tag/source Origin, and tiny Start/SELECT1 /
Snapshot/Fork/Close checks. Keep both OSes and fail on wrong bytes/versions/resolution.

**Strongest evidence:** current published mode repeats the same GORM32/SQLAlchemy44
and installed pytest suite already checked against the exact accepted artifact.
Public transport adds a distinct risk, but does not change identical runtime bytes.

**Counterargument/downside:** full ORM execution through public resolution will no
longer occur after every publication. Wrong public source/package selection must be
detected mechanically by identities plus tiny installed behavior; full ORM remains
required for final artifacts. If this identity premise cannot be enforced, keep
full public acceptance rather than silently narrowing it.

**Human question:** Keep full final-artifact consumers and narrow only the subsequent
public smoke under these exact-byte/public-origin conditions?

## Approval and continuation

The maintainer approved Decisions A and B: migrate the existing Product workflow
to strict runtime-only qualification, retain full final-artifact consumers, and
narrow publication smoke only with exact accepted identities. See
[v045-p1 implementation/evidence](v045-p1-runtime-artifact-migration.md).
No merge/release or Snapshot optimization was approved.

## Remaining sequence after review

Finish ORM case/dependency consolidation and historical caller migration; implement
approved evidence responsibilities and negative tests; native qualification;
stabilize measurement preflight; then Snapshot total decomposition, Fresh/Fork
crossover and bounded product controls. No Snapshot optimization without another
Human Decision. No guest migration, automatic cache or public product feature.

Canonical roles remain check, integration, native acceptance, manual bench, release;
only the first two are normal development tasks. Current `check --scope` preserves
`full` as the default; narrower scopes are explicit boundary assertions.

P0 introduces no runtime change, so no unrelated platform acceptance was rerun.
The new wire cases require real execution and received that execution on macOS;
Ubuntu is pending the next qualification, not inferred from previous CI.
No v0.4.5 version bump/release/merge is authorized by this checkpoint.
