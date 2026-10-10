# Building and testing

Generated-Go is the only supported runtime since the published v0.4.3 release.
Build products and downloaded inputs live under ignored `build/`. Use Go1.26.8
and Python with pytest/PyMySQL; Go1.27.0/1.27.1 arm64 remain unsupported because
of upstream go#81036. Product platforms are macOS15+ arm64 and Ubuntu24.04 x86_64.

## Git source identity

A hexadecimal SHA identifies an object, not necessarily source code. Annotated
release tags have their own object SHA; checkout, archive and measurement inputs
use the target **commit**. The shared tool prints both identities explicitly:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/git_identity.py inspect v0.4.3
python3 scripts/git_identity.py verify-release \
  --pin release/baselines/v0.4.3.json --fetch origin
```

`inspect` is local/read-only. `--fetch origin` explicitly fetches the immutable
tag object, without moving a branch. Do not take the first remote tag-listing SHA
as a source commit. Baseline records use `release_tag`, `tag_object_sha` and
`source_commit`; duplicate, reversed or mismatched identities fail verification.
Library callers use `require_commit()` for exact candidate inputs and
`verify_release_pin()` for release baselines. Update the checked pin once rather
than copying constants among workflows/harnesses.

The runtime-qualification workflow and comparison tools perform this preflight
before tools, builds or performance work. Identity failures should cost Git checks, not a build.

## Local verification

Choose verification from the changed boundary, not the file extension or the
fact that a branch is being merged. Start with focused checks. Expand only when
a focused failure or an actual dependency requires it, and explain the exact
changed-file-to-subsystem dependency before running broader checks.

For experiment-workspace skill/helper/docs/tests changes that do not affect the
MariaDB runtime, generated-Go execution, SQL, Snapshot/Fork or language SDKs:

- Run `python3 -m pytest tests/test_experiment_workspace.py tests/test_release_tools.py tests/test_development_cleanup.py -q`.
- Validate the skill using the available skill validator and check its examples
  and relative links; run the Python tooling checks affected by the diff.
- Run `python3 scripts/check_public.py` and the affected boundary tests. If
  unrelated user files violate the publication allowlist, use a clean worktree
  at the exact candidate SHA; do not remove those files or relax the allowlist.
- Check `git diff --check`, the intended merge diff and Git status. Confirm no
  new tracked/staged or untracked changes remain; report pre-existing user state
  separately and preserve it.

Do not run full `verify.py check`, Go runtime integration, SQLAlchemy/GORM,
Snapshot/Fork runtime acceptance or broad release acceptance for that scope
without a concrete dependency found by focused verification. Documentation-only
changes need wording/reference and diff/status checks, not runtime tests. These
rules leave runtime-change and explicitly requested release gates intact.

The development workflow chooses from a local event diff, without downloading
historical release or Product CI artifacts. Unknown inputs and unavailable/empty
diffs select full check plus integration. This selection is not a reusable runtime
qualification receipt. Explicit release reuse still requires authenticated proof.

Archived Go-toolchain/memfs measurement data has explicit documentation scope in
the local selector. Its three saved reproduction recipes have tooling scope;
they are not runtime qualification commands. Unknown code or other evidence
directories remain conservative. Adding these reports must not rerun unchanged
MariaDB integration merely because their JSON/profile summaries are new files.

| Changed boundary | Canonical check | Guest / approximate cost |
| --- | --- | --- |
| ordinary documentation | wording/references/diff; `verify.py check --scope docs` for version/public boundary | no guest, seconds |
| explicitly classified Python tooling/policy and its unit suites | `verify.py check --scope python` or narrower named pytest owners | no real guest; current broad Python subset about 23 s, cold prerequisites vary |
| SDK, SQL, ownership, VFS, guest/generated code, build inputs, unknown files | full `verify.py check` then relevant `integration` | real guest for integration; minutes plus cold compile |
| final module/wheel packaging and version | installed-consumer/release artifact qualification | exact final artifacts, separate from runtime reuse |
| latency/resource question | one identity-bound manual benchmark after relevant correctness | one campaign at a time; sample dependent |

The [v0.4.5 measured feedback and scope](reviews/v045-human-review.md) records
one cold native qualification at approximately 18 minutes Ubuntu / 25 minutes
macOS, versus seconds for warm focused tooling checks. Queue/build/cache state
varies; these are responsibility boundaries, not latency promises. Measurement
uses OwnedPrepared's Fresh control/capture/import and process counters rather
than the historical native/Wasmer practical-suite orchestrator.

### Generated-source changes: before expensive verification

The installer `scripts/generate_runtime.py` owns adaptation and the
`HANDWRITTEN_FILES` boundary; generated `main.go` is output even though it is host
glue. Edit the canonical recipe first. `verify_generated_runtime.py` reports actual
changed output paths. Independent clean-installer tests derive expected handwritten
files from repository source minus provenance, so a shared list cannot confirm
its own omission. New glue must be carried into clean regeneration.

Full `verify.py check` runs generated/inclusion/adapter, distribution-license and
Python-mirror oracles before Go compilation and excludes those same suites from
later pytest. For a source/provenance repair, the focused source-only check is:

```sh
python3 scripts/verify_generated_runtime.py
python3 -m pytest tests/test_generated_runtime_inventory.py \
  tests/test_distribution_licenses.py tests/test_packaging_license_mirrors.py -q
```

A changed provenance hash requires inspecting the content/input delta, not blindly
refreshing license hashes or performing a fresh attribution audit by default.
Guest/dependency/license changes require review; a justified source-only continuity
record must retain historical audit identities. Reviewed evidence changes may also
require distribution inventory and Python mirrors. Regeneration, runtime behavior,
final artifacts and public distribution still have their own gates. See the
[change-impact/economics review](reviews/v045-verification-economics.md).

### Runtime, artifact and publication responsibilities

Native **Runtime qualification (v1)** uses the existing workflow file
`.github/workflows/v044-product-validation.yml` and
`scripts/validate_product_candidate.py`. The filename preserves its registered
Actions entry; its new receipt contract does not accept old Product CI evidence.
It runs full `check` and `integration` on macOS15 arm64 and Ubuntu24.04 x86_64,
without building release artifacts or running performance comparisons.

Receipts bind the exact commit/tree, every tracked input, guest, toolchain,
commands, native environment, and authenticated artifact IDs/ZIP digests. Both
platforms are required. Runtime receipts are retained for 90 days; expiration
still rejects explicit release reuse. Development uses the local diff selector
and has no dependency on those receipts. No v0.4.4-specific intent is active;
its original bytes are archived as historical evidence.

Final-artifact qualification retains GORM32, SQLAlchemy44, installed pytest/xdist
and normal external Go consumers against the exact candidate module/wheel.
Post-publication smoke first authenticates accepted READY/provenance/asset hashes,
public module tag/commit **and library bytes**, and installed package/host bytes.
Only then does it run minimal Start/SELECT1/Snapshot/Fork/Close, rather than the
ORM suites again. Missing or differing identity stops; it does not downgrade or
mark unexecuted ORM cases passed. Candidate artifact guards still require all
full consumer stages. Publication smoke has a distinct report contract.

Qualification is an explicit CI handoff, not a normal per-change developer task.
After submission, return the run/candidate identity and stop; do not supervise CI.
A cold qualification costs compilation plus both check/integration runs; measure
actual feedback latency before publishing an estimate. Manual measurement is
separate and requires matching correctness first.

Narrow check scopes are explicit scope assertions, not automatic safety proofs.
Do not use them for runtime-affecting inputs. New files default conservatively in
`scripts/development_scope.py` until their responsibility is assigned.

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py check
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py integration
```

`check` defaults to the complete source check: Go tests/vet, checkout Python tests, generated identity,
version consistency and public-source validation. Historical Wasmer fixtures
under `tests/historical` are excluded; they are not a current release gate.
`integration` always uses the compiled generated guest: SQL/auth/sessions,
Snapshot/Fork, lifecycle/memory32 traps, focused runtime/thread/TLS/futex races,
and Python normal Close/multi-client/wire metadata/protocol tests. Retired native/runtime environment
overrides are cleared by the harness; public APIs reject them explicitly.
Installed-wheel SQLAlchemy and outside-checkout GORM remain separate acceptance.

The full generated guest is not Go race-detector clean; do not suppress it or
claim focused tests prove otherwise. See the [race census](../benchmarks/direct-link-race-scope.md).
Forced query-timeout/hard-failure reclamation remains a separate diagnostic,
not part of normal cooperative Close acceptance. The retained diagnostic
`tests/test_python_timeout.py::test_query_timeout_disposes_wrapper` is not a gate.
No force-kill or guest race adaptation is added by runtime retirement.

## Guest / generated source

WASM is a build intermediate; WASIX libc/sysroot and LLVM runtime sources remain
required. Retiring the Wasmer execution engine does not retire those sources,
thread imports, converter or notices. Current exact recipes/pins remain unchanged:

- `scripts/build_generated_guest.py`: two independent source-to-WASM builds on
  a fresh Linux arm64 builder; this is a build platform, not the Ubuntu product.
- `scripts/regenerate_release_guest.py`: regenerate all checked-in translated
  source and compare every byte, including pure-memory32 regression fixtures.
- `scripts/verify_generated_runtime.py`: cheap committed translation identity.

Use the exact-source Release CI for fresh guest/source acceptance. No Wasmer
validator, native AOT compilation or external runtime is used in that path.
`guest/source.patch` stays canonical. Temporary source changes belong only to
`guest/experimental.patch` on experiment branches and cannot pass release provenance.

## Packaging / release dry runs

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/build_alpha.py
python3 scripts/verify.py release-check --ci-candidate-sha <full-sha> --candidate-root <clean-checkout>
```

The builder stages a host-only wheel; legacy runtime/module packaging flags are
rejected. `release-check` only validates/stages accepted bytes, never publishes.
Exact macOS/Ubuntu artifacts, Go/Python consumers, GPL corresponding source,
NOTICE/licenses/provenance and READY are required. See [releasing](releasing.md).
A release request is one exact-SHA CI handoff; historical evidence is not new
candidate approval. Do not wait/poll after successful submission.

## Benchmark / experiment mechanics

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py bench go-isolation --runs 3 --warmup 1 --workers 1
```

No native directory is needed. Measurements remain manual and run alone on the
machine. Preserve useful lifecycle/stage/resource harnesses and historical
reports; reproduce old Wasmer execution with its pinned old tag rather than a
second current runtime. See [benchmark notes](../benchmarks/README.md).

Use independent experiment branches/worktrees and explicit disk/resource guards.
Preserve compact JSON/CSV, final reports and checksums; dispose owned temp/build
outputs after finalization. Confirm shared-cache inactivity, preserve unique evidence, then delete
recreatable caches; regeneration cost is not a KEEP reason. See [workspace cleanup](experiment-workspace.md) and [project status](project-status.md).

## Historical runtime material

The removed legacy guest-build/platform/Ubuntu workflows exist in prior tags.
Native/AOT packaging, provision/cache, Wasmer-specific acceptance and notice
review CLIs are retired and fail with guidance to that history. Their source and
inert fixtures remain reference material, outside current gates. Shared module
identity, platform metadata and authenticated GitHub artifact transport are
retained as runtime-independent helpers. See [Track A inventory](../benchmarks/v043-wasmer-retirement.md).
