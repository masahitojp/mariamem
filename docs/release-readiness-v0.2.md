# v0.2 release-readiness audit

Audited on 2026-09-29 at clean main
`9dc577d6bf544bd55503a599621a915c56dc839b`, also available on remote main.
This is a source/evidence audit, not a READY result for a newly built stable
candidate. No artifacts were rebuilt and no tag or release was created.

## Release identity and distribution

The current public release is
[v0.2.0-alpha.1](https://github.com/masahitojp/mariamem/releases/tag/v0.2.0-alpha.1),
an annotated tag resolving to `8b44e9db569c0ea04e45ae6c60fc8ecf54b7b8ab`.
The canonical source, `python/mariamem/_version.py`, still derives that tag and
Python `0.2.0a1`. Python setup metadata and `mariamem.__version__` consume it;
native/wheel/source names and guards derive their versions rather than owning
another editable version. Go module `github.com/masahitojp/mariamem` gets its
release version from Git tags; the private host CLI has no independent public
version interface. There is no stable `v0.2.0` tag or release yet.

If the human selects **v0.2.0**, release preparation must set stage to empty
and serial to zero, deriving Python `0.2.0`, and prepare
`release/NOTES-v0.2.0.md`. Existing stable-version handling does not mark that
release as a GitHub prerelease. This audit does not select or bump a version.

The public alpha has the expected seven uploaded assets: two native archives,
two platform wheels, two platform-qualified corresponding-source archives,
and SHA256SUMS. Their versions are `0.2.0a1`; they are not stable candidates.
GitHub asset metadata/digests were inspected; this audit did not independently
download and rehash all large source archives. There is no release sdist or
PyPI publication path being claimed. Ubuntu wheels use `linux_x86_64`, not a
manylinux compatibility claim. Go requires an explicitly supplied native
bundle; there is no automatic runtime download.

## Findings

Each finding has one classification. Missing future-release artifacts are
preparation work, not evidence of a product defect.

| ID | Classification | Finding / release consequence |
| --- | --- | --- |
| R1 | REQUIRED BEFORE RELEASE | Prepare the human-selected final version, synchronized README/Go/Python/releasing examples and release notes. `Development Status :: 3 - Alpha` in `python/setup.cfg` also needs an intentional maturity choice; a stable 0.x version does not establish production stability or 1.0 compatibility. |
| R2 | REQUIRED BEFORE RELEASE | Correct public Go guide paragraphs claiming Ubuntu acceptance is pending and no Linux release asset exists. Project status still calls v0.1.0 the current release and describes superseded latency references; distinguish historical evidence from the final fixed-reference result. |
| R3 | REQUIRED BEFORE RELEASE | Reconcile historical wording in NOTICE, THIRD_PARTY_LICENSES and guest-source provenance guidance with the current CI release path. Explain which inventory/provenance each record covers; preserve actual incomplete-SBOM/member-map limitations and component terms. Keep packaging notice/license copies synchronized. |
| R4 | REQUIRED BEFORE RELEASE | Build and clean-accept a fresh final candidate with current host/package code and the selected version. Existing alpha archives and tracked historical review files cannot serve as its final acceptance. Both platform guards and aggregate guard must validate exact source, hashes, metadata, corresponding source and external evidence before publication. |
| R5 | DOCUMENT | Support is macOS 15+ arm64 and Ubuntu 24.04 LTS x86_64 with SSE2 + SSSE3. No generic Linux, manylinux, other distro/Ubuntu version, Linux arm64, macOS Intel or Windows claim. Canonical CI uses Go 1.26.8 / Python 3.14; module minimum is Go 1.26.0 and Python metadata says >=3.9. Those minimums and pure-Python wheel tags are not a broad tested-version matrix. |
| R6 | DOCUMENT | Public APIs/examples otherwise match current code and import paths. Snapshot is cold, requires disconnected clients/no unfinished transactions and consumes the source Database on success. Slots are independent; current guest capacity is 16, not a permanent API guarantee; the 17th session gets recoverable MySQL 1040. Interrupted active SQL invalidates the whole Database. Server-side prepared statements are unsupported. 0.x API compatibility remains qualified. Public test RSA keys and default grant bypass are test infrastructure, not a full-authentication/security product claim. |
| R7 | DOCUMENT | Fixed-reference p95 <500 ms passed on the recorded M1/macOS machine; this is not a per-platform or hardware-independent promise. Hosted Ubuntu CPU models span materially different regimes. CPU budgets remain provisional; memory is about 259 MiB/DB macOS physical-footprint and 327 MiB/DB Ubuntu PSS at ×16, not an interchangeable raw-RSS figure. ×16 completion and cleanup passed, but unique ownership within guest/runtime remains unresolved. |
| R8 | DOCUMENT | Prepared Fork gives fresh isolated server state. Testcontainers schema reset shares a server and is a different isolation contract. The local comparison also records two failed 100-container runs without a resolved cause; do not convert those failures into a general incompatibility or marketing claim. Prepared-state benefit depends on fixture/setup workload. |
| R9 | REQUIRED BEFORE RELEASE | Retain current-product normal-check and packaged lifecycle/race/corruption/key-failure evidence alongside final release acceptance. Aggregate READY does not itself run every development/failure-injection suite. Existing two-platform FAST tranche evidence covers unchanged production code; avoid duplicating historical suites for version/docs-only preparation, but rerun relevant checks if product inputs change. |
| R10 | DOCUMENT | Provenance establishes exact inputs and accepted output bytes, not independently rebuilt bit-identical WASM/AOT. Deterministic archive packing of identical inputs is a narrower property. Independent clean acceptance jobs do not constitute independent compiler rebuilds. Hosted images/apt packages, full compiler closure and final archive-member link maps have stated limits. |
| R11 | DEFER | A broad language/distro matrix, post-publication installed-Python smoke beyond the existing exact-wheel prepublication acceptance, wider automatic regression-suite wiring, and stronger independent-build/SBOM tooling are follow-ups; do not weaken any existing source/notice requirement meanwhile. |
| R12 | DEFER | ORM/interface dogfood (GORM, SQLAlchemy, Django, dbt), further restore/latency work, precise memory ownership and sharing/VFS/CoW/continuation architectures are not required to close this release. No speculative experiment code should enter production provenance. |

## Integrity, licensing and release-critical evidence

Project LICENSE/NOTICE/Python license metadata consistently identify project
code as GPL-2.0-only, with original bundled component terms retained. The pinned
lite4mariadb revision is `24be9371a2f6c71250a2356631ad6feab2280b02`.
Wasmer 7.4.2 is mixed-license: Singlepass BUSL-1.1 terms are explicitly shipped
and disclosed; the whole runtime must not be described as MIT or GPL-only.
The wolfSSL election and WASIX libc/LLVM/header sources/notices are retained.
The recorded webc upstream notice-file absence is an explicit reviewed exception,
not permission to silently omit newly discovered obligations.

No unresolved distribution/source obligation was identified in the checked
records. Offline runtime-notice verifiers passed for both platforms (macOS:
509 reviewed packages; Ubuntu: complete inventory, no missing notices), and
the input lock records no known unresolved items. This is an engineering audit
of the existing disclosure/verification model, not a new license interpretation.
A missing required source, notice or unresolved obligation for the actual final
candidate remains a release blocker; historical alpha acceptance cannot waive it.

Release CI builds one common WASM, verifies its handoff to each platform AOT,
and records target/runtime/CPU provenance. Independent clean jobs accept exact
native archives and installed wheels, including external Go consumers. The
aggregate guard requires both platforms, exact candidate source, immutable
artifact hashes and external acceptance evidence. Published source archives
are checked against selected checkout files and the prepared guest inputs;
GitHub's default source ZIP is not their substitute. Publication tags that exact
build commit, verifies uploaded bytes, and runs public-tag Go smoke per platform.
Existing tags/releases cannot be moved or overwritten; NOT READY publishes nothing.

Evidence relevant to current main:

- [Published alpha release CI](https://github.com/masahitojp/mariamem/actions/runs/36317955886):
  both clean platform acceptances, aggregate guard, publication and public Go
  tag/native smoke passed. This establishes the public import/module path;
  pkg.go.dev indexing was not independently tested in this audit.
- [Production FAST verification](https://github.com/masahitojp/mariamem/actions/runs/36522659284):
  both packaged FAST acceptances and lifecycle/integrity integration passed,
  including Go race and Python timeout/multi-client paths. External packaged
  checks exercise prepared-key success/missing/corrupt behavior and bounded
  actual authentication without changing default grant bypass.
- Production files have not changed since that verification implementation;
  differences to audited main are benchmark/test/report files only.
- [Current development checks](https://github.com/masahitojp/mariamem/actions/runs/36540383052)
  passed. Normal checks cover Go unit/vet, Python checkout tests, version/docs
  consistency and public-source selection. Corruption/mutation tests preserve
  mandatory native/snapshot checks and deterministic bounded two-worker errors.
- The push-triggered macOS integration uses an older pinned native baseline;
  it alone cannot establish current guest/package correctness. Current-package
  FAST acceptance and final Release CI provide that distinct evidence. Release
  READY does not substitute for the separately maintained race/negative suites.

Performance/limits are sourced from
[fixed-local acceptance](../benchmarks/final-v02-local-reference.md),
[two-worker verification](../benchmarks/two-worker-verification.md),
[memory/session envelope](../benchmarks/memory-session-envelope.md) and
[practical isolated-test comparison](../benchmarks/practical-suite-comparison.md).
The fixed-local 30-trial distribution was min/p50/p95/max
341.268 / 374.203 / 417.681 / 446.071 ms. One DB with 16 sessions passed isolation,
1040 rejection, reconnect and cleanup; that is readiness evidence for later pool
dogfood, not ORM certification or high-connection scalability.

Audit verification: `.venv/bin/python scripts/verify.py check` passed Go unit
tests/vet, Python **326 passed / 3 skipped**, version/docs consistency and
public-source selection (268 files). Both `runtime_notices.py` and
`linux_runtime_notices.py` passed; `git diff --check` passed. No expensive
integration, release build, benchmark or new CI run was launched for this
documentation-only audit. Existing completed CI evidence was inspected.

### v0.2 release verdict

**READY AFTER RELEASE PREP.** No confirmed product or recorded licensing blocker
was found. A fresh final candidate has not yet been built/guarded; this verdict
does not authorize publication or assert its future guard result.

### Blocking items

None identified in current product/evidence. Final candidate failure of either
platform acceptance, exact identity, corresponding-source or required notices
must stop publication rather than be bypassed.

### Release preparation checklist

1. Human chooses the final version. For v0.2.0, derive Python 0.2.0 from the
   canonical semantic components; update checked current examples and create
   concise stable release notes. Review the Alpha classifier intentionally.
2. Correct stale release/platform/status and notice-review scope text (R2/R3).
   Make measured memory, hardware-dependent performance and narrow toolchain
   validation scope accessible from public guidance/notes, retaining API limits.
3. Run canonical `scripts/verify.py check`; retain the existing applicable
   packaged race/lifecycle/negative evidence and rerun it if production inputs
   change. No new performance optimization or independent-rebuild requirement
   is introduced by this audit.
4. Commit/push focused preparation. Upon an explicit release instruction, use
   the release skill to submit the exact remote candidate to full Release CI.
   Require fresh two-platform assets/source/checksums, version/provenance/notice
   checks, clean acceptance and aggregate READY. Keep evidence external; no
   rebuild after acceptance and no evidence commit. CI owns exact tag,
   publication and public smoke; Codex hands off without polling.

### Deferred backlog

R11/R12: wider compatibility/automation coverage and stronger rebuild tooling;
ORM/dbt workload evidence; remaining restore/memory attribution and larger
performance architectures. Memory cost and hosted-runner variance are documented
limitations, not reasons to resume architecture or cache work before release.
