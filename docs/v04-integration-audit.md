# v0.4 integration readiness audit

**Historical pre-direct-link audit.** This report preserves the earlier
selected-bundle/subprocess boundary and its then-pending work. v0.4.0 is now
published with direct-link Go and host-only wheels; the classifications below
are not current requirements or a roadmap. See [current architecture](v04-generated-go-architecture.md),
[release contract](releasing.md) and [project status](project-status.md).

Audit source: `a06773e5296be5cc3c3657e9e48785fba7bd6d25`.
This separates the selected local generated-Go candidate from released v0.3.
Architecture exploration is closed. No ready-heap reentry, CoW redesign, runtime
sharing, or new platform work is authorized by this audit. Windows was explicitly
removed from scope; no Windows build or compatibility claim is made.

## Wasmer-era mechanisms

| Mechanism | Disposition | Compatibility decision / implementation status |
| --- | --- | --- |
| Public `Options.NativeDir` / `MARIAMEM_NATIVE_DIR` | REQUIRED compatibility option | Keep explicit override for private/offline/custom bundles. Not required for ordinary tagged Go usage today; an untagged local candidate needs an override. Do not remove this public option. |
| Wasmer executable/AOT loader | LEGACY FALLBACK | Required by released v0.3 and current CI. Selected generated-Go executable does not execute Wasmer. Remove from the generated-Go distribution only after runtime-kind validation and both-platform acceptance exist. |
| Native host/generated guest executable bundle | REQUIRED | Architecture still uses a per-instance guest subprocess. Generated Go does not embed 184 MB of generated source into the public Go module or eliminate platform binaries by itself. |
| Bundle download/cache | REQUIRED | Current public Go module retrieves exact tagged platform bytes. Retain offline cache, concurrent-install locking, archive allowlist, damage detection and integrity. Generated-Go cache keys/manifest contract must include runtime kind/build identity. |
| Exact-version bundle resolver | REQUIRED | Preserve exact Go build/release identity. A v0.3 cache entry must not satisfy a v0.4 generated-Go request. Local candidate labels are not a distribution migration. |
| Artifact/build/Snapshot verification | REQUIRED | Check executables, source/build identity, inventory and Snapshot hashes; keep startup rechecks and immutable prepared-base validation. WASM becoming intermediate does not justify removing trust checks. |
| Wasmer-specific `.wasmu` loader, argv, environment and `wasmer_version` stamp | DEPRECATED for intended v0.4 | Currently used as a local selection bridge, not migrated. Host calls `run`, verification hard-codes filenames, wheel builder stamps Wasmer 7.4.2 regardless of supplied runtime. Must migrate generically before enabling generated Go. |
| Runtime WASM/AOT payload | REMOVABLE from generated-Go runtime distribution | Keep WASM intermediate/hash in build provenance and Snapshot compatibility identity. Today the local candidate still reads/hashes a `.wasmu`-named legacy WASM file to bind compiled code. Do not delete until equivalent compiled-artifact trust exists. |
| Python bundled runtime assets | REQUIRED with updated contents | Python still needs host and generated guest executable plus metadata. Current wheel pipeline remains Wasmer-shaped; runtime-kind manifest, notices, target checks and consumer verification need migration. |
| Wasmer notices/source inventories | LEGACY FALLBACK | Preserve for artifacts that still distribute Wasmer. Generated-Go notices require separate converter/runtime inventory; MariaDB/lite4mariadb GPL-derived source obligations remain independently relevant. |

No option is removed. `Start(ctx, Options{})` remains the target. Setting NativeDir
manually is a local-candidate selector, not the proposed ordinary v0.4 workflow.
Runtime-kind is currently recorded by the candidate script but is not a required
field of `internal/artifacts` or Python verification; filenames/checksums alone
must not be presented as a completed runtime migration.

## Build audit

| Stage | Verified current mechanism | Remaining gate |
| --- | --- | --- |
| MariaDB/dependencies/overlays | `release/inputs.lock.json`, archive digests, `prepare_guest.py`, pristine/modified file hashes | Canonical legacy-mode toolchain provenance must replace the release's exnref sysroot assumption. |
| LLVM/WASIX/Binaryen | WASIXCC 0.4.7; LLVM distribution 21.1.206 (binary reports 21.1.2); Binaryen 133; WASIX sysroot v2026-07-03.1 | Local arm64 Docker image is pinned by ID, but its Dockerfile download path is not a checksum-verified, clean x86_64 release bootstrap. |
| Legacy EH | Supported legacy compiler mode; no wrapper postopt during build; compatible O2 postopt without emit-exnref | Internal bridge only; preserve exceptions/threading. Wasmer 7.4.2 cannot validate this artifact. Static import/feature inspection, generated-code and product behavior are alternative validation. |
| Converter | Fork ac98bcf00c17d8531f0c071a9836d0b50975e7ff; pinned archive; automated imported-memory/function-index patches; Go 1.26.8 | Not included in release inputs lock/CI bootstrap yet. |
| Generated code / shims | Fresh conversion inventory, fail-closed exact adaptations, isolated go.mod, generated source/assembly hashes, compiled guest binding | Production-owned shim package/generation contract and abnormal WASIX behavior still need hardening. |
| Platform artifacts | Local reproducible recipe, `-trimpath`, executable checksums and per-candidate provenance | Current recipe explicitly rejects Linux; canonical Linux build/distribution job and macOS15 acceptance missing. |
| Go/Python distribution | Existing Wasmer release/wheel checks remain | No generated-Go zero-setup package migration, cache invalidation test or generated-Go CI regeneration job. |
| Licensing | Existing notices retained; pinned converter MIT notice added | Generated executable corresponding-source/notices inventory and release review have not been completed. |

`readiness_replay.py` automates a new git-archive checkout, verified source archive
preparation, isolated network-disabled legacy guest build, two converter patches,
fresh translation/inventory checks and candidate creation. It copies no old Go
source/object files. Failure stops and records the exact stage; it never updates
pins silently. Its optional translation-only mode is explicitly partial, not a
source-to-WASM reproducibility result. Local build results and timings are in the
candidate report/evidence. It is not a new release workflow or hidden local build
instruction. A Docker image ID is a replay input, not a portable cold bootstrap.

## Documentation inventory

Current means accurate for the scope shown; historical evidence is preserved.

| Document(s) | Class | Action |
| --- | --- | --- |
| README.md | UPDATE | Link the candidate status; released installation remains v0.3/Wasmer. |
| docs/v04-generated-go-architecture.md | UPDATE | Canonical intended build/runtime split and actual disabled-by-default status; remove the stale unresolved FD gate. |
| docs/project-status.md | UPDATE | Close architecture exploration; record selected prepared-files/fresh execution model and release gates. |
| docs/development.md, CONTRIBUTING.md | CURRENT / UPDATE | Preserve normal commands; add candidate verification tiers and audit link in development guide. |
| docs/go.md, docs/python.md, docs/go-zero-setup.md | CURRENT (released APIs), UPDATE for release | No public API change. Explicit v0.4 status link avoids presenting a local override as released zero setup. Artifact details need updating with the distribution implementation. |
| docs/verification.md, docs/guest-source-provenance.md, docs/runtime-notices.md | CURRENT v0.3 / UPDATE for release | Keep current guarantees; new runtime-kind/source/notice contracts not falsely documented as implemented. |
| docs/macos-compatibility.md, docs/platform-acceptance.md | CURRENT released scope / UPDATE for release | macOS15 arm64 and Ubuntu24.04 x86_64 only. Local newer macOS/emulation do not replace exact release acceptance. |
| docs/releasing.md, docs/source-alpha-publication.md | CURRENT current pipeline / UPDATE for release | Existing workflow is Wasmer; no tag/publication run in this task. |
| docs/sqlalchemy-dogfood.md, docs/gorm-dogfood.md | CURRENT workloads | Retain unchanged SQL/AutoMigrate/schema-discovery acceptance, distinguish current candidate results. |
| docs/guest-start-diagnostic.md | HISTORICAL runtime-specific diagnostic | Keep opt-in Wasmer diagnostic; never charge it to candidate benchmarks. |
| docs/v03-acceptance.md, docs/release-readiness-v0.2.md, docs/release-readiness-v0.3.md | HISTORICAL | Preserve exact released evidence. |
| release/GO-v0.1.0-alpha.1.md, release/NOTES-alpha.*.md, release/NOTES-v*.md | HISTORICAL | Do not rewrite release history. |
| release/NOTES.md | CURRENT v0.3 | Update only during formal release preparation. |
| benchmarks/v04-generated-go-candidate.md | CURRENT candidate | Canonical latest selected-bundle results and readiness verdict. Earlier sections remain clearly dated evidence. |
| benchmarks/wasm2go-feasibility.md, cow-feasibility.md, prepared-clone-feasibility.md, reentry-feasibility.md | HISTORICAL architecture evidence | Preserve GREEN candidate / RED reentry decisions; no new exploration. |
| Earlier benchmark reports and spike READMEs | HISTORICAL / manual diagnostics | Keep measurement boundaries/source identity; not user installation instructions. |
| AGENTS.md | CURRENT repository workflow | Preserve CI handoff and no-publication rules. |

No document is removed as REDUNDANT/REMOVE: historical evidence and distinct
release procedures still serve different purposes. Canonical docs link one audit
instead of duplicating inaccurate implementation claims.

## Test inventory and tiers

| Coverage / paths | Tier | Decision |
| --- | --- | --- |
| mariamem_test.go; internal/artifacts/*_test.go; internal/host/*_test.go; internal/snapshot/*_test.go; internal/timing/*_test.go; internal/guest/*_test.go | fast PR | API/errors, slots, identity/cache/Snapshot ownership and timing unit tests retained. |
| tests/test_python_diagnostics.py; pytest plugin/wrapper tests | fast PR | Wrapper/failure reporting tests retained. |
| tests/test_guest_auth_hooks.py, test_prepared_auth_keys.py | fast PR with pinned-source/native prerequisites | Keep authentication primitive tests; no success inferred from skipped missing inputs. |
| tests/test_guest_provenance.py, test_guest_build_boundary.py, test_ci_guest_source.py, test_runtime_sources.py; test_native_*.py, test_packaging_license_mirrors.py, test_deployment.py | fast PR / build | Existing packaging/provenance checks remain; they currently protect the Wasmer pipeline. |
| tests/test_ci_*.py; test_release_*.py; test_runtime_notices.py; test_linux_runtime_notices.py; test_platform_acceptance.py; test_ubuntu_acceptance.py; test_v03_acceptance.py; test_verification_report.py | fast PR (unit policy checks) | Distinct release/source/trust rules, not equivalent to actual release acceptance. |
| tests/test_*benchmark*.py; test_competitive_benchmark.py; test_final_latency.py; test_go_isolation.py; test_isolation_baseline.py; test_memory_envelope.py; test_practical_suites.py; test_fast_tranche_acceptance.py; benchmarks/goisolation/*_test.go | fast PR harness units | Not performance runs; no latency pass/fail target. |
| tests/test_guest_start*.py; test_init_diagnostics.py | fast PR diagnostic units | Retain diagnostics; actual invasive traces remain manual. |
| tests/gointegration/lifecycle_test.go, multiclient_test.go, timeout_test.go; test_python_multiclient.py, test_python_timeout.py | integration CI | Core SQL/transactions/errors, sessions/MaxSessions, Snapshot/Fork, reconnect, cancellation/fatal-query/Close and cleanup. Rebuild candidate first. |
| tests/integration.py, tests/support/wire_acceptance.py | integration CI | MySQL protocol/auth/CLIENT_FOUND_ROWS and wire failure injection. Keep distinct raw-wire coverage. |
| tests/snapshots.py | integration CI | Snapshot negative paths, transaction rejection, corruption, child isolation and resource ownership. |
| generated-go-integration relative-fd-contract-test.go.txt | integration CI after generation | Keep deterministic rename+name reuse, unlink/nested open/FD reuse regressions; not silently copied into normal package discovery. |
| memfs-growth-test.go.txt, prepared-growth-test.go.txt, prepared-files-test.go.txt | integration CI after generation | Keep growth/truncate/zero-fill, mapped ownership, base/child isolation and partial initialization cleanup. |
| wasm2go/wait-contract-test.go.txt, futex-host-contract-test.go.txt; reduced thread/TLS/atomic fixtures | integration CI after generation | Contract tests remain necessary. Current setup installs base wait tests; full host/TLS fixture matrix is not wired to release CI. |
| tests/consumer/test_sqlalchemy_dogfood.py + run_sqlalchemy.py | integration CI / release | 44 order-balanced assertions on installed wrapper, ordinary SQL/schema/transactions; keep Start/Fork modes. |
| tests/consumer/gorm/dogfood_test.go + run_gorm.py | integration CI / release | 32 assertions, repeated AutoMigrate/schema discovery and lifecycle retained. CLIENT_FOUND_ROWS is covered by raw-wire acceptance. |
| tests/consumer/test_database.py, test_ubuntu.py, zero_setup/acceptance_test.go; tests/verify_alpha.py; scripts/platform_acceptance, ubuntu_acceptance | release acceptance | Exact supported OS, fresh wheel/tagged Go, no runtime override, notices/source and failure cleanup. Local selected-bundle overrides cannot satisfy this tier. |
| v04_candidate.py, v04_orm.py, competitive/practical benchmark commands | benchmark/manual | Fixed environment, slow runs retained, no CI speed gate; x1/x4/x8/x16 cleanup counters. |
| EH/opcode reductions, guest-index wait traces, boundary-variant probes, CoW/prepared/reentry diagnostics, snapshot-audit-patch.json | spike-only/manual | Isolated independent modules; never part of ordinary test discovery or production runtime. |

No tests were removed. The reduced experiments and actual runtime contract tests
are not interchangeable; retaining `.go.txt` fixtures costs no normal Go build
work. A robust CI tier must generate its inputs first rather than depend on
ignored local files. Proposed tiers use the existing `verify.py check`,
`integration`, raw-wire/Snapshot and consumer commands. Current check.yml still
runs only released Wasmer integration; generated-Go CI is an explicit blocker,
not a claimed implemented tier.

## Decision gate

Performance evidence is promising and the FD/MemFS regressions are fixed.
Ready for formal release preparation requires a reproducible cold build,
runtime-kind distribution/trust migration, both-platform product and failure
acceptance, and source/notices review. Until those gates pass, the candidate must
remain disabled by default. Do not turn missing evidence into a weakened API,
verification rule or successful acceptance claim.

## Completed local readiness audit

The final results and retained evidence are in [the canonical candidate report](../benchmarks/v04-generated-go-candidate.md#final-canonical-candidate-and-release-preparation-audit) and [readiness evidence](../benchmarks/v04-integration-readiness-evidence.json). macOS arm64 acceptance and Ubuntu x86_64 container acceptance pass; the latter uses emulation on the reference Mac and does not replace native release CI. Two fresh translations of the accepted guest produce matching generated-source inventories and matching binaries under the same VCS metadata. Complete source-to-WASM regeneration fails the accepted checksum gate and is not approved as an equivalent guest.

Default distribution/runtime selection, generated-Go CI regeneration, native supported-platform acceptance and failure-path hardening remain release gates. No public compatibility option or focused regression test has been removed. Windows is excluded at the user's request. **NOT READY — BLOCKERS REMAIN**.

## Source-build reproducibility follow-up

The earlier LLVM21 checksum blocker is resolved by the pinned LLVM23.1.0 WASM
profile: six independent full legacy-EH builds match, and two generated-Go
regenerations match. [Evidence and recipe](v04-guest-reproducibility.md) record
the upstream MapVector fix, target-header profile, bounded relaxed-madd generator
adapter and new-candidate acceptance. The previous audit remains historical.
Portable/native release CI, default resolver migration, failure-path hardening
and corresponding-source/notices propagation remain open; no release approval
is implied.
