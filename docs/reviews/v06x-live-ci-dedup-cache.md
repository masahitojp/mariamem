# Live CI deduplication and compiler-cache candidate

The Human requested removing duplicate canonical work and investigating Go cache
reuse on the dogfood candidate, starting at source_commit
`950af59b1d19fd291138d277486ec9f5c3d15db5`. This record describes a CI candidate,
not main adoption or measured performance evidence.

## Actual owners and bounded change

Inspection found Development's `check` on `ubuntu-latest`, but its `integration`
on `macos-15`. Removing both Ubuntu Live invocations would lose Ubuntu runtime
integration. The selected allocation for full PR/main-push diffs is:

| Canonical invocation | Development | Live |
| --- | --- | --- |
| Ubuntu check | retained | duplicate omitted |
| Ubuntu integration | none | retained |
| macOS check | none | retained |
| macOS integration | retained | duplicate omitted |

The Live selector uses the same exact event source/diff as Development and
exports explicit decisions for the two delegatable invocations. Delegation
requires a known shared PR/main event and a full corresponding Development
scope. For tooling/docs scopes, unavailable diffs, experiment pushes and
workflow_dispatch, Live keeps its original local canonical coverage. Existing
guide-only selection is unchanged. Both hosts retain Live race, public Go/Python
browser/failure controls, public runnable examples and installed consumers.
Native references and Python3.11/3.14 cells remain unchanged.

No cross-workflow polling or artifact substitution is added. Protected `check`
and `integration` still own the delegated work; `Live required gate` still owns
the complete selected Live matrix. Protection settings are not modified.
Contract mutations cover missing/wrong owners, reduced scopes, missing conditions,
standalone execution and trigger filters. They use actual Development selector
results, including its runtime reason, rather than invented scope fixtures.

## Cache investigation and policy

The initial experimental Live workflow `ca74140` already set `cache: false`;
the maintained candidate inherited it. Inspection of relevant history and
development/Live records found no explicit reason requiring cold compiler caches.
Absence of such a record is not evidence of a historical intent.

The pinned [setup-go implementation](https://github.com/actions/setup-go/blob/924ae3a1cded613372ab5595356fb5720e22ba16/src/cache-restore.ts)
keys caches by OS, architecture, Linux image family, Go version and dependency
hash. Live enables it for module/build reuse, hashing go.sum and its own workflow;
the native job also hashes native.py to separate its small app cache from the
host job's generated/runtime compilation cache. Neither job restores build/
executables or old result receipts. Host/application builds and embedded exact
source checks remain required. `-trimpath` is retained, but cache correctness
depends on Go's input keys and existing identity checks, not on that flag alone.

The [Go cache contract](https://pkg.go.dev/cmd/go@go1.26.10#hdr-Build_and_test_caching)
distinguishes build objects from successful test results. After restore, each job
runs `go clean -testcache`; Live race invocations additionally use `-count=1`.
Thus cached test PASS is not substituted for execution. Release/Qualification
cache policy, Python/browser installation and native image guards are unchanged.

## Verification and limits

- PASS: focused workflow, public-example and Development selector checks,
  130 passed / 3 existing explicit real-host skips.
- PASS: actionlint1.7.12 for Live and Development workflows (`-shellcheck=`;
  shellcheck not run).
- Scope: workflow/helper/tests/docs only; no runtime/guest/generated changes.
- Pending new CI: actual selected steps, cache restore/save and source-bound
  acceptance. Existing receipts retain their original source identities.

No new local runtime build or performance benchmark was needed for this CI-only
boundary. The change removes two canonical invocations on full PR/main diffs;
minutes saved, warm-cache benefit and wall-clock impact are not yet measured.
The first cache namespace fill can be cold, and cache availability is not a gate.
