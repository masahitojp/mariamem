# v0.4.4 — Runtime evidence reuse before release

**PROPOSAL ONLY.** The maintainer stopped release dispatch to review this design.
No workflow/guard/runtime implementation is changed by this report. v0.4.4 is
not published and package metadata remains 0.4.3.

## Recommendation

Separate two proofs inside the existing one-shot release operation:

1. The runtime inputs are the same as a successfully tested source on both OSes.
2. The actual final-version artifacts/source/notices are correct for the exact
   candidate being published.

Reuse the first proof; freshly establish the second. Never rewrite an old
receipt's source SHA, version or wheel hash to make it match a new candidate.
This is narrower than cross-source READY or wheel reuse.

## Current facts and blockers

- Runtime basis **R**: `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.
  [Product CI run 37898847164](https://github.com/masahitojp/mariamem/actions/runs/37898847164)
  passed both macOS arm64 and Ubuntu x86_64 jobs, correctness, installed
  pytest/xdist and performance/FD gates. It built 0.4.3-version candidate wheels.
- Local main integrated R, identity fix `55f46a1…`, and scope clarification
  `69f852d…` by fast-forward. At `69f852d…`, runtime/API/guest/dependency files are
  byte-for-byte R; only ten tooling/docs paths differ. Remote main is still
  `c8bd25a…`. No dispatch/tag/publication occurred.
- `scripts/release_plan.py:ready_bundle` requires source/version/artifact equality;
  discovery examines canonical Release CI READY, not Product CI. There is no
  valid READY for the eventual v0.4.4 source **F**.
- The workflow's full candidate job invokes both `verify.py check` and
  `verify.py integration` before building wheels. It would repeat the runtime
  tests already covered by R.
- `generated_release.verify_acceptance` also requires exact F/version/wheel
  identities, GORM32 and SQLAlchemy44. Product CI does not provide those ORM
  receipts. They must not be marked passed by reusing Product CI.
- `check.yml` automatically runs compilation/unit checks and macOS integration
  on a main push. Avoiding only release-job duplicates is insufficient.
- `release_prepare.py submit` invokes full `verify.py check` when preparation
  files are dirty. Its scoped preparation behavior must also be considered;
  the design must not hide a duplicate local runtime campaign.

## Smallest credible reuse proof

Use a narrow, reviewed comparison against R; do not begin with a general-purpose
cache, arbitrary trusted SHA or user-controlled `skip_tests` switch.

| Requirement | Fail-closed validation |
|---|---|
| Source identities | Full commit SHAs, object type, R ancestor of F, clean exact F checkout |
| Evidence origin | Repository + pinned Product workflow path, successful required native jobs, exact R, explicit artifact IDs and GitHub ZIP digests |
| Evidence content | Verify each internal checksum, source inventory against Git R, native platform/toolchain/build settings, required results and suite completeness |
| Runtime equality | Compare R/F trees; reject added/removed/renamed/type/mode-changed inputs outside a narrowly reviewed non-runtime exception set |
| Exception set | Named identity/preflight tooling and focused tests, current docs/reports/notes, and future reviewed release-validation plumbing; never blanket-exempt `scripts/`, `tests/`, `release/` or Python |
| Version preparation | Only the five canonical version assignments may differ in `_version.py`; all derived logic stays identical. Check final version and manifest behavior separately |
| Compiler/guest inputs | Same complete generated/handwritten/runtime/API/host/Python source, dependencies, guest/pins, compiler and semantic build settings; changed configuration invalidates reuse |
| Lifetimes | Both-platform evidence required; a flag, matching path or head SHA by itself is insufficient |

Prefer a complete tree-diff proof with explicit exceptions to an initially
fragile hand-picked list of runtime files. Unknown changed paths fail closed.
Evidence harness identity is checked against R; changed focused tooling at F is
tested at F. Do not demand that an old harness falsely appear to have tested F.

The final receipt records **both** `runtime_basis_commit=R` and
`release_source_commit=F`, run/artifact identities, the comparison/exception
proof and focused-check results. Final wheel hashes and build-info identify F.
Do not normalize native binary bytes or claim that a changed VCS build-info
revision makes the old and new wheel byte-identical.

Record the authenticated evidence selection in a compact tracked input; compute
F in CI from the dispatch SHA, avoiding a self-referential commit field. After
runtime proof succeeds, candidate builds and aggregate guard consume its digest.
Mutable artifacts changing between selection and guard invalidate the release.

## One-shot stage plan

Normal public operations remain `verify` / `release`, with automatic planning.
No preceding verify, manual recovery run IDs or extra publication approval.

| Boundary | Proposed action |
|---|---|
| Runtime unit/integration/races/Snapshot generation/isolation | Reuse R's authenticated both-platform evidence when the equality proof succeeds |
| Ready/performance/FD measurement | Preserve original R measurements; no new benchmark campaign and no performance claim for unmeasured F |
| Final Go module/wheel acquisition | Build/package exact F at v0.4.4, freeze hashes; test outside-checkout module resolution and installed bytes/version/manifest/entry points |
| GORM32 / SQLAlchemy44 | Retain qualification: absent from Product CI, so these are new consumer evidence, not inherited PASS |
| Source/license/NOTICE/provenance | Retain exact F checks; no false source identity or silent notice exception |
| Guest source reproducibility | Preserve the current recipe/guard; reuse of guest-build provenance is a separate question, not automatically granted by runtime reuse |
| Aggregate release guard | Require runtime equivalence proof plus exact F artifact/consumer/source records; old READY alone is insufficient |
| Publication/public smoke | Retain existing exact-tag publication and public checks; no direct local publish |

Initially keep the existing external consumer stage unchanged: its ORM and
packaging coverage is missing for the new candidate, and splitting all those
tests would enlarge this change. This proposal removes duplicate Product runtime
campaigns, not every invocation of SQL during release or public smoke.

For an explicitly selected reuse intent, missing/expired/corrupted/incomplete
evidence or a changed runtime must yield **NOT READY**, not silently select full
runtime qualification. Ordinary future candidates without reuse intent can
retain full qualification. Exact-F READY reuse remains the strongest existing
path when it exists.

Before main push, make Development CI use the same proof for the certified
integration/preparation commit; it must not launch duplicate integration because
its parent was v0.4.3. Genuine later runtime edits run normal checks. Release-only
metadata preparation should use focused docs/version/identity/release-tool checks
when the proof permits it. Never globally disable integration on main.

## Expected implementation boundary after approval

- Add one pure comparison/evidence validator and focused rejection tests.
- Extend planning and platform/aggregate receipt verification with a distinct
  runtime proof. Preserve artifact/source identity equality.
- Condition only duplicate candidate runtime commands on that proof.
- Align Development CI and preparation checks with the same bounded rule.
- Keep immutable artifact transport fail-closed. Product evidence transport must
  be typed separately; do not weaken the existing Release workflow restriction
  in the generic handoff downloader.
- Update release docs/skill to explain runtime basis versus release source.

This crosses the release-guard boundary and needs reviewed tests; it is not one
`if` or a `verified=true` shortcut. It is smaller than reusable cross-SHA READY
or a new cache service and does not change MariaDB/Snapshot behavior.

Acceptance tests must reject tag objects, wrong release refs, wrong/missing OS,
unsuccessful runs, wrong workflow/repository/source, altered inventory/hashes,
unreviewed runtime/helper/dependency/config changes, disguised version logic
edits, stale artifacts and failed equivalence checks before expensive work.
Verify READY needs both proofs and publication remains impossible on NOT READY.
Test the main-push and local-preparation paths as well as Release CI.

## Decision to review

Approve **runtime evidence reuse + fresh exact-version artifact/consumer gates**
as the bounded implementation target. This does not mean reusing old 0.4.3
wheels, skipping new ORM coverage or claiming that F itself ran R's tests.
If the desired requirement is also to omit all external consumers/guest builds/
public-smoke SQL, that is a larger contract change and needs separate discussion.

The FD trade-off remains accepted, with many concurrent/file-heavy baselines a
non-blocking workload-driven future concern. No v0.4.5 is created here.
