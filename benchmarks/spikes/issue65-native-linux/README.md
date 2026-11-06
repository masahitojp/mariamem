# Issue65 native Linux repeat — prepared, not executed locally

The Human selected Linux -> Live -> compatibility/contracts -> productization/
performance. This step prepares a bounded native Linux x86_64 repeat of the
[macOS3D.1 experiment](../issue65-native-capture/README.md). No fatal-wire contract
choice, Live implementation, production adoption or release is implied.

[The dedicated workflow](../../../.github/workflows/issue65-native-linux.yml)
builds the exact UNQUALIFIED guest on Ubuntu24.04 arm64, then executes on the
native Ubuntu24.04 x86_64 hosted runner. The build host is not product-platform
acceptance. No local Docker x86 emulation is counted as Linux evidence.

The guest must match source_commit5d9915d9940ff691249361aafb6ea39551f29a87 and
SHA256c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf.
The runtime checkout is ecd5d2b7ceff2085cac59f629c36d688007fc6bc. Five Go input
templates are pinned to the immutable Mac final record; the probe also requires
identical Go/assembly/data source hashes, detecting extra files as well as changes.
There is no automatic refresh of guest hashes, worker bindings or case scope.

Acceptance is the same14 cases, the actual adapter's controlled failed-worker/
blocked-peer boundary, the two negative binding controls and21 existing Python
binding tests. Results retain architecture, Go build info, binary/source hashes,
commands, original failures and cleanup. The production guest-index Go tests
remain outside this probe; their compile problem is not reclassified as a pass.
A failed invalid-restore bootstrap is expected negative output; only complete
Go test PASS/case coverage qualifies the run.

Hosted builder/runtime workspaces each have12GiB owned budget/free floor12GiB.
Builder timeout75min/runtime50min are ceilings; the initial active budget is2h,
measurement tooling30min and at most2 heavy CI submissions. The WASM transfer
artifact expires after1day and is deleted by an always-run final job. Unique
compact evidence artifacts retain7days. A mismatched guest is saved as an
unexpected-output observation, never accepted or reused. SDK, downloads, build,
converter copies, generated code, binaries and Go caches are removed by the
owned-workspace helper, including after failures. Empty converter Git metadata
is removed only after comparing all source with the pinned archive plus patches.
A retry starts a fresh full run; disposable transfer artifacts are not a cache.

Local checks validate the acceptance parser, immutable guest rejection, symmetric
source comparison and non-Linux guard with standard-library unit tests, plus
workflow YAML, Python AST, public-source and diff checks. Workflow edits also
require `actionlint -shellcheck= .github/workflows/issue65-native-linux.yml`
(verified with v1.7.12). YAML parsing alone does not check Actions expression
contexts. Set `TASK_WORK` through `$GITHUB_ENV` in a step: `runner.temp` is
unavailable in job-level `env`. They do not execute
Linux or establish a Linux PASS. After successful CI submission, return its URL
and exact workflow/source SHA; follow the repository's CI handoff rule instead
of polling. Later continuation must read actual results before starting Live.
