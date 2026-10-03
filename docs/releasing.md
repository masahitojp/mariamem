# Releasing mariamem

The canonical package version is `v0.4.0`; Python spelling is `0.4.0`.
[v0.4.0 is published](https://github.com/masahitojp/mariamem/releases/tag/v0.4.0)
from `39537e9bb2fbbc28315e1ff672960ad734a9e399`;
[Release CI](https://github.com/masahitojp/mariamem/actions/runs/37109036059)
passed both platform public smokes. See [notes](../release/NOTES-v0.4.0.md) and
[current status / roadmap](project-status.md). Future releases require exact-SHA
verify and a separately authorized release operation.

## Exact-source release boundary

**Exact source commit → immutable artifacts → external acceptance evidence →
release guard.** `release-candidate-ready.yml` defaults to `operation=verify`.
Verify has read-only repository permissions and never enters publication.
`dry-run` rechecks publication prerequisites without writes. Only an explicit
human release request authorizes `operation=release`; the existing publisher
owns the exact tag and accepted asset bytes, never a rebuild during publication.

Change only the five semantic components in `python/mariamem/_version.py`.
Stable releases use `STAGE = ""`, `SERIAL = 0` and tracked
`release/NOTES-vX.Y.Z.md`; prereleases use `NOTES-<stage>.<serial>.md`.
Update current README/Go/Python/releasing examples with the derived version.
`check_version.py` rejects stale examples/metadata; historical evidence is not
rewritten. PyPI publication remains unavailable pending account recovery;
GitHub Release wheels are the current Python distribution channel.

## v0.4 artifact contract: generated-go-v1

| Consumer / artifact | Contract |
| --- | --- |
| Go module | Exact source commit/tag; canonical generated Go is ordinary source/build input in the module. `Options{}` direct-links it; no guest executable, NativeDir, bundle/cache or Wasmer download. |
| macOS wheel | `mariamem-<version>-py3-none-macosx_15_0_arm64.whl`; macOS 15+ arm64; `_native` contains only `mariamem-host` and its checksum-bound manifest. |
| Ubuntu wheel | `mariamem-<version>-py3-none-linux_x86_64.whl`; tested on Ubuntu 24.04 x86_64, not a manylinux claim; same host-only layout. |
| Corresponding source | One common `mariamem-<version>-corresponding-source.tar.gz`, covering both wheels and Go source: product source/generated code/patches/scripts, pinned MariaDB/lite4mariadb/dependency sources, WASIX libc, LLVM runtime/header submodule sources, converter source and build evidence. |
| Provenance | `mariamem-<version>-provenance.json`: exact source/guest/generated/toolchain/notices hashes, both frozen wheel records and external acceptance hashes. |
| Hashes | `SHA256SUMS` binds the two wheels, common corresponding source and provenance. Go source identity is bound to the exact tag commit and module fixture inventory. |

These four assets plus SHA256SUMS replace native-bundle/AOT assets on the normal
release path. Existing legacy Wasmer code, notices, locks and historical guard
fixtures remain. Explicit fallback still requires its independently verified
legacy bundle; this release contract does not promise a new fallback bundle.
No legacy evidence substitutes for generated-Go acceptance.

Normal host-only wheels use the explicit notice inventory in
`release/distribution-licenses.json`; they exclude Wasmer engine/BUSL/Rust notices.
The Go module and corresponding-source archive retain repository/fallback source
and notices. Only the external Wasmer engine archive is excluded from the normal
corresponding-source input set; guest/sysroot/runtime/header/converter sources
remain. Original library texts are checked against pinned source archives.
See [artifact license inventory](v04-license-inventory.md). Changed packaging/
notice bytes require new exact-SHA verification; previous READY is not reused.

WASM is a **build intermediate**, not the normal runtime format:

```text
MariaDB/WASIX source → LLVM23 legacy-EH WASM → patched pinned wasm2go
→ generated Go → consumer Go build / platform Python host build
```

Each DB reconstructs fresh execution/thread/TLS/FD state and private writable
files. Snapshot/Fork use prepared files, not ready-heap/live-worker restoration.
Python's installed host links the same guest; Go runs it in-process.

## Build and source/provenance verification

`release/generated-go-toolchain.json` pins WASIXCC 0.4.7, LLVM/LLD 23.1.0,
Binaryen 133, sysroot v2026-07-03.1 **sysroot-eh / sysroot-ehpic**, converter commit/archive and
all downloaded tool hashes. The old `inputs.lock.json` runtime toolchain profile
remains a legacy profile; its source revisions still provide guest dependencies
and WASIX libc/runtime/header corresponding sources.

The build-host job uses [GitHub's Linux arm64 runner](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
to preserve the accepted canonical recipe. It does not add a supported product
platform. `build_generated_guest.py` installs a fresh checksum-verified SDK and
LLVM23 header profile, uses fixed `/work/source` build paths, performs two
independent clean source builds and requires both linked and final WASM hashes
to equal the accepted canonical identities. No local Docker image or hidden
SDK/download is accepted. `regenerate_release_guest.py` applies the three pinned
generator patches and bounded filesystem adaptations automatically, uses pinned
Go1.26.8 formatting, and compares **all** regenerated files (including handwritten
ownership glue) with committed generated source. A mismatch fails; it does not
update accepted hashes.

The legacy-EH intermediate cannot be validated by Wasmer7.4.2. Validation is
independent rebuild/hash equality, exact converter/input/output provenance and
observable SQL/runtime acceptance on the generated-Go path. Exceptions are not
disabled and the guest is not rewritten to satisfy Wasmer.

`release_generated_ci.py source` collects the complete pinned source archives
and preserved notices; `generated_release.verify_source` extracts outside the
checkout, checks every archive/file/version hash and pinned runtime/header
source/license coverage, disables network, and repeats source preparation.
Modified input hashes must equal those used in the actual WASM build. The new
sysroot archive is checksum-bound to its upstream release; this is **not** an
independent rebuild of the sysroot or a final linked-file SBOM. The compiler
LLVM23 revision is recorded separately from the older LLVM runtime source
revision used by that WASIX sysroot. Original source/license texts remain in
full archives. GPL-derived obligations remain independently relevant; historical
Wasmer/source approval is not reused to approve changed bytes.

## CI inputs, reuse, and acceptance

| Mode | Inputs | Work |
| --- | --- | --- |
| `full` (default) | remotely fetchable exact `candidate_ref` | Two source→WASM builds; generated-source verification; common source archive; both host-only wheels; frozen handoffs; both clean consumers; aggregate guard. |
| `acceptance-only` | original SHA, original `candidate_run` | Hash-verified frozen handoffs, new clean acceptance, guard. No rebuild fallback. |
| `guard-only` | original SHA, `candidate_run`, explicit `evidence_run` | Restore exact handoffs/evidence and recheck only. No build or acceptance. |

The macOS `guard-only` reuse path currently rejects the normal `/var` →
`/private/var` temporary-directory alias as a symlink. The
[failed release attempt](https://github.com/masahitojp/mariamem/actions/runs/37108460866)
and reduced helper reproduction confirmed this; v0.4.0 publication used `full`.
Use the verified `full` path until reuse-path hardening is separately accepted.

Artifacts expire after 14 days. Missing/expired artifacts, ambiguous identities,
unsafe archive entries, overwritten files, changed source/version/guest/notices,
missing acceptance or one missing platform produce **NOT READY**. A full run is
required if immutable inputs are unavailable. Reuse executes the exact candidate
scripts; a candidate-script fix needs a new source candidate, not a silent
reinterpretation of old evidence.

macOS acceptance runs on `macos-15` arm64; Ubuntu on `ubuntu-24.04` x86_64.
A private exact-tag Go module proxy transports the **candidate source** without
`replace` or a native bundle. A fresh external Go consumer runs existing
Options{} SQL/Snapshot/Fork/isolation/corruption/failure/lifecycle tests and
GORM32 (Start/Fork, including repeated schema discovery). A fresh external venv
installs the frozen wheel, verifies installed bytes/notices/version, runs the
serial/parallel/seeded/failure-cleanup suite and SQLAlchemy44. Both platforms also check the installed host binary format/architecture and
missing-host recovery. The old Ubuntu AOT-corruption/forced-timeout diagnostics
remain legacy-only; they are not claimed as generated-Go acceptance. Wheel build receipts bind the clean Git commit, complete source inventory and
host Go build-info revision; stale receipts fail even when package/guest versions
match. Both guards bind source, harness, platform and wheel hashes before aggregate READY. Public smoke later downloads accepted bytes and
checks the public Go tag's origin commit; it cannot modify the release.

## Known limitations and release preparation

Full generated guest `-race` remains **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**;
no suppression is used and it is not a v0.4 release gate. Focused handwritten
FD/MemFS/thread/TLS/futex race coverage remains enabled in normal integration CI.
Forced query-timeout reclamation/hard failure containment is not guaranteed.
The ~1s legal guest-side startup tail remains observable. macOS post-Close
physical footprint is not live Go heap and is not claimed harmless or immediately
reclaimable. Go1.27.0/1.27.1 arm64 are unsupported due to the documented upstream
compiler regression; no generated-source/compiler workaround is used.

For each new candidate, submit its exact pushed SHA with `operation=verify` to
collect hosted-runner evidence. Local script tests are not that evidence.
Before release: human-selected version/notes preparation, unused-tag checks,
review source/notices/provenance and **both-platform READY for that exact
final-version candidate**. The release skill owns only preparation/handoff;
CI owns build, acceptance, guard, publication and public smoke.
