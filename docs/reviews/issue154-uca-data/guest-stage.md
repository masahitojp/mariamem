# Issue154: first actual guest build and source-only translation

The Human requested continuing after source prototype `5706d719`. This increment
uses the existing single-build development route. It produces one real candidate
WASM and its source-only Go translation for the next execution gate; it does not
claim that a guest has executed successfully.

The first inspection found an unavoidable dependency: the canonical Go installer
requires the accepted guest SHA and exact worker allocation/reclaimer and CRC
function/data bindings. The experimental guest necessarily changes its SHA and
may move functions/data. Running normal regeneration now would fail that guard.
Do not override its SHA, weaken it, or submit a job known to fail at installation.
Instead obtain the exact translation, report existing body/data anchors, and then
review the correspondence needed for installation. A missing/changed anchor is
reported as a mismatch; it is never fuzzy-matched into acceptance.

## Fixed budget and handoff

- One heavy CI submission, one C guest build on Linux arm64/root, existing pinned
  toolchain and `--development-output`; timeout100 minutes. These are ceilings,
  not an estimate of elapsed time. No second reproducibility build.
- One Ubuntu24.04 x86_64 source-only translation/adapter job, Go1.26.10,
  timeout45 minutes; no generated-host build, guest execution or server service.
- Active preparation ceiling2h/tooling30min. No local full runtime build or
  performance campaign. Source work remains on `experiment/uca-default-init`.
- Manual workflow dispatch is available; initial submission is a push restricted
  to that exact experiment branch and the workflow/patch/translation-owner paths.
  Docs-only pushes do not repeat the expensive build.
- On submission, return the exact source/run URL and stop; no CI polling.

`uca-copy-experiment.yml` is separate from the canonical UCA/timer workflows.
Its source identity must equal `GITHUB_SHA`, the checkout must be clean, and the
build must report one repetition plus the experimental patch and the explicit
`development-unqualified-v1` / `UNQUALIFIED` contract. Guest downloads remain
bound to source-SHA artifact names and the existing verifier checks their source,
patch, toolchain, WASM and linked bytes before translation.

`tests/uca_copy_translate.py` uses the existing pinned converter and source
adapter, verifies their inventory, and records worker/CRC anchors without
changing `runtime_thread_lifetime.py`, `runtime_crc32c.py`, their hashes or their
acceptance logic. The artifact result is deliberately
`UNQUALIFIED_TRANSLATION_COMPLETE_BINDING_REVIEW_REQUIRED`, even if all inspected
anchors match. No runtime acceptance, native SQL, performance, Qualification or
publication follows from a green workflow.

The full generated source is kept in a short-lived CI artifact for inspection,
not committed to the repository. Later receipts must retain exact run/job/artifact
identities and compact conclusions/checksums; routine logs and full REST payloads
stay outside main. Source-only prototype data and its receipt remain under their
original source identities.

## Local verification and next action

The six new read-only binding-inspection cases plus existing dev-guest identity
and development-scope cases pass:125 tests. Mutated/missing function bodies,
changed/moved CRC data are reported as mismatches, and successful inspection
leaves original files and accepted guest identities unchanged. YAML, embedded
shell syntax, explicit one-build selection and diff checks also pass. No new
runtime result is claimed by these local tests.

After the run, inspect the complete binding evidence. Resolve any body/data
changes with exact comparison and an explicit bounded experimental binding;
then execute actual full-table checks/corruption/profiling separation, native
MariaDB SQL comparison, alias/variant order, two children, reSnapshot/disposal
and failure handling. Mac/product adoption and observer-off Pipe P4/P8 timing
remain later gates. This staged dependency changes the next submission, not
Issue154's correctness/performance exit conditions.

## Bootstrap failure and bounded network correction

Run [43034233695](https://github.com/masahitojp/mariamem/actions/runs/43034233695)
at source `d9363eae9f673e77d7a2318da93616fd365f6073` failed before checkout/build:
`ports.ubuntu.com` could not be resolved inside the job container. Attempt1
job130568790900 and attempt3 job130580523116 show the same failure; translation
was skipped. These are infrastructure failures, not UCA correctness results.
Repeated retry has not resolved the observed problem. The logs do not establish
whether the fault belongs to Docker DNS forwarding or upstream DNS.

The bounded correction retains the exact image digest, arm64 runner, root user,
dependency set, source/patch guards and one-build UNQUALIFIED operation. It runs
the fixed builder explicitly with Docker's Linux
[host network](https://docs.docker.com/engine/network/drivers/host/), bypassing the
job-container bridge path. Runner and builder name resolution are checked with
20-second bounds; resolver evidence and bootstrap output remain CI artifacts.
APT update uses error-mode=any and two acquisition retries, so a failed index
fetch cannot continue into misleading package-not-found errors. No hardcoded
server IP, alternate package origin, guest/runtime change or acceptance bypass
is introduced. The existing build100m/translation45m ceilings remain unchanged.
The Human's new failure report authorizes this one corrected submission; the
prior failed run is not relabeled. Success of this workaround remains unverified
until the corrected CI executes. No additional local guest build is needed.

Local checks pass for YAML parsing, runner/inner-builder shell syntax, unchanged
image/dependencies/build guards/translation, and mounted artifact paths. The diff
is restricted to this workflow and diagnosis record; no runtime tests are rerun.
