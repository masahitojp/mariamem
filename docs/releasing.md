# Releasing mariamem

The current published release is `v0.6.2`; Python spelling is `0.6.2`.
Its [versioned notes](../release/NOTES-v0.6.2.md) describe shipped scope and
limitations; [project status](project-status.md#additional-062-distribution-169) records
its successful Release CI and public smoke. The procedure below applies to
the next human-selected candidate; preparation alone is not qualification.
A normal release requires one human request authorizing one exact final-version SHA.
An optional `verify` audit never authorizes publication.


## Additional Linux/Windows wheels for published 0.6.2

Publication is complete: [run 43622853054, attempt 2](https://github.com/masahitojp/mariamem/actions/runs/43622853054/attempts/2). Tooling source_commit
`dcb7a9c90684a5ed638322b7d5990647f8763ac6`, product source_commit
`3627e6de6a780dc19195dbbb0331bed42c5de2a0`. Four added wheels are on PyPI;
macOS plus Linux on two CPUs/two libc families plus Windows on two CPUs passed
public install/hash/SELECT 1/Close/host exit. Existing tag and original assets
were retained. The procedure below documents the additive/recovery route;
completion does not require another publication.

The additive route uses the existing `release-candidate-ready.yml` and `pypi`
Trusted Publisher. Set `additional_v062=true`, `candidate_ref` to the exact
maintenance product SHA, and `operation=verify` or `release`. Leave `published_tag`
empty. The workflow/tooling SHA and product SHA are distinct. The product must
retain the engine, guest, wire and SDK of the approved maintenance baseline;
main's later product implementation is not built for this route.

Both operations qualify native Linux x86_64/aarch64 and Windows x86_64/arm64.
Linux installs one CPU-specific wheel on glibc and musl; Windows runs its initial
installed acceptance. The read-only verify operation then checks the additive
publication guard. Release performs the same qualification and guard, appends
missing GitHub/PyPI assets and runs seven short public smoke environments. There
is no new-tag step or second approval after qualification. Existing macOS/Ubuntu
assets and the annotated v0.6.2 tag remain immutable.

Qualification freezes four wheels, their source-bound build/acceptance receipts,
and an additional corresponding-source archive. That archive contains the full
current tracked product tree and the hash-checked original corresponding-source
archive with the dependency inputs, plus extraction instructions. It does not
require a local build folder. Additional source/provenance assets include the
full product SHA in their names and never overwrite the original source bundle,
provenance or SHA256SUMS.

After a partial failure, use `candidate_run` only as an advanced recovery input
pointing to the run holding `additional-v062-<product SHA>`. The workflow validates
its artifact digest, original workflow and exact tooling/source identities;
changed qualification conditions require fresh qualification. It reuses the same
wheel bytes, rejects existing-name hash conflicts, and uploads only missing files.
Successful public smoke cells are reused only for identical wheel/source and
runtime/script conditions. Missing or failed cells are executed again. Without a
recovery run the normal path performs fresh qualification. Publication is not
complete until every expected asset/hash and all seven public smoke cells pass.

## Exact-source release boundary

**Exact source commit → immutable artifacts → external acceptance evidence →
release guard.** `release-candidate-ready.yml` defaults to `operation=verify`.
Verify has read-only repository permissions and never enters publication.
Only an explicit
human release request authorizes `operation=release`; the existing publisher
owns the exact tag and accepted asset bytes, never a rebuild during publication.
CI automatically discovers reusable READY evidence or qualifies the candidate
from source, then publishes after READY and runs public smoke in that same run.
There is no second approval or mandatory verify dispatch. Codex returns the run
URL, exact SHA and operation immediately after submission and stops.

Prepare a human-selected version with the repository release skill. Submit using
`<venv>/bin/python scripts/release_prepare.py submit vX.Y.Z`.
Go 1.26.10 is the 0.6.2 build toolchain (GO-2026-6809); the module minimum
remains Go 1.26.0 and the forward-compat check uses Go 1.27.3.
Already-prepared clean candidates are accepted without another metadata commit.
For an allowed version/docs preparation diff, local submission runs the focused
`release_preparation_checks.py` regardless of runtime-reuse intent. It checks
metadata, source/license boundaries and release tooling without Go compilation
or runtime qualification; Release CI owns those checks. An explicit runtime reuse
intent is still authenticated before push.
For an optional READY-only audit, add `--operation verify`. Run names include the
operation, supplied version and short SHA; display labels never establish identity.

Change only the five semantic components in `python/mariamem/_version.py`.
Stable releases use `STAGE = ""`, `SERIAL = 0` and tracked
`release/NOTES-vX.Y.Z.md`; prereleases use `NOTES-<stage>.<serial>.md`.
Update current README/Go/Python/releasing examples with the derived version.
`check_version.py` rejects stale examples/metadata; historical evidence is not
rewritten. PyPI account access is restored and the Human has registered the
Trusted Publisher for `masahitojp/mariamem`, `release-candidate-ready.yml`,
environment `pypi`. The initial macOS upload succeeded in
[run 43567522416](https://github.com/masahitojp/mariamem/actions/runs/43567522416);
the initial immediate JSON lookup saw the wheel as absent. A later read confirmed
its original SHA256. [Attempt 2](https://github.com/masahitojp/mariamem/actions/runs/43567522416/attempts/2)
completed the initial macOS PyPI publication and installed-wheel smoke.
The later Linux/Windows addition is complete as recorded above; all supported
Python hosts can now install 0.6.2 from PyPI.

## PyPI publication and existing-release backfill

Stable normal releases also run `pypi_publication` after GitHub publication,
then `pypi_smoke`. Both use the dispatch commit's tooling while recording the
original artifact `source_commit` separately. This normal/backfill route retains
its original macOS target. The completed 0.6.2 Linux/Windows addition uses the
separate additive route above; do not infer a future all-platform normal release
inventory from the original macOS helper. The legacy Ubuntu wheel stays on
GitHub, while the additional portable Linux and Windows wheels are on PyPI.

The PyPI job uses `environment: pypi` and job-scoped `id-token: write` with the
pinned PyPA publishing action. No long-lived API token or password is needed.
Configure the matching GitHub environment for the main deployment branch,
without a second reviewer approval after the release decision. Pending publisher
registration is not evidence that OIDC authentication or upload has succeeded.

For the **one-time 0.6.2 macOS backfill**, or recovery of a later stable PyPI
stage, use the same workflow on the reviewed main tooling commit with:

- `published_tag`: the existing stable tag (`v0.6.2` for the first backfill).
- `candidate_ref`: its original full source commit, verified with
  `scripts/git_identity.py verify-release --pin release/baselines/v0.6.2.json`.
- `operation=verify`: read-only preflight, checking tag/provenance/accepted wheel
  hashes and the PyPI inventory. This never uploads and needs no OIDC permission.
- `operation=release`: explicitly approved transfer and installed-wheel smoke.

`published_tag` is an advanced backfill/recovery input, not a required step for
new releases. Do not use `release_prepare.py submit` for an existing-tag
backfill: that command prepares a new release and requires an unused tag.
With this input, qualification/build/tag creation are skipped:
only an already published, stable, checksum-bound GitHub release with matching
both-platform READY provenance is eligible. Do not dispatch the old 0.6.2
workflow or re-label current main as its source. A dry run is optional, not a new
publication approval ceremony. `alpha`, `beta`, `rc` and verify never upload.

The PyPI helper reuses exact GitHub asset bytes, verifies their SHA256 against
SHA256SUMS and accepted provenance, and stages only absent PyPI filenames.
An existing matching hash is reused; a conflict or yanked file stops. Never use
unconditional `skip-existing`, replace assets, or bump a version just because
transport failed. Even an upload-action error is reconciled against the actual
PyPI hashes: a lost success response can complete; missing or conflicting bytes
fail. After upload, an absent file is rechecked up to six times with at most
60 seconds of waiting for public JSON visibility. Hash conflicts, yanks and
HTTP errors fail immediately. A subsequent backfill attempt starts from the same published inputs.
Failures before GitHub has a published release remain the existing GitHub-stage
recovery responsibility; this input never manufactures a missing release.

`ci-pypi-publication.json` records GitHub/PyPI stages, original source, tag object,
tooling commit and hashes. `HASH_VERIFIED` is still `SMOKE_PENDING`; only the
installed smoke makes the PyPI transaction `COMPLETE`. A failed stage retains
its reason. GitHub publication success alone does not mean PyPI completion.

The short smoke uses a fresh venv on macOS arm64/Python 3.14, installs the exact
version from PyPI, checks pip's selected wheel and hash, starts the bundled host,
executes SELECT 1, closes the database and observes host exit. It performs no Go
build, guest generation, ORM or Snapshot/Fork campaign. Completed smoke receipts
can be reused from recent canonical workflow runs only after checking the GitHub
artifact digest, same tooling commit, source, tag, asset/provenance hashes and
smoke conditions. Expired/missing receipts cause another short smoke; changed
conditions never reuse the old success. No new review-document dumps are needed.

## v0.4 artifact contract: generated-go-v1

| Consumer / artifact | Contract |
| --- | --- |
| Go module | Exact source commit/tag; canonical generated Go is ordinary source/build input in the module. `Options{}` direct-links it; no guest executable, NativeDir, bundle/cache or Wasmer download. |
| macOS wheel | `mariamem-<version>-py3-none-macosx_15_0_arm64.whl`; macOS 15+ arm64; `_native` contains only `mariamem-host` and its checksum-bound manifest. |
| PyPI 0.6.2 | Original macOS wheel plus portable Linux x86_64/aarch64 and Windows x86_64/arm64; exact GitHub asset bytes, all seven public smoke environments passed. |
| Ubuntu wheel | `mariamem-<version>-py3-none-linux_x86_64.whl`; tested on Ubuntu 24.04 x86_64, not a manylinux claim; same host-only layout. |
| Corresponding source | One common `mariamem-<version>-corresponding-source.tar.gz`, covering both wheels and Go source: product source/generated code/patches/scripts, pinned MariaDB/lite4mariadb/dependency sources, WASIX libc, LLVM runtime/header submodule sources, converter source and build evidence. |
| Provenance | `mariamem-<version>-provenance.json`: exact source/guest/generated/toolchain/notices hashes, both frozen wheel records and external acceptance hashes. |
| Hashes | `SHA256SUMS` binds the two wheels, common corresponding source and provenance. Go source identity is bound to the exact tag commit and module fixture inventory. |

Portable Linux candidate path (#170): `scripts/build_alpha.py --target linux-x86_64`
or `--target linux-aarch64` produces one CPU-specific wheel with compressed platform
tags `manylinux_2_28_<arch>.musllinux_1_2_<arch>`. The host must be static ELF with
no interpreter, NEEDED library or GLIBC symbol dependency. Runtime discovery checks
CPU, libc version and manifest minimums; it does not identify portability by
Ubuntu release name. The native-runner Linux wheel workflow checks memory/image/
atomic ownership and installs the same wheel in both libc environments for SQL,
Snapshot/Fork independence and Close/cleanup. Image digests, source and wheel hashes
are retained as small CI receipts. Containers share the runner kernel; these runs
do not establish execution on an old minimum kernel.

The initial four-environment acceptance passed in
[CI43574710937](https://github.com/masahitojp/mariamem/actions/runs/43574710937)
on candidate0f3cb82a (CI merge source74ce30e5, identical tree). This is not a
versioned release qualification.

The main source-build path and its initial acceptance above are separate from
the published 0.6.2 maintenance product. The original two-wheel contract above
remains immutable. The additive inventory contains four new wheels:
`manylinux_2_28_<arch>.musllinux_1_2_<arch>` for Linux x86_64/aarch64 and
`win_amd64` / `win_arm64` for Windows build 22000+. It uses
`mariamem-0.6.2-additional-<product source_commit>-source.tar.gz` and a matching
`-provenance.json`; the qualified additional asset map binds their hashes and
wheel hashes without rewriting original SHA256SUMS. Neither these wheels nor
public smoke extend Go v0.6.2's OS support.

`docs/reviews/go.mod` and `benchmarks/go.mod` exclude those nested modules from the
Go module ZIP. Corresponding source still includes the repository inputs and
GPL notices; module delivery exclusion does not remove corresponding source.
The external consumer fixture continues to include the runtime's embedded layout.
See [local benchmark invocation](../benchmarks/README.md) for the separate module.

These four assets plus SHA256SUMS replace native-bundle/AOT assets on the normal
release path. Wasmer runtime, bundle resolution and legacy wheel packaging are retired on the
v0.4.3 release. Prior tags/reports and retained historical notice
fixtures are comparison references, not current runtime or release gates.
No legacy evidence substitutes for generated-Go acceptance.

Normal host-only wheels use the explicit notice inventory in
`release/distribution-licenses.json`; they exclude Wasmer engine/BUSL/Rust notices.
The Go module and corresponding-source archive retain repository and historical reference source
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
files. Snapshot/Fork use immutable prepared blocks with private child
changes, not ready-heap/live-worker restoration. The previous v0.5.0 release used
file-backed prepared state. Python shares one host per root lineage.
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
SDK/download is accepted. `regenerate_release_guest.py` applies the pinned
converter patches (including memory32 bounds, controlled traps and memory
ownership) and bounded filesystem adaptations automatically, uses pinned
Go1.26.10 formatting, and compares **all** regenerated files (including handwritten
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

## Reviewed runtime evidence reuse

`release/runtime-validation.json` is an explicit reviewed intent, not a skip-tests
switch. Version2 pins a successful `runtime-qualification-v1` run, source commit, both native artifact
IDs and ZIP digests. `runtime_validation.py` authenticates the run/workflow/jobs,
internal checksums and full source inventories, then compares the tested source
with the exact release checkout. Unknown changed paths fail closed; only reviewed
documentation paths and the five version constants are exempt; arbitrary tooling changes are not. Runtime,
guest, dependency, build recipe and consumer harness changes invalidate reuse.

The frozen proof records `runtime_basis_commit` separately from
`release_source_commit`. It accompanies each platform handoff and is revalidated
by the final guard/provenance. Old wheels or READY receipts are never relabeled.
Final-version wheels/source, external consumers (including GORM/SQLAlchemy),
notices/licenses, provenance, publication and public smoke remain fresh gates.

For this explicit intent, missing/expired/incomplete/changed evidence stops before
expensive work; there is no automatic runtime fallback. Local metadata preparation
uses `release_preparation_checks.py` and authenticates reuse before main push.
Development CI selects checks from its local event diff and never downloads this
proof. The old v0.4.4 intent is historical; old Product receipts cannot satisfy the
new runtime-only contract. No explicit intent means the existing full release
qualification route; an invalid explicit intent stops.
Remove or replace the tracked intent through review when qualifying changed
runtime inputs. The ordinary no-intent release path is unchanged.

## CI inputs, reuse, and acceptance

| Normal operation | Inputs | Work |
| --- | --- | --- |
| `verify` | exact `candidate_ref` | Automatic reuse or full qualification; stop at READY / NOT READY; never publish. |
| `release` | exact `candidate_ref`, tracked notes | Automatic reuse or full qualification; READY → exact tag/publish → public smoke. This dispatch is the publication approval. |

Heavy product validation belongs here, not in ordinary PR/main CI or a separate
candidate-adoption run. Release calls the full Live/browser/installed, Dump,
Django, routing, preparation/migration and native SQL workflows with the resolved
`candidate_ref` commit. All six feature jobs must succeed before aggregate READY
or publication, or have authenticated exact-READY success evidence as described
below. Failed, cancelled, missing or unexpectedly skipped jobs stop the transaction.
Full core integration/race remains in candidate qualification, with existing
explicit authenticated runtime reuse. Daily source smoke cannot substitute for it.
Release builds one shared wheel/embedded host for each supported OS in parallel
with canonical guest reproduction. Candidate freezing and all six feature suites
consume these exact bytes. `release_runtime.py` validates platform, source inventory,
wheel and host hashes, and the host's embedded clean-source Go identity before use.
Feature jobs never call the wheel builder or silently rebuild a missing host.
Core integration likewise uses the verified shared host. Distinct Go test/example
executables and independent source→WASM reproduction remain separate work.
Artifact-reuse modes restore the original authenticated wheel; they do not rebuild
it. Qualification still requires fresh guest/source reproduction in full mode.

Shared pure routing compatibility, dump policy/binding and preparation receipt
units run once for Python3.11/pytest7 and Python3.14/pytest9 on Ubuntu. Installed
package and platform-dependent cases stay in their feature jobs. Core full pytest
retains its independent baseline.

After complete fresh success, the aggregate saves `release-features-v1` with
source SHA, original run ID, all six feature/shared-unit results and final READY
asset hashes. `qualification.json` version2 references that original artifact.
Automatic reuse validates its GitHub artifact digest, canonical workflow origin,
expiry, source, complete success and exact assets before selecting feature skips.
The aggregate authenticates it again before publication. Old READY without feature
proof, or unavailable/expired/invalid feature proof, reruns features while retaining
valid core reuse. No new copy extends the original 14-day retention. Evidence lost
after selection fails aggregation. Explicit recovery modes still run features;
`mode=full` forces fresh qualification.

`mode=auto` is the default. The planner searches completed canonical workflow
runs in the 14-day retention window (at most 1,000 recent runs), downloads the
hash-authenticated aggregate READY receipt and resolves its immutable handoff/
acceptance run references. Legacy full receipts without references can be reused
only if all inputs validate from that same run. The candidate's own scripts
restore both platforms in disposable scratch and recompute the aggregate guard;
the complete READY record must equal the original, including version, source,
NOTICE/licenses, GPL source, generated provenance, artifact and acceptance hashes.
Only then does CI select reuse. Scratch from a failed attempt is discarded.

Missing, expired, incomplete, corrupted, NOT READY or mismatched evidence is
never reused. Discovery/validation failure selects a full qualification in that
same run. Full qualification retains two independent source→WASM builds,
generated-source verification, GPL source closure, both frozen wheels and both
clean external Go/Python/ORM acceptance suites. After selection, inputs are
authenticated again at restoration, aggregation and publication; a subsequent
change/download failure stops without publication rather than trusting the plan.

With valid READY, frozen-artifact builds and their external consumer acceptance
are reused. With valid feature proof, shared runtime preparation, shared units
and all six feature suites are skipped as well. Without it, those jobs run.
Publication downloads the authenticated aggregate READY from the selected evidence
run and requires its candidate/evidence references to match. Both platform
handoffs retain archive digest and path validation during restoration. The
publisher then recomputes the aggregate guard once, compares the complete result
to that READY and stages/checks the exact asset bytes before tagging or uploading.
Existing staged files are never repaired to hide a mismatch. No public CLI option
bypasses the final guard; ordinary restore/guard commands remain checked.

Within READY selection, reused-platform verification and aggregation, the combined
`restore-guard` command performs authenticated restoration followed by one complete
semantic guard. Failure writes NOT READY, including restoration or staging failure.
Older candidate scripts keep the legacy checked sequence. This does not remove
the publisher's final guard or reuse a successful test result from a Go cache.
Candidate core/race compilation has its own OS/toolchain/source-scoped cache;
tests still run after clearing restored test results. Guest reproduction and
clean external-consumer qualification retain their existing isolation.

For full qualification, core checks start after the shared wheel is ready and run
alongside canonical guest reproduction. Each OS freezes after its own core checks
and guest reproduction succeed, then independently runs external consumers in a
fresh verification job. The final join still requires both OSes and every full
qualification prerequisite. Reuse/recovery skips the full-only core/freeze/guest
jobs and retains both-platform artifact verification. Existing evidence names,
run references, feature acceptance and publication conditions are unchanged.

Hash/source/license/identity checks and the final guard still run; they
bind the accepted bytes to the candidate immediately before publication. Public
smoke always runs after publication on both supported platforms. New aggregate
receipts retain immutable qualification references so later reuse can follow a
reuse run without requiring manual run selection.

Advanced `full`, `acceptance-only` and `guard-only` overrides remain for recovery;
only explicit recovery requires `candidate_run` / `evidence_run`. There is no
silent rebuild fallback in manually selected reuse modes. The publisher's local
`--dry-run` remains available for fixtures/preflight, outside the normal ceremony.

An explicitly approved `operation=public-smoke-recovery` is a read-only advanced
recovery for an already published release whose Ubuntu smoke failed. Supply its
exact `candidate_ref`, original publication `candidate_run`, and a full
`smoke_ref` differing only in `scripts/guest_smoke/main.go`. The workflow uses
the dispatch commit's tooling, authenticates the original successful publication
and immutable receipt, and checks public artifact/module/installed identities
with the corrected program. It records published, smoke and tooling SHAs
separately. It never builds, qualifies artifacts, tags or publishes; normal
operations remain `verify` and `release`. Missing or invalid proof fails closed.

Previously, the documented verify-before-release ceremony repeated builds and
acceptance, while manual reuse required run IDs. In
[this v0.4.2 reuse attempt](https://github.com/masahitojp/mariamem/actions/runs/37380087403),
READY succeeded but publication was skipped: the publication/smoke job conditions
inherited the implicit `success()` check across skipped build ancestors. Explicit
status conditions now permit the reuse path while still requiring successful
resolution, aggregate READY and publication before public smoke. Normal flow is
now one dispatch, with optional prior READY automatically reused.

The macOS `guard-only` path previously rejected the normal `/var` →
`/private/var` temporary-directory alias as a symlink. The
[v0.4.0 failed release attempt](https://github.com/masahitojp/mariamem/actions/runs/37108460866)
confirmed this; v0.4.0 publication used `full`. The generated reuse and public
smoke helpers now canonicalize owned staging paths instead of relying on a
workflow `TMPDIR` override.

Freshly created, owned temporary staging directories must be canonicalized with
`Path(temporary).resolve()` before strict archive destination checks. macOS can
return a system temporary path through `/var` → `/private/var`; that host alias
must not be mistaken for an unsafe archive destination. Keep member traversal,
archive-link, destination-symlink and overwrite rejection intact. The generated
reuse regression tests simulate a symlinked system temporary directory on every
platform, independently of CI `TMPDIR` overrides.

Artifacts expire after 14 days. Invalid inputs never produce READY. In normal
auto mode unusable previous exact-SHA READY inputs trigger full qualification;
explicit runtime reuse intent and recovery fail closed. Reuse executes the exact candidate
scripts; a candidate-script fix needs a new source candidate, not a silent
reinterpretation of old evidence.

macOS acceptance runs on `macos-15` arm64; Ubuntu on `ubuntu-24.04` x86_64.
A private exact-tag Go module proxy transports the **candidate source** without
`replace` or a native bundle. A fresh external Go consumer runs existing
Options{} SQL/Snapshot/Fork/isolation/corruption/failure/lifecycle tests and
GORM32 (Start/Fork, including repeated schema discovery). A fresh external venv
installs the frozen wheel, verifies installed bytes/notices/version, runs the
serial/parallel/seeded/failure-cleanup suite and SQLAlchemy44. Both platforms also check the installed host binary format/architecture and
missing-host recovery. The historical Ubuntu AOT-corruption/forced-timeout diagnostics are disabled
references, not live release gates or generated-Go acceptance. Wheel build receipts bind the clean Git commit, complete source inventory and
host Go build-info revision; stale receipts fail even when package/guest versions
match. Both guards bind source, harness, platform and wheel hashes before aggregate READY. Public smoke later downloads accepted bytes and
checks the public Go tag's origin commit; it cannot modify the release.

Public Go consumers use `GOPROXY=https://proxy.golang.org,direct`; successful
consumer acquisition alone does not distinguish proxy delivery from direct
fallback. After required consumer smoke passes, `ci-public-smoke.json` records a
separate best-effort request to the official proxy's version `.info` endpoint.
The module path comes from `go.mod`, and the version from the authenticated
publication tag. The report includes the HTTP status and version-specific
pkg.go.dev documentation URL. A successful version response is proxy acquisition
confirmation and discovery promotion, **not** confirmation of documentation
listing. pkg.go.dev indexing is asynchronous and remains `NOT_CHECKED` by CI.
The request has a five-second timeout, no polling/retries, and errors cannot fail
consumer smoke or require another release/runtime verification. See the
[official discovery guidance](https://pkg.go.dev/about#adding-a-package).

## Release notes and usage reconciliation

Use [unreleased staging](release-notes/unreleased.md) for changes merged after
the latest published version. Before submitting a human-selected release,
transfer applicable entries to its tracked `release/NOTES-vX.Y.Z.md` (or
prerelease equivalent). Check them against adopted code and name compatibility
changes and accepted limitations. `scripts/release_prepare.py` accepts that
versioned path; it does not consume or generate notes from staging automatically.
After publication, clear transferred staging entries; keep versioned notes and
source-bound receipts as history.

Reconcile README and all current Python/Go/Live/Django/preparation/dump/Node
guides, including example READMEs. Update package installation examples to the
selected version, distinguish newly shipped features from previous releases,
and remove obsolete source-only or integration-pending instructions. Preserve
callback/app-hook responsibilities, exact driver exceptions and unsupported
paths. D1 shipped in 0.6.1; its earlier 0.6.0 deferral is historical.

Documentation reconciliation adds no runtime or packet-capture evidence.
CI still owns exact-candidate qualification and publication. Do not use old
candidate receipts as acceptance of the new version's artifacts.

## Known limitations and release preparation

Full generated guest `-race` remains **GENERAL SHARED-MEMORY MODEL WORK REQUIRED**;
the full generated-engine race run is not a release gate. Focused handwritten
FD/MemFS/thread/TLS/futex race coverage remains enabled in normal integration CI.
Forced query-timeout reclamation/hard failure containment is not guaranteed.
The v0.5.0 ~1s startup mode has a source correction in v0.5.1;
bounded checks passed on both platforms. The subsequent macOS
[Product Verification](../benchmarks/main-product-verification.md) completed 274
executions. Its old slow small resource trial did not recur in bounded repeats;
its cause remains unknown. The maintainer accepted the performance tradeoff and
deferred the adverse 100 MiB Go Fresh result until after v0.5.1 release; this is
not an added release gate. The current runtime releases its
mmap-backed linear memory after cooperative join; remaining Go filesystem/metadata
heap and OS accounting still differ from live allocations. The exact combined
source's external Go1.27.2 consumers passed on both native platforms in
[final Qualification](reviews/main-storage-qualification.md); that historical
qualification used Go1.26.8. Current build/forward-compatibility
pins are Go1.26.10/1.27.3, and minimum Go remains 1.26.0. See
[historical compiler compatibility scope](go-compatibility.md).

For each release, submit its exact pushed SHA once with `operation=release`.
CI collects or revalidates hosted-runner evidence before publication. Local
script tests are not that evidence. Human-selected version/notes preparation,
unused-tag checks, source/notices/provenance and **both-platform READY for that
exact final-version candidate** remain required. The release skill owns only preparation/handoff;
CI owns build, acceptance, guard, publication and public smoke.
