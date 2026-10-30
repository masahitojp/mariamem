# Building and testing

Generated-Go is the only supported runtime since the published v0.4.3 release.
Build products and downloaded inputs live under ignored `build/`. Use Go1.26.10
and Python with pytest/PyMySQL. Prepared runtime integration additionally requires
mysql-connector-python26.7.0 (the release integration consumer pin). macOS arm64
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

Track actionable work in GitHub Issues, grouped by the intended release
milestone (for example, [v0.6.0](https://github.com/masahitojp/mariamem/milestone/1)).
Issues own checklists and acceptance evidence; [project status](project-status.md#current-work-tracking)
retains approved scope and decisions. Keep reference-only accepted limitations
without a release milestone unless work on them is explicitly scheduled.

## Bounded investigations

Human-approved working rule, 2026-10-30, following the P1 process review. Apply
this to resource, performance and architecture investigations. Keep one decision
per investigation and record the following in its existing Issue or short plan;
no new tracker, contract lint or CI job is required.

```text
Decision/question, and the product/documentation action the result will inform:
Fixed workload/environment and necessary observations (including precision):
Exit criteria and what an inconclusive result must report:
Active-work budget / measurement-tooling budget / heavy-CI submission limit:
```

Unless a task-specific budget is agreed, an initial spike has 2 hours of active
work, including at most 30 minutes on measurement tooling, and at most 2 heavy
CI submissions. Tool development, debugging and failure diagnosis count against
the same budgets, including subtasks; failures do not reset them. Limits are
ceilings, not instructions to spend the whole allowance. Record elapsed waiting
separately from active work; label estimates honestly rather than inventing time
measurements. Record a changed budget before continuing beyond the agreed one.

Check that essential observations are feasible with existing tools on a small
case before building the full campaign. Choose precision for the decision: keep
approximate, point-in-time and partial observations labelled; unavailable data
is unknown, never zero or PASS. A collector needing a custom barrier or native
helper is a tooling investment to assess, not an automatic addition to the exit
criteria. Present the limitation, existing alternatives, necessary precision and
additional cost before building another layer or making it a new prerequisite.
Obtain agreement if this expands the recorded scope or budget. Routine fixes
within the agreed bounds remain autonomous.

Progress updates state what became decidable, which exit conditions remain and
whether the work is within budget. A tool milestone alone is not evidence that
the original question is closer to resolution. Batch focused checks before a
stable candidate's heavy CI; use existing verification and evidence-reuse rules.

At a budget boundary, stop adding investigation work, safely stop/reap owned
processes as needed and preserve compact evidence. Cleanup is necessary even if
it exceeds the investigation allowance. Report the conclusion or INCONCLUSIVE,
what is unknown, available decisions, and concrete work/cost to obtain missing
evidence. Ask for additional investment only when needed. An inconclusive report
may close the investigation; it does not complete a product acceptance condition.
Budgets never waive correctness, source identity, required platform coverage or
existing failure oracles. Product acceptance, adoption and release keep their
own gates; do not silently broaden them when measurement tooling is difficult.

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

The development workflow runs on PRs and explicit manual dispatch, without a
main-push repeat. Maintained workflow definitions have explicit tooling scope:
CI-only edits run Python/policy checks without compiling unchanged Go. An
inventory test catches new unclassified workflows; unknown paths and mixed
runtime changes still select the complete daily profile. It selects checks from the local event diff; unknown inputs or
unavailable/empty diffs select all daily product checks plus representative smoke.
This selection produces no reusable runtime-qualification receipt.

| Execution point | Checks | Heavy runtime campaigns |
| --- | --- | --- |
| Documentation PR | version/public boundary and diff | none |
| Classified tooling PR | Python/source policy checks | none |
| Runtime, build or unknown PR change | `verify.py check --profile daily` and Ubuntu `verify.py smoke` | none |
| Release CI (`verify` or `release`) | full integration/race, native SQL, Live, Dump, Django, routing, preparation/migration, final artifacts | both supported platforms and required interpreter/browser/ORM cells |

Daily Go checks cover `.`, `./cmd/...`, `./internal/...` and `./mariamemtest/...`.
`go test` delegates vet to the following explicit vet step. That step retains all
handwritten analyzers; only pure generated `code/pN` packages select build-tag
analysis, using the standard vet tool so dependency facts remain well formed.
`verify.py check` defaults to the full profile for Release/runtime qualification:
all packages (including benchmarks, examples and acceptance programs) and all
applicable generated-code analyzers. No cache hit skips test execution.

The `check` job runs source checks followed by `verify.py smoke` when selected,
using the same checkout and compiler cache. The smoke builds one
host for Python DB/Snapshot/Fork independence and Live connect/mutate/Reset,
stable endpoint and cleanup; Go checks Live reset, busy-session and closed-parent
refusals. It does not install browsers, run native MariaDB, build a wheel or run
race/ORM campaigns. The protected `Live required gate` aggregates source checks
and the selected smoke result; docs/tooling may skip smoke, but failed/cancelled
checks or unavailable selection fail. The protected `integration` context checks
the actual smoke step outcome. Both result gates use job metadata without a
checkout. Daily PASS is not full qualification.

Full Live, Dump, Django, routing, preparation/migration and native SQL workflows
are callable only from Release CI. Every checkout and source-bound receipt uses
the resolved release candidate SHA. Release aggregation requires all six feature
suites, in addition to existing artifact qualification; any failure, cancellation,
skip or missing result stops publication. Full integration owns core/race/fault
regressions; the routing campaign has only its dedicated release owner. No
standalone final-candidate acceptance ceremony is required.

Platform/browser/ORM/fault-specific regressions can therefore be detected later,
at release. This is the Human-approved cost tradeoff. Exact-SHA artifact reuse
also reuses all-six-feature success when its authenticated original receipt
matches the guarded asset set. Without that receipt, the six suites run again;
a valid core READY remains reusable independently.
Eight retired experiment workflows are removed; their reports and source-pinned
workflow links remain historical evidence. Runtime qualification is retained as
a manual-only compatibility path for reviewed runtime reuse.

Archived Go-toolchain/memfs measurement data has explicit documentation scope in
the local selector. Its three saved reproduction recipes have tooling scope;
they are not runtime qualification commands. Unknown code or other evidence
directories remain conservative. Adding these reports must not rerun unchanged
MariaDB integration merely because their JSON/profile summaries are new files.

| Changed boundary | Canonical check | Guest / approximate cost |
| --- | --- | --- |
| ordinary documentation | wording/references/diff; `verify.py check --scope docs` for version/public boundary | no guest, seconds |
| explicitly classified Python tooling/policy and its unit suites | `verify.py check --scope python` or narrower named pytest owners | no real guest; current broad Python subset about 23 s, cold prerequisites vary |
| SDK, SQL, ownership, VFS, guest/generated code, build inputs, unknown files | `verify.py check --profile daily` plus `verify.py smoke`; focused regression when fixing a concrete defect | representative guest; cold compile varies |
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

Development uses one Ubuntu24.04 runner and one checkout for local diff selection,
source/unit checks and selected Go/Python smoke. There is no separate scope runner
or second cold compilation on a smoke runner. Full history remains in that one
checkout for diff and existing fixture-ancestry tests. Documentation/tooling
selection still avoids Go setup and smoke. A failed source check stops before smoke.

The three protected contexts remain `check`, `integration` and `Live required gate`.
`check` owns execution and exposes the selection and actual smoke step outcome.
`integration` checks that the selected execution succeeded; the final gate requires
successful source checks and the exact expected smoke/context outcomes. For docs
and tooling both must be skipped; for runtime both must succeed. Missing outputs,
invalid selection, failure, cancellation and an unexpected skip fail closed.
The two metadata-only jobs install nothing and check out no repository. Tests
execute their actual inline scripts against successful and incomplete outcomes.

The single Development setup-go cache is keyed by runner platform/architecture,
Go1.26.10 and `go.mod`/`go.sum`. Workflow or test-script edits no longer invalidate
that namespace. Go's input-based compiler cache still rebuilds changed packages;
`go clean -testcache` invalidates restored test PASS before any test execution.
Both source checks and smoke inherit the exported `GOCACHE`; no artifact transfer
or trusted prebuilt host is introduced. A cache hit never skips either command.
GitHub cache scope still applies: unrelated PR caches are not interchangeable,
and a first run without an accessible base/current-branch cache remains cold.
No automatic main-push cache-warming build is added.

Local release metadata preparation uses `release_preparation_checks.py` for the
allowed version/docs diff, with no local Go compilation or runtime campaign.
Explicit runtime-reuse intent is authenticated separately before submission.

Full integration/race and the six feature campaigns belong to Release CI. One
shared runtime job per OS builds the wheel while canonical guest reproduction
runs independently. Candidate qualification and Live/Dump/Django/routing/
preparation/native-SQL consume that same wheel/host; no consumer rebuild fallback
exists. Wheel validation binds the source inventory, platform and hashes; extracted
hosts also retain the exact clean-source Go stamp. Full integration accepts only
such a verified host via `--host`. Go example/fixture/consumer programs still build
their distinct executables; those are not replacements for the packaged host.

When features need execution, artifact-reuse modes restore the authenticated
frozen wheel into the shared job.
The artifact is then distributed identically to fresh mode. The final release
still requires both-platform qualification, six feature results and canonical
source/guest reproduction. Shared pure unit/receipt tests run once on Ubuntu for
Python3.11/pytest7 and Python3.14/pytest9. Installed-package and platform runtime
cases remain with each feature. Core full pytest is retained separately.

A fresh aggregate records `release-features-v1` only after shared units, all six
features and both-platform artifact verification succeed. `qualification.json`
version2 points to that original run. Automatic READY reuse authenticates the
original feature ZIP and matches source, complete results and final asset hashes;
then runtime preparation, shared units and six campaigns are skipped. The
aggregate retrieves the original proof again before publication. Version1 READY
or missing/expired feature proof reruns features without discarding valid core
reuse. No copied artifact extends the original 14-day retention. Explicit
recovery modes keep feature execution; `mode=full` forces complete qualification. The runtime build uses the same dependency-keyed compiler cache as
Development, allowing future main-based Release builds to populate it without a
separate cache-warming workflow. Local task-cache ownership remains unchanged.

Publication owns one final semantic guard after authenticated artifact transport.
It downloads the aggregate READY from the evidence run, checks its original
candidate/evidence references, and restores both platforms. Internal transport
helpers validate archive digests and safe paths but do not assert qualification.
The publisher recomputes the aggregate guard once, requires equality with the
authenticated READY, stages those exact assets, and verifies their hashes before
any remote mutation. Existing staging is verified, never silently repaired.
There is no public option to skip the final guard. Other restore consumers retain
semantic checks. Remote tag identity, uploaded-asset verification and public smoke
are unchanged.

Only Development groups automatic PR concurrency by workflow, event and PR number.
A new update cancels the prior run of the same PR; explicit manual runs use unique
run IDs. This does not add main pushes or change Release concurrency.

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

## Live execution frequency

Ordinary PR checks run source/unit verification and selected Ubuntu smoke.
Full Live is callable only from Release CI, alongside the other feature suites;
it has no PR/main/standalone-manual trigger. The former family selector and
Draft-specific full gate remain removed. Required `check`, `integration` (smoke)
and `Live required gate` (daily aggregate) keep their protected names. Their
success is not both-platform full qualification.

The reusable Live workflow checks out `inputs.source_commit` and binds native,
G1, P1, browser and installed-consumer receipts to SOURCE_COMMIT. P1's native
command/callback control and both-host/minor installed-wheel entry acceptance
are retained there, without running on unrelated daily PRs. Release CI requires
the full feature result; no independent final-candidate ceremony is introduced.

P1 has historical both-host/minor full evidence at head8912224a (executed6ccec794,
matching full tree) before PR34/PR35 landed. Those receipts remain at that source.
After integrating the new CI policy, fresh head source/smoke results and the
unchanged P1 product/input boundary are recorded separately; do not call the
updated head's deferred platform/native/browser checks PASS. They belong to a
later explicitly requested Release transaction. See
[P1 gap closure](reviews/v06x-p1-adoption-gap-closure.md).

The former PR-family policy was measured at run40855108044 (head5b27eaf3,
executed538ca001): macOS39m40s including24m25s generic integration. This is
historical evidence, not a saving estimate for the Release-only policy.
