# v0.4 Release CI contract migration

Base candidate: `d2cc855b1c8c48343076040ac67946d9e5d288d4`,
branch `v0.4/generated-go-integration`. This changes release tooling, packaging
receipts, notices and documentation; no production Go/runtime/generated source,
public API, guest configuration or canonical benchmark is changed. No workflow,
tag or publication was started. All locally built artifacts are private v0.3.0
version fixtures; the human-selected v0.4 version is still future preparation.

## Contract and ownership

| Boundary | Previous normal release | Current `generated-go-v1` |
| --- | --- | --- |
| Go | native/AOT bundle provisioning and clean-bundle consumer evidence | exact source/module with ordinary generated-Go build input; Options{} direct-link consumer |
| Python | host + Wasmer + AOT/native bundle | platform wheel with linked `mariamem-host` + manifest only |
| Guest build | older SDK/Wasmer-AOT provenance | fresh pinned LLVM23 legacy-EH source builds, canonical WASM and all generated-source equality |
| Corresponding source | platform/native/AOT source records | one common GPL source archive, pinned guest/runtime/header/converter sources and all notices |
| Acceptance | bundle identities | immutable wheel/build/source handoffs, external Go/installed-wheel evidence and source-bound wheel receipts |
| Guard | native platform evidence | exact candidate/hashes/version/notices/harness, both platforms required; no rebuild/publication fallback |

The [release documentation](releasing.md) and repository release skill own the
current handoff. Normal release CI does not download/package Wasmer or generate
AOT/native bundles. Legacy code, source/notices, locks and manual diagnostics
remain; their historical approval cannot approve generated-Go artifacts.

## Local component validation

The [small validation record](../release/evidence/generated-go-ci-migration.json)
binds the component SHAs, artifact/checksum identities and raw-log digests.
Raw logs/private artifacts are under ignored
`build/mariamem-work/release-ci-migration` in the outer workspace. These are
component tests at different development SHAs, **not** one final-candidate READY
record. CI must rebuild and accept the final pushed SHA without reusing or
relabeling this evidence.

- Fresh checksum-installed SDK/LLVM on Linux arm64: two independent source
  builds at `675aa050fc6a8a09cea86ee808fc83a2dbfd5eba`; both linked SHA
  `94b2ae2ba97f424faf419daf4e819f2dfeefc8640b529ae19a98ee3579cb7d1b`
  and post-opt SHA
  `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`
  equal the accepted canonical values. Local replay used an ephemeral Linux
  container with its old SDK removed; production CI installs pinned archives
  on `ubuntu-24.04-arm`, without a local Docker image dependency.
- Updated regeneration launcher at
  `14145820a43835d7412556119613350f46dbee33`: raw converter output matches the
  pinned translation; all 64 installed generated/glue/provenance files equal
  committed source. No manual generated-source patch or hash adoption.
- Source archive: 567,200,836 bytes, SHA
  `87380320c23e24cd83abdecd3af45a7dbfdc4d1ea69c0de229ffbd4e0375fe8b`,
  for the earlier source-build SHA. The updated verifier checks the exact
  members/source/notices/runtime-header license inventories and successfully
  repeats preparation with network disabled. Legacy upstream source archives
  are retained conservatively. This does not independently rebuild the sysroot
  or claim a final linked-file SBOM.
- Host-only wheel built at
  `14145820a43835d7412556119613350f46dbee33`, SHA
  `23701b5cad0d68e976f87d5dd0e25e79786b2a8590e06cbb6387d7dac5d52330`:
  clean VCS revision/complete source receipt; external ordinary Go SQL,
  Snapshot/Fork/isolation/failure/lifecycle acceptance; installed-byte
  serial/parallel/migration/failure-cleanup acceptance; SQLAlchemy **44/44**,
  GORM **32/32**; runtime cache empty. Local macOS is **27.0.1 arm64**, not the
  minimum supported release runner. The guard rejects this as macOS15 evidence.
- Normal `verify.py check` passes (Go test/vet, generated identity, Python
  415 passed/6 skipped, public selection). `verify.py integration` passes
  focused handwritten/runtime race checks, ordinary Go/default Snapshot/Fork
  and Python lifecycle tests. Actionlint and release guard/packaging unit tests
  pass; changed minimum-platform/source-receipt rejection cases remain enabled.

The new pipeline tests exposed and fixed bounded release-tool gaps: flat SDK and
nested sysroot layouts; the PIC legacy sysroot needed by wolfSSL; portable ICU
extraction; empty `/work` and cross-filesystem source staging; raw-translation
manifest selection; offline local-module imports; pip's tool cache being counted
as runtime provisioning. No MariaDB or synchronization change was used.

## Supported-platform verify path

`full` resolves an exact remote SHA, performs two canonical source builds and
regeneration, collects source, builds both wheels, freezes hash-bound handoffs,
and accepts them outside fresh candidate checkouts on **macos-15 arm64** and
**ubuntu-24.04 x86_64**, using Go1.26.8/Python3.14. Private exact-tag Go proxy
transport uses no replace/native bundle. Both platforms check actual host binary
format, missing-host recovery and ordinary SQL/Snapshot/Fork/ORM behavior.
Obsolete AOT-corruption/forced-timeout Ubuntu diagnostics remain legacy-only.

Platform/aggregate guard failures replace stale READY with NOT READY. Missing
platforms, mismatched source/receipts/hashes, stale evidence and unsafe frozen
inputs fail closed. `acceptance-only` requires original immutable handoffs;
`guard-only` also requires an explicit evidence run. Publication only consumes
accepted bytes after explicit release authorization. `verify` never enters
publication, and no write permission is needed for its jobs.

## Remaining release work

The migrated candidate can be submitted to Release CI **verify**, but no hosted
macOS15/Ubuntu24.04 aggregate READY is claimed here. Obtain that evidence for the
exact final pushed SHA, review its corresponding source/notices/provenance,
then prepare the human-selected version/current examples/tracked notes and
reverify the final-version candidate before a separate release instruction.

Known limitations are unchanged: full guest `-race` shared-memory-model work;
non-cooperative forced-timeout/hard-failure reclamation; unsupported
Go1.27.0/1.27.1 arm64; legal ~1s startup tails; macOS physical accounting versus
live Go heap. Focused runtime race checks remain gates; none of these limitations
is suppressed or described as harmless. Legacy Wasmer cleanup, performance,
CoW, MariaDB migration and v0.5 work are outside this task.
