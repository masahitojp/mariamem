# v0.4.1 migration debt / toil audit

Static audit from released `v0.4.0`, source **39537e9bb2fbbc28315e1ff672960ad734a9e399**.
No product code, workflow, packaging, license or test was changed. This is a
proposal for human selection, not deletion approval. Tracked inventory is in
[v041-migration-debt-inventory.json](v041-migration-debt-inventory.json).
The post-release direction on main is context, not a source input to this lane.

## Current invariants

Normal `Options{}` selects `host.StartGenerated` → `guest.StartKind(GeneratedGo)` → `guest.startLinked` →
`generatedgo.StartInstance`. `mariamem.go` resolves native artifacts only after
explicit legacy selection. Preserve SQL/transaction/auth/session/lifecycle,
Snapshot/Fork hashes and isolation, directory-FD identity, grow/truncate,
thread/TLS/futex and focused handwritten race tests. Preserve exact source →
immutable artifacts → external consumer evidence → release guard, GPL source,
notices and canonical source/WASM/generated provenance.

## Prioritized findings

| Priority / class | Concrete evidence and candidate | Scope / risk | Recommendation |
| --- | --- | --- | --- |
| P1 CLEANUP | `internal/builtinruntime` has 6 tracked files / 117,304,775 bytes (111.87 MiB), including both encoded images. No Go source outside that package imports it. `Prepare` decodes/checksums/private-materializes an executable that ordinary Start never invokes. `scripts/embed_generated_runtime.py` and the image half of `scripts/verify_generated_runtime.py` perpetuate the old binding. | Small-to-medium, bounded coordinated packaging/provenance/test change; medium trust risk if source verification is accidentally weakened. | Remove dead image delivery after proving no supported path calls it; keep generated-source inventory/guest pin verification. Do not remove the explicit Wasmer launcher. |
| P1 CONSOLIDATE | `.github/workflows/check.yml` integration still downloads the accepted **v0.1.0-alpha.2** Wasmer bundle unconditionally. With its NativeDir env, `verify.py integration` checks legacy integration plus the separate direct-link godefault suite. The old bundle is not necessary for normal v0.4 integration. | Small CI change, low runtime risk, medium coverage risk. | Make default integration bundle-free; retain a clearly named opt-in/scheduled legacy fallback job rather than deleting fallback acceptance. |
| P1 CONSOLIDATE | `benchmarks/v04_orm.py` asserts installed version `0.3.0` and expects an old native manifest. It cannot serve as an unchanged released-v0.4 runner. Several newer candidate/ORM scripts already contain environment and trial capture. | Small runner change, low production risk; measurement boundary must remain explicit. | One version-aware runner with installed host-only manifest validation and immutable scenario identifiers. Keep original raw results/report as historical evidence. |
| P1 CLEANUP | `release_generated_ci.restore_platform` creates an unresolved macOS temporary path; `unzip` rejects symlink ancestors. `/var` aliases `/private/var`, so guard-only reuse can reject its own trusted temporary directory. Full release passed, but guard-only macOS reuse failed during release. | Small targeted trust-boundary fix + deterministic test, low risk if extraction checks stay intact. | Resolve the owned temporary root before extraction; never disable archive/symlink validation. Confirm on macOS plus fixture tests in a separately approved task. |
| P2 CONSOLIDATE | Release candidate jobs invoke check, integration and generated-runtime verification; check already invokes generated-runtime verification. Static source/image checking currently decompresses both obsolete platform images every time. | Small once image cleanup is chosen; avoid conflating local source checks with final-artifact acceptance. | Remove identical repeated verification within one exact-SHA job, retain separate immutable-artifact/source guard and clean Go/wheel consumers. |
| P2 HISTORICAL | `benchmarks/spikes` has 119 files / ~0.97 MiB; historical v0.2/v0.3 readiness reports and v0.4 integration/audit reports describe superseded decision gates. | Small documentation/index change, low risk. | Label historical reports and use `docs/project-status.md` as the only roadmap. Retain race reproducers, provenance/reproducibility scripts and evidence. Do not mass-delete spike tests by filename. |
| P2 CONSOLIDATE | `scripts/verify.py bench` exposes older workload runners but not a common resource-lifetime/crossover/consumer interface. Probe metadata, quantiles, subprocess boundaries, raw paths and comparison calculations are repeated. | Medium tooling work, low runtime risk, medium measurement risk. | Standardize mechanics after these lanes establish useful scenarios; keep generation-soak long-lived boundaries distinct from startup fresh-process boundaries. |
| P2 CONSOLIDATE | `scripts/clean_development.py` safely dry-runs an explicit historical output allowlist, checks ignored/untracked paths, and exports small evidence before apply. Its allowlist consists mostly of named v0.4 build trees; current shared caches/worktrees require a clearer owned work-root contract. | Small-to-medium tooling change, low risk with current refusal gates preserved. | Extend existing command instead of a second deletion tool. Cache, work and evidence must remain separate. Never delete source, Git worktrees or tool inputs through broad globbing. |

Peer review confirmed the dead-image boundary, with two cautions:
`guest.Process`, generic spawn/AbortAndWait and native resolution still serve
Wasmer fallback. `cmd/mariamem-guest` is a diagnostic CLI and current image
entry-binding input; its deletion requires a separate caller audit, not merely
removing encoded images.

## KEEP versus cleanup boundaries

| Area | Classification | Reason |
| --- | --- | --- |
| `internal/generatedgo` (65 files, 205,714,993 bytes) | KEEP | Canonical generated source is ordinary Go dependency/build input, not a disposable runtime artifact. Its size is a measured consumer question, not deletion evidence. |
| `internal/artifacts`, `internal/guest/guest.go`, NativeDir API, native resolver/tests | KEEP | Explicit legacy Wasmer fallback still has an observable contract. Lack of default use does not make it dead. |
| host-only wheel `_native/mariamem-host` + manifest | KEEP | Python needs its installed host executable; `_native` naming alone does not imply obsolete Wasmer packaging. `generated_release.verify_wheel` requires exactly host + manifest. |
| guest build/reproduction scripts, pins, corresponding source, notices | KEEP | Release reproducibility and derived-source obligations remain independent of runtime selection. |
| SQLAlchemy44/GORM32, repeated AutoMigrate, CLIENT_FOUND_ROWS, Snapshot/Fork/lifecycle regressions | KEEP | Current product behavior, not migration ceremony. |
| reduced full-guest race patterns/census and forced-timeout diagnostic | HISTORICAL evidence + KEEP diagnostics | Known limitations remain real; do not suppress races or claim forced reclamation. Full-guest race is not a v0.4 normal acceptance gate. |
| old native-bundle release workflows/acceptance scripts | CONSOLIDATE | Audit each caller and name explicit legacy usage. Product fallback is retained; obsolete default release assumptions can be removed only with equivalent source/trust coverage. |

## Reusable tooling / skill candidates

1. **Cleanup tool + repository skill:** extend `clean_development.py` with an
   owned work-manifest, dry-run by default, cache-versus-work classification,
   exact tracked/ignored/symlink guards, small evidence export and recovered-space
   reporting. A short skill should route inventory → proposal → deletion only
   for authorized disposable outputs; it should call the script rather than
   duplicate shell deletion recipes. Never include arbitrary worktrees or caches
   merely because they are large.
2. **Benchmark runner/report + repository skill:** common exclusive host lock,
   supported toolchain/environment capture, scenario version, source/guest hash,
   fresh-process controls, explicit warm/cold caches, raw JSON checksums,
   nearest-rank quantiles and baseline deltas. The skill should enforce hypothesis,
   budgets and stop conditions before running; it must not equate macOS physical
   footprint with live Go heap, filter slow trials or silently change boundaries.
   Keep a generation-soak mode separate from one-shot startup measurement.

These are maintainer toil investments, not new runtime architecture. No new
skill or cleanup implementation was added in this static lane.

## Verification and decision

Tracked-source import scan, workflow/script caller inspection and inventory JSON
were checked; `git diff --check` passes. No measurements or runtime acceptance
were needed because the diff is report/inventory only. Prioritize dead encoded
images and honest default-versus-legacy CI naming, then runner version/metadata
repair and the bounded guard-only temporary-root issue. Do not automate release,
remove fallback, weaken licensing or merge this lane without the human decision.
