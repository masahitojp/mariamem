# Building and testing

Generated-Go is the only supported runtime since the published v0.4.3 release.
Build products and downloaded inputs live under ignored `build/`. Use Go1.26.10
and Python with pytest/PyMySQL. Prepared runtime integration additionally requires
mysql-connector-python26.7.0 (the normal-CI selected consumer pin). macOS arm64
external consumers also passed with Go1.27.0/1.27.1/1.27.2 historically;
GO-2026-6809 affects Go <1.26.10 and1.27.0–1.27.2, so the current forward-compat
check uses1.27.3. See [compatibility](go-compatibility.md). Product
platforms are macOS15+ arm64 and Ubuntu24.04 x86_64.

## Scope and completion

Judge completion against the requested scope and exit criteria. Obtain agreement
before reducing them. Report confirmed results and unfinished work accurately.

Methods and priorities may change autonomously when the scope is preserved;
omitting targets or weakening exit criteria requires agreement. Before completion
or Human Review, compare the request with the results. Distinguish inventory,
analysis and verification; if incomplete, open with what remains, why submit now
and how it limits the decision. Answer scope questions directly rather than
replacing them with a demand for universal safety proof.

## Human Review recommendations

Identify **one decision needed from the Human now** before writing. Open with
your short recommendation and decisive reason; incomplete work follows the
[scope and completion](#scope-and-completion) opening rule first. Make the action
explicit: adopt
and implement a candidate, investigate a question, or accept a stated limitation.
Do not combine candidate adoption with later release approval. Codex offers a
grounded recommendation; the Human decides and uses it to explore the evidence
from the PO's perspective. This does not add approval gates to authorized work.

In the opening, include the strongest material objection when a reasonable
alternative could change the decision, followed immediately by why you still
recommend the action or what would change it. Revise the recommendation if the
objection wins; do not invent one for a small decision with no substantive
alternative. State the rationale once. Use user impact before internal terms.
There is no sentence/character limit or required table: the opening alone must
show **what to decide, why you recommend it, and the main concern**.

Link technical evidence, detailed validation conditions and remaining work in
the report afterward. Keep these as author checks, not mandatory opening fields:

- Distinguish facts, inference and unknowns, including specification differences,
  real-workload reachability and reproduced user harm. Translate possible harm
  into user consequences without presenting it as observed.
- Assess likelihood/severity with reasons, not invented probabilities. Compare
  alternative costs and residual risks. Uncertainty does not excuse withholding
  a recommendation or automatically make an issue acceptable or blocking.
- State reversal evidence, bounded investigation scope and exit conditions, including
  what to recommend if inconclusive. General correctness proof is not an indefinite
  gate; finite tests or detector blind spots do not prove the missing property.

Before submitting, check that the opening makes the approval/rejection clear,
any objection helps that decision, and links lead to the evidence and its limits.
Record approved product direction in current decision/status documents; preserve
historical reviews. Format examples do not supersede active technical decisions.

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

Homebrew Python3.14 linked to OpenSSL4 has a known local verification constraint:
fixed Oracle Connector/Python26.7.0 can fail at import with
`AttributeError: module 'ssl' has no attribute 'PROTOCOL_TLSv1'`. CPython's
[OpenSSL4 adaptation](https://github.com/python/cpython/commit/3364e7e62fa24d0e19133fb0f90b1c24ef1110c5)
conditionally omits version-specific protocol constants; this client still
accesses them unconditionally. This standalone import failure precedes any
mariamem connection and does not establish a runtime regression. Record Python,
`ssl.OPENSSL_VERSION` and the original exception. Full local integration remains
FAIL in that environment; use the CI-supported Python/OpenSSL profile for the
fixed consumer gate. Do not synthesize ssl constants, patch the driver or relax
the native profile to report PASS. Current OpenSSL3 CI cannot detect this local
OpenSSL4 constraint. See the [Python driver note](python.md#local-openssl4-and-connectorpython).

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

Documentation-only diffs likewise skip the expensive Live matrix: the Live scope and
required-gate jobs still run and report (they are protected checks), but the native,
browser, guest and installed-consumer jobs are not started. The skip uses the same
documentation classification as the development selector, so any runtime or unknown
path restores the full matrix.

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

### Optional development observations and task-local Go cache

Fast feedback does not qualify a release. Fast = changed-owner tests and a small
real-guest smoke where needed; Focused = relevant correctness/failure boundaries;
Full = canonical check/integration, required native qualification and final release
source/artifact/consumer guards. Omitted initial checks still run at that Full boundary.

The existing commands can write opt-in JSONL phase observations with
`MARIAMEM_PHASE_TRACE` set to an absolute output path. Records include command wall
time, exit/exception, actual Go version for Go commands, source/diff and explicit
input/output hashes. macOS/Linux `wait4` reports user/system CPU and RSS high-water
marks; this is child rusage with OS-dependent descendant attribution, not simultaneous
process-tree memory. Unsupported/unavailable counters are null with a reason.
Parent/child phase records can overlap; do not sum nested intervals/resources.
Observer metadata/hash overhead is recorded separately from command wall time.
Write failures warn and preserve the command result. OFF uses ordinary subprocess
execution, without resource probes or extra hashes. These records are diagnostics,
never a substitute for provenance or qualification receipts.

For one active task, use the existing experiment workspace, not a permanent cache:

```sh
python3 scripts/experiment_workspace.py prepare guest-feedback \
  --branch experiment/guest-feedback --min-free-gib 16 --budget-gib 12
cd build/experiment-work/guest-feedback/worktree
export MARIAMEM_DEV_WORKSPACE="$(cd .. && pwd -P)"
export MARIAMEM_PHASE_TRACE="$MARIAMEM_DEV_WORKSPACE/evidence/phases.jsonl"
export GOTOOLCHAIN=go1.26.10
export GOCACHE="$MARIAMEM_DEV_WORKSPACE/temp/gocache"
export GOPATH="$MARIAMEM_DEV_WORKSPACE/temp/gopath"
export GOMODCACHE="$MARIAMEM_DEV_WORKSPACE/temp/modcache"
python3 scripts/experiment_disk.py --work-dir "$MARIAMEM_DEV_WORKSPACE" \
  --min-free-gib 16 --budget-gib 12 --timeout 1200 -- \
  python3 scripts/verify.py check
```

Choose the actual changed boundary before running that full check. `verify.py`,
regeneration/translation and wheel host-build callers also derive these cache paths
when only `MARIAMEM_DEV_WORKSPACE` is set; conflicting paths, other checkouts,
completed workspaces and symlinked cache roots are rejected. Direct Go commands
need the explicit exports above. Go keys compatible build results; race/CGO/flags,
toolchain and platform changes still cause needed work. External cgo inputs may
require explicit invalidation. Generation/provenance checks remain mandatory for
their changed boundary; the Go compiler cache cannot validate a stale guest recipe.
Host binaries are rebuilt through Go, not reused because an old file exists.

Focused commands can use the same existing verification runner for observation:

```sh
PYTHONPATH=scripts python3 -c 'from verify import run; run(["go", "test", "-p", "1", "./internal/snapshot", "-count=1"])'
PYTHONPATH=scripts python3 -c 'import sys; from verify import run; run([sys.executable, "-m", "pytest", "tests/test_build_feedback.py", "-q"])'
```

Unset `MARIAMEM_PHASE_TRACE` to disable observation; unset workspace/cache variables
to return to the previous cache defaults. Do not opt Release/runtime qualification
into this developer cache path; existing isolated qualification environments and
guards remain authoritative. Use the existing workspace disk guard for expensive
commands and finalize/cleanup after preserving compact measurements. A manually
supervised prepared workspace can use this disk guard for each iteration; alternatively
`experiment_workspace.py run` supervises one whole campaign and then completes it.
Do not reuse a completed receipt or retain the task cache after completion.
See [phase 1 evidence](reviews/v05-fast-feedback-phase1.md) and the
[approved dev guest design](reviews/v05-dev-guest-build-design.md) and
[implementation validation](reviews/v05-dev-guest-build-validation.md).

### Maintained CI ownership and compiler caches

For full PR and main-push diffs, Development owns the Ubuntu canonical `check`
and `integration`; Live retains macOS `check` and `integration`, both-host Live
race tests and the native/browser/installed matrix. The required `integration`
context keeps its name and now runs on Ubuntu24.04. Live skips its duplicate
Ubuntu integration only when the same event/source has full Development coverage.
Live derives delegation from the same event diff and selector as Development.
Reduced Development scopes, unavailable diffs, manual runs and experiment pushes
keep local canonical invocations.

The original Development integration used a published macOS native bundle
at commit `0a66842`; that dependency was removed with the legacy Wasmer path at
`c2ebc0a`. The current `verify.py integration` has no macOS-only requirement and
is also used on Ubuntu by Live and qualification workflows. To reduce contention
for macOS runners, its standalone required job moves to Ubuntu and macOS coverage
is consolidated into the already selected Live host job. The historical
[Live allocation](reviews/v06x-live-ci-dedup-cache.md) describes the prior owners.

The three protected contexts remain separate:
`check`, `integration`, and `Live required gate`; the Live gate alone does not
attest the delegated Development jobs. The paired workflow contract tests detect
changes to their owners, commands, triggers and conditions.

Dump uses the same canonical delegation selector as Live. Its additional Ubuntu
`check` and Ubuntu `integration` run only when Development does not own the full
corresponding check for the event. Native reference and dump comparisons remain
independent of this selector. Missing/empty diffs and standalone events
retain local canonical runs. Dump success alone does not attest the delegated
Development checks; the protected Development contexts still decide those checks.

Connection routing likewise delegates its generic Ubuntu `source` check only to
full Development coverage on the same main-push event/source. Its scope job uses
the shared selector; reduced/unavailable diffs, feature pushes and manual runs
retain the full local check. The dedicated native matrix explicitly accepts
`source=skipped` only alongside a successful scope selecting delegation and
successful compatibility cells. Scope/source/compatibility failure or cancellation
cannot select native acceptance. Both native OSes and compatibility Python versions
remain unchanged. This workflow still runs on its existing push/manual events.

Dump guest-comparison and Django recipe select Ubuntu only for pull requests.
Main pushes and manual `workflow_dispatch` runs retain Ubuntu and macOS (as do
Dump experiment pushes). This removes three candidate macOS matrix jobs per PR
when both workflows are selected, while both Python versions remain tested.
Their macOS-specific failures can therefore be detected after merge; main-push
success is not a pre-merge gate. The Human requested this placement to reduce
macOS runner contention. The Human verifies macOS during local development,
so platform problems can be found before CI. Required Live macOS checks are
retained; Development's required integration uses Ubuntu. With both candidate
workflows selected, PRs now need one macOS job (Live) instead of the previous
five (Development integration, Live, Dump and two Django cells).
Release CI does not automatically invoke these two dedicated campaigns; when
separate pre-release evidence is needed, dispatch these workflows at the exact
candidate SHA. Their main path filters still determine which pushes run them.

Development, Dump, Django and Live use setup-go's GitHub-managed module/build
cache. Each Go job exports its actual `go env GOCACHE` through `GITHUB_ENV` so
later wheel builds inherit that cache instead of selecting `build/gocache`.
Development check/integration and Dump comparison/check/integration have separate
cache namespaces to avoid competing to save different compilation workloads.
Django builds one source-stamped host per selected OS and sequentially runs both
Python versions against that binary. Each interpreter retains its own pinned
native reference, dependency report and acceptance output. Both acceptance calls
are attempted even if the first fails, and either failure fails the job. The
shared job budget allows one build and both unchanged per-case deadlines; native
references remain independent Python matrix jobs. Scratch cleanup does not remove
the compiler cache before setup-go saves it. Compiler paths are
runner-managed; scratch budget guards do not account for these compiler caches.

The pinned setup-go action keys entries by platform, architecture, Go version
and declared dependency hashes; the workflow is included in those hashes, with separate native
and host namespaces. Restored test results are invalidated with `go clean
-testcache`, and explicit race/integration invocations retain `-count=1`. Candidate
executables are still built through Go and checked against their actual embedded source identity.
This does not reuse an old PASS receipt or a packaged host. Release workflows and
local task-cache lifecycle are unchanged. Cache misses execute ordinary builds;
these runs make no cold-setup or measured speedup claim. See the
[CI change record](reviews/v06x-live-ci-dedup-cache.md).

These four maintained PR workflows group concurrency by workflow, event and PR
number. A new update cancels only older runs of the same PR in that workflow.
Main pushes, experiment pushes and manual runs use unique run IDs, so unrelated
or pending non-PR runs do not replace each other. Release/Qualification concurrency
and cache policy are unchanged.

### Archived CI efficiency observations

[PR12 observations](reviews/ci-efficiency-pr12-observations.json) retain metadata,
checkout source identities, compact cache log matches and input digests for all
four workflows in two completed executions. The heads are `5304c1b` and `5a6bbd1`;
the actual checkout commits were `7f98b74` and `babed7d`. The heads/configuration
and actual checkout source are deliberately separate. The two sources differ by
the merged release-scope documentation, with the CI/runtime/test inputs unchanged.
These are observations of the same PR12 configuration, not before/after proof of
the follow-up changes described above.

| Observed PR12 cohort | PR wall time across four workflows | Sum of occupied job wall times | Maximum dependency-ready-to-start delay |
| --- | --- | --- | --- |
| 5304c1b (several compiler-cache misses) | 55 min 1 s | 119 min 36 s | 5 min 4 s |
| 5a6bbd1 (all selected Go jobs restored caches) | 15 min 48 s | 50 min 47 s | 5 s |

Development's check/integration first missed and saved their separate keys, then
restored the same keys on the next execution. Test-result invalidation and the
actual test steps succeeded on both. Live and Dump likewise supply miss/save and
later restore observations; Django restored its earlier key in both cohorts.
Django's cold miss is not established by these two observations. Build and
source-bound consumer acceptance still succeeded with caches present or absent
where those states were observed.

The job-wall sum is an unweighted occupied-runner proxy, not billed minutes.
Ready-to-start begins after all declared dependencies finish and includes
scheduler/provisioning delay; it is not a pure account-queue measurement. Queue
conditions, compiler state and runners vary between samples, so the observed
wall-time difference is not a controlled cache-only speedup or future guarantee.
The new Django/routing follow-up still needs its own CI confirmation and timing.

Reproduce the offline summary by downloading each recorded run's JSON and log:

```sh
gh run view RUN_ID --repo masahitojp/mariamem --json databaseId,headSha,workflowName,event,status,conclusion,createdAt,startedAt,updatedAt,url,jobs > run.json
gh run view RUN_ID --repo masahitojp/mariamem --log > run.log
# Save each pair separately as development.*, live.*, dump.* and django.*.
# Supply all four workflows for one head; repeat the four pairs for the second head.
python3 scripts/summarize_ci_efficiency.py \
  --run development.json development.log --run live.json live.log \
  --run dump.json dump.log --run django.json django.log \
  --output build/ci-observations.json
```

The summarizer requires a complete four-workflow cohort, rejects unknown DAG
jobs and preserves skipped jobs without counting them as occupied runners. It
never fetches, reruns or qualifies CI. Keep each input pair/run separate when
repeating the download commands; the JSON receipt lists all eight run IDs.

### Single-pass unqualified guest development

This is a developer route, not a release qualification command. First prepare
an owned experiment workspace and commit the exact source/patch/tool inputs.
Use a fresh Linux arm64/root builder with the existing build prerequisites,
empty `/work` and no existing `/root/.wasixcc`. Source can be mounted read-only,
with a writable task build staging directory. If overriding the `build/` mount,
carry the tracked `build/go.mod` into it unchanged.

```sh
# In that fresh builder; both paths must be absolute.
export MARIAMEM_PHASE_TRACE=/absolute/task/evidence/guest-phases.jsonl
python3 scripts/build_generated_guest.py \
  --development-output /absolute/task/temp/dev-guest
```

Do not specify `--repetitions`: development performs exactly one build. Default
execution without this option remains the accepted two-build Release recipe.
The dev output contains observed WASM, linked WASM and `guest.json` marked
`development-unqualified-v1` / `UNQUALIFIED`, plus actual compiler/source/patch
identities. Matching the accepted hash does not qualify a single build.

Copy/preserve those bound files and the exact clean source checkout. On a
supported native product platform, activate pytest/PyMySQL, choose Go1.26.10 and
set the task cache environment documented above:

```sh
export MARIAMEM_PHASE_TRACE="$MARIAMEM_DEV_WORKSPACE/evidence/native-phases.jsonl"
python3 scripts/regenerate_release_guest.py --development \
  --guest-dir "$MARIAMEM_DEV_WORKSPACE/temp/dev-guest" \
  --output "$MARIAMEM_DEV_WORKSPACE/temp/dev-native"
```

The output must be fresh, outside the source checkout and outside reserved
Release/canonical namespaces. The existing converter/adapter/installer produce
an isolated source copy; old generated source and native binaries are excluded.
Only the copy's guest compatibility constant is bound to the observed dev hash.
The route builds a fresh host, checks its identity, then explicitly selects the
small SQL/transaction/Snapshot/Fork/Close test. `development.json` is emitted
only on complete success and remains UNQUALIFIED. `failure.json` records failed
generation; partial output is never a completion proof.

Guest-origin and host-stage identities are recorded separately. With unchanged
source, all tracked bytes and the commit are verified directly. A later clean
commit may reuse a guest only when differences are confined to docs/tests and
three host-stage scripts (`dev_guest.py`, `generate_runtime.py`,
`regenerate_release_guest.py`). Changed original bytes are verified against the
actual historical Git tree; the native stage is independently bound to its
current clean tree. Guest preparation/build/patch/tool inputs, other scripts,
and Go source changes require a fresh guest. No receipt is relabeled or promoted.
This narrow boundary permits fixing the host pipeline without repeating the C
build; it is not a general cross-commit artifact cache. Valid downloads and Go
compiler cache can be reused within the active task; discard failed/partial
C and translated output before retrying.

Before Release adoption, accept the exact source/recipe and perform independent
clean two-build reproduction, accepted input verification, current runtime/race/
trap/platform checks and final consumers/source/license/artifact guards. Dev
receipts cannot substitute for any of those guarantees. Preserve compact result
records and delete task SDK/source/object/product/cache/container state afterward.

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
GOTOOLCHAIN=go1.26.10 python3 scripts/verify.py check
GOTOOLCHAIN=go1.26.10 python3 scripts/verify.py integration
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
thread imports, converter or notices. The canonical guest input is now MariaDB 12.3.3; the v0.4.7 converter and
toolchain pins remain unchanged. See the [integration record](reviews/v050-ad-integration.md).
Canonical commands:

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
GOTOOLCHAIN=go1.26.10 python3 scripts/build_alpha.py
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
GOTOOLCHAIN=go1.26.10 python3 scripts/verify.py bench go-isolation --runs 3 --warmup 1 --workers 1
```

No native directory is needed. Measurements remain manual and run alone on the
machine. Preserve useful lifecycle/stage/resource harnesses and historical
reports; reproduce old Wasmer execution with its pinned old tag rather than a
second current runtime. See [benchmark notes](../benchmarks/README.md).

Use independent experiment branches/worktrees and explicit disk/resource guards.
Preserve compact JSON/CSV, final reports and checksums; dispose owned temp/build
outputs after finalization. Confirm shared-cache inactivity, preserve unique evidence, then delete
recreatable caches; regeneration cost is not a KEEP reason. See [workspace cleanup](experiment-workspace.md) and [project status](project-status.md).

## Guest patch maintenance

Guest portability maintenance follows the approved
[common plus source-specific patch policy](decisions/guest-patch-management.md).
Use its inventory and review fields when updating MariaDB inputs or removing
upstreamed fixes; distinguish source-application evidence from runtime qualification.
`guest/input.json` binds the sole adopted source/archive, six lite4 recipe files
and ordered portability patches with preimage/postimage hashes. `prepare_guest.py`
rejects changed inputs and applies portability then canonical source.patch without
fuzz. Release provenance compares that descriptor/series with the actual build.

## Historical runtime material

The removed legacy guest-build/platform/Ubuntu workflows exist in prior tags.
Native/AOT packaging, provision/cache, Wasmer-specific acceptance and notice
review CLIs are retired and fail with guidance to that history. Their source and
inert fixtures remain reference material, outside current gates. Shared module
identity, platform metadata and authenticated GitHub artifact transport are
retained as runtime-independent helpers. See [Track A inventory](../benchmarks/v043-wasmer-retirement.md).
