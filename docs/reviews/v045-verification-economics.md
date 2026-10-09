# v0.4.5 Verification Economics & Final Stabilization

## Human Review packet

**Recommendation: READY FOR v0.4.5 RELEASE PREP, after Human Review.**
Keep the distinct source/runtime/artifact/publication guarantees. The largest
measured cost is not the count of Python tests; cold Go build/link/analysis is
substantial, but existing logs cannot assign its components precisely. Do not
weaken qualification or redesign feedback architecture to chase unmeasured savings.
Two small changes consolidate generated ownership and move existing source/license
oracles before compilation. No check, license obligation or release safeguard is
removed. No new Skill/workflow/manifest/framework, runtime change or benchmark run.

The [six audit decisions/inventories](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md),
[P0/P1 checkpoint](v045-infrastructure-checkpoint.md),
[approved A/B migration](v045-p1-runtime-artifact-migration.md) and
[completed measurements/review](v045-human-review.md) remain inputs, not replaced history.

### 1. Verification value and cost

Every retained expensive boundary has a different failure target: source can be
unreproducible while tests pass; runtime can be correct while a wheel omits a host;
local artifacts can pass while the public tag or download serves different bytes.
Keep those layers. The current whole-tree evidence scope is conservative and has
maintenance cost; a smaller dependency-derived scope needs explicit coverage/trust
design, deferred rather than silently weakening the accepted P1 contract.

### 2. Implemented bounded improvements

- **MERGE ownership lists:** installer `generate_runtime.HANDWRITTEN_FILES` is the
  verifier's canonical handwritten boundary. The independent clean-installer test
  still derives expected files from actual source minus provenance, not that list.
  Overlap with generated inventory rejects an attempt to hide a generated edit.
  Generated mismatch errors identify paths and point to adapter/regeneration,
  explicitly discouraging unexplained provenance hash refresh.
- **MOVE source oracles:** the existing generated inventory/inclusion/adapter,
  license binding/notices and Python mirror suites run before Go in full `check`.
  Later broad pytest excludes exactly those suites so all guarantees run once.
  Python-only checks still execute them normally. Existing release preparation
  shares the list and checks inventory first. No separate preflight framework.

Focused verification: **110 PASS in 1.21 s**, including independent installer,
ownership overlap, modified-file reporting, negative licensing, archive notices,
mirror checks and ordering/no-Go-on-failure. A real stale-evidence whitespace
mutation failed in **1.18 s before any Go command**, then original bytes were
restored. Additional identity/source tooling suites: 217 PASS; the actual updated
release-preparation entry passed 207 tests plus 3 benchmark-helper tests. These
sets overlap and are not summed as unique cases. The previous source reached Go before this oracle; it was intercepted,
not benchmarked. This is earlier actionable feedback, **not a measured 25-minute
speedup on successful CI**. See [compact evidence](v045-verification-economics-evidence.json).

### 3. Remaining structural issues

No exact compiler/vet/race-build stage clocks; conservative whole-tree reuse
invalidation; cold normal/race/tagged builds; Development check/integration on
different workers; release artifact/reproducibility costs. Evaluate these in
v0.5.0 Fast Feedback with actual command timing and dependency proof. Do not remove
real integration, consumer tests, source rebuilding or accepted identity guards.
Source continuity evidence's Snapshot-specific field is friction; a generic schema
would change trust/maintenance semantics and needs its own Human Review.

### 4. Measurement documentation and next scope

[Benchmark document](../../benchmarks/v045-measurement.md) now owns conditions,
full-public timing, crossover and reproduction. Raw JSON/CSV/checksums moved there
without byte changes. README is unchanged. Fresh may win for cheap setup; reused
expensive preparation may win; no universal fixture-size threshold, no adopted
Snapshot optimization. No new Testcontainers/shared-DB campaign in this phase.

[v0.4.6 handoff](v046-handoff.md) owns Go persisted-load completeness, comparable
Go/Python documentation/scenarios and later realistic Product Validation. It is
a handoff, not implementation or a new release created automatically.

### 5. Identity and release readiness

Released main remains `8ede4ad65def07436b64801076004ff80aec0799`.
This work starts from measurement report source
`02573816dfe37edd76df6f7400a0d05bd915637f`; its executable measurement input is
`f0a06f4d0e39756fe7839783fc00dbcc2a8ca0c9`.
Actual native-qualified runtime/source is
`34eaea1df86b57765a4d8b0840845a33d539065f`,
[run 37994377940](https://github.com/masahitojp/mariamem/actions/runs/37994377940).
705 tracked inputs and both exact native receipts remain authenticated historical
evidence. Downloaded logs were checked against their SHA256 inventories and pinned
receipt/run/source; no old proof was relabelled.

This phase changes orchestration/generator ownership declarations/tests/docs only;
generated/SDK/guest/runtime/provenance/license bytes are unchanged. Focused tests
prove the copy boundary and execution order; no new native runtime qualification
is claimed. **The executable verifier/generator changes invalidate automatic reuse
under the current strict P1 rules.** Preserve old proof under its identity; do not
activate an intent or override that rejection. Release prep must use the existing
fail-closed qualification path for the exact final candidate and final artifacts.
No merge, version bump, dispatch or publication has happened here.

**Human question: accept this bounded final stabilization for v0.4.5 release
preparation, leaving trust-scope redesign and performance optimization deferred?**

## Appendix A — Check-by-check economics

| Check/owner | Decision | Unique risk / failure oracle | Invalidation / appropriate stage / cost |
| --- | --- | --- | --- |
| generated inventory, pins, guest (`verify_generated_runtime`) | KEEP; SIMPLIFY error/list ownership | edited/missing/extra generated output, wrong accepted input/guest; hashes actual files and refuses unexplained differences | generated bytes/pins/guest; development before compile; local <1 s |
| independent clean-installer source test | KEEP, MOVE early | handwritten file omitted from regenerated tree even when normal build works; actual expected source-minus-provenance compared with installed files/bytes | new/deleted/changed glue, installer; development/regeneration; no Go build |
| pinned driver adapter test / fixed-formatter byte proof | KEEP | direct output edit has no reproducible recipe; known pinned input, fragment shape and export body; whole-driver formatting proof remains separate | driver/adapter/converter/formatter; fast test first, actual full regeneration at release |
| full upstream guest→translation→installation byte comparison (`regenerate_release_guest`, release `verify_build`) | KEEP, release/regeneration owner | hash self-consistency is possible for unreproducible or incomplete source; independent accepted build reproduces every generated and handwritten byte | guest/patch/translation/build/toolchain/adapter/glue; expensive, not routine docs/tooling edits |
| provenance/input/guest identity vs regenerated proof | KEEP | correct-looking result generated with another recipe/input or stale receipt | those inputs/source identity; source and release, distinct from SQL tests |
| distribution notice/evidence inventory | KEEP, MOVE early | missing/unclassified/tampered notices or orphaned attribution receipt | notices/classification/evidence bytes; fast development, rechecked against final packaged files |
| guest/provenance/license continuity and retained definitions test | KEEP, MOVE early; future SIMPLIFY schema | attribution applied to different guest/generated content; positive retained-source examples disappeared | guest/provenance/retained source; review first; hash change alone is not a new obligation |
| upstream notice archive comparison | KEEP | local notice + local hash changed together; detects against pinned original archive | upstream input/notice origin/bytes; small synthetic development oracle; real archives at release/source packaging |
| Python license mirrors | KEEP, MOVE early | clean source checkout and wheel staging disagree even when root notices pass | inventory/notices/mirrors; byte equality, no guest; final wheel check remains distinct |
| `go test ./...` vs vet | KEEP | runtime unit assertions vs static suspicious constructs; generated dead-control exception is narrow, full handwritten vet retained | code/toolchain; relevant changes/full qualification; share build cache within job, no deletion by name similarity |
| handwritten race tests vs tagged guest integration | KEEP | host synchronization/lifetime races vs real MariaDB SQL/isolation behavior; generated full race is not claimed | corresponding code; normal/race/tag build variants have necessary distinct coverage |
| Runtime qualification receipt (existing workflow) | KEEP | tests skipped/runner substituted, mismatched platform/source or forged partial PASS; exact jobs/tools/commands/artifacts | accepted full tracked-input model; both OSes; expired/missing proof rejects release reuse |
| final GORM32/SQLAlchemy44/installed pytest + Go lifecycle | KEEP, artifact owner | packaging/ABI/external consumer behavior absent from source runtime tests | final bytes/dependencies/harness; exact final artifacts, release; not repeat as public smoke when identity is proved |
| publication asset/module/wheel identity + minimal smoke | KEEP | actual public distribution differs/unavailable/uninstallable; accepted local file is insufficient | published tag/source/assets; only after publication; full artifact consumers are its trusted basis |
| repeated full-source suite later in full `check` | REMOVE duplicate invocation only | same three suites already ran before Go | explicit excludes preserve all original cases; Python-only scope still runs them once |
| two identical handwritten declarations | MERGE | list drift, missing new glue | verifier imports installer list; independent source-derived oracle protects against shared-list self-confirmation |

No guarantee is retired. Tests are not reduced merely because 491 cases exist.
Broad verification belongs to runtime/build boundaries and releases; source-only
metadata failures should not need successful compilation to become visible.

## Appendix B — Existing CI time attribution

| Exact 34eaea1 qualification | Ubuntu | macOS |
| --- | ---: | ---: |
| whole native job | 1075 s | 1495 s |
| recorded check subprocess | 419.87 s | 587.54 s |
| ordinary Go test processes, summed | 1.257 s | 1.620 s |
| ordinary Python pytest reported | 16.80 s | 28.14 s |
| recorded integration subprocess | 622.94 s | 856.91 s |
| race + tagged Go test processes, summed | 38.243 s | 30.402 s |
| real-host Python pytest reported | 50.14 s | 32.54 s |

Earlier P1 8a30e184 whole jobs were ~15m21s Ubuntu / ~31m05s macOS. Those are
different cold runs, not before/after speedup evidence. Latest check minus visible
test process times leaves ~402/~558 s for compilation/link/analysis, source checks,
process startup and other overhead; it is not a measured compiler-only duration.
Race compilation is another build variant. `snapshots.py` reports 49 checks but no
elapsed duration; integration's residual cannot be assigned solely to compilation.

Job timestamps separately cover checkout/Go/Python/pip/upload/cleanup; aggregate
whole-job minus check/integration is ~32/~51 s, including all those boundaries and
unsegmented runner/orchestrator cleanup. The receipt total scope and job scope
differ slightly. There is no final-wheel/provenance build in this runtime job;
do not attribute its minutes to artifact qualification. Detailed steps/log hashes
and observed process durations are preserved in the evidence JSON.

Time to useful failure improved for a demonstrated stale-evidence path (~1.18 s
local), but normal success throughput is essentially unchanged. Cheap source
checks add one early pytest process; later duplication is excluded. Python tooling
is suitable here; rewriting it in Go would not solve cold generated compilation.

## Appendix C — Change-impact map

The owners are the existing installer, input pins, provenance, license inventory,
release guard and source inventories. This table is guidance, **not a second
machine-maintained registry**. Inventory differences and byte equality are
mechanical; determining attribution/license meaning and accepted trust scope is
a human/source-review action. No command auto-refreshes these records.

| Changed input | Consequence | Mechanical owner / human decision |
| --- | --- | --- |
| generated `.go`/`.s` output | MUST REGENERATE; MUST REVIEW when no canonical recipe edit explains it | verifier identifies exact differing paths; change installer/converter recipe first, not output + self-approved hash |
| handwritten generated-directory glue | MUST REVALIDATE relevant runtime; MUST REGENERATE inclusion at clean regeneration | installer list and independent source-minus-provenance copy test; no generated provenance hash refresh just for glue |
| new handwritten file | MUST REVIEW ownership; MUST REVALIDATE inclusion | installer `HANDWRITTEN_FILES`; an unclassified actual file fails inventory; tests verify copied contents independently |
| guest/patch/converter/build/formatter/translation inputs | MUST REGENERATE and MUST REVALIDATE identity/runtime/release | existing input pins/toolchain/recipe plus fresh independent build; retained-library review/audit may be required |
| provenance bytes/content identity | MUST REVIEW cause; MUST UPDATE EVIDENCE only after a justified continuity/new audit | guest/provenance binding and positive examples; distinguish adapter-only delta from actual derived dependencies |
| evidence metadata/formatting only | MUST REVALIDATE referencing hashes/mirrors; MUST REVIEW meaning; NO ACTION on unchanged runtime content | distribution evidence hash → Python inventory mirror; do not invent fresh host/nm/source audit results |
| actual dependency/license/classification/upstream notices | MUST REVIEW obligations/source coverage; MUST UPDATE EVIDENCE after required audit; MUST REVALIDATE artifacts | pinned original archives, corresponding source, retained attribution and package license bytes; never a blind hash repair |
| Python mirror-only discrepancy | MUST REVALIDATE/reconcile to reviewed source | root inventory/notices are authority, exact mirror test; source may need review if source itself changed |
| public Go/Python API/ownership | MUST REVALIDATE contract/lifecycle/consumers/examples/runtime proof | actual runtime + consumer owners; doc changes do not prove implementation |
| consumer cases/dependency pins | MUST REVIEW coverage, MUST REVALIDATE final artifacts | `consumer_acceptance`/installed-consumer receipt/harness hashes; same name does not imply equivalent failure detection |
| runtime qualification harness/workflow/verifier inputs | MUST REVIEW affected oracles; MUST REVALIDATE exact proof eligibility | shared source inventory and runtime validator; old SHA remains old evidence, strict executable-input mismatch rejects reuse |
| release identity/build/guard/publication tools | MUST REVALIDATE focused negative/identity tests; MUST REVIEW trust changes | shared `git_identity`, release/platform/READY/publication owners; final exact artifacts still require qualification |
| explanatory docs / unchanged historical benchmark evidence | NO ACTION on runtime behavior; MUST REVALIDATE wording/links/content identity where consumed | verification scope follows actual consumers; broad Development unknown-file policy can still conservatively select full checks |

A provenance hash change can mean content changed, JSON bytes changed, recipe
metadata changed or guest changed. Inspect those facts first. Source continuity
can preserve existing attribution without pretending old host audit ran on a new
SHA; changed dependencies/retained attribution may require a fresh audit. The
current positive-symbol check is not an exhaustive legal judgment. Notice and
corresponding-source coverage remain release responsibilities regardless of hashes.

Known failures now have an early owner: omitted glue → independent install test;
direct generated edit → real repository inventory + adapter oracle; stale license
binding/mirror → existing source-only license/mirror suites before compilation.
Someone who changes an accepted identity should run these owners before costly CI.

## Appendix D — Deferred economics changes

| Candidate | Demonstrated issue / potential value | Why not implement in v0.4.5 |
| --- | --- | --- |
| runtime dependency-subset reuse | whole-tree executable-tool changes invalidate unchanged runtime behavior evidence | changing trust scope needs dependency closure and negative proof; material Human Review required |
| stage clocks / compiled test artifacts / protected cache | large unassigned cold build budget | useful v0.5.0 baseline, but no measured command breakdown or safe cache/reuse design here; no broad Fast Feedback redesign |
| generic license continuity record | current Snapshot-specific record couples an historical delta to current identity | new evidence schema is not a cheap hash update; preserve reviewed original facts and defer trust-model work |
| docs/evidence changed-path exceptions | unknown report JSON can select full Development | no blanket docs exemption for potentially executable/consumed inputs; prove consumers first, avoid another hardcoded whitelist |
| delete historical native adapters | several active/import regression callers remain | complete caller/unique-owner migration first; existing extracted helpers already reduce live dependence |
| Snapshot pass fusion | measured repeated logical reads/hashes | optimization not approved; separate bounded identity/lifetime/integrity decision |

No new performance thresholds, automatic cache management, API or release version
is introduced. Compact committed reports/data and Git refs are durable; all task
worktrees/venvs/downloaded logs/caches are disposable after final preservation.
