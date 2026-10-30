# EP1 / EG1 supplied E2E entry — implementation proposal

Decision requested: approve implementing the bounded Python browser and Go HTTP
entries described here, at `readable-owned`, using existing Live. Recommend this
shared lifecycle with language-specific test adapters: it removes repeated owner
wiring while retaining application-specific quiescence. The strongest objection
is that hooks cannot prove an application has stopped every future job. Require
an explicit registered-work boundary and a delayed-job control; Live drain checks
physical sessions independently, but neither observation proves arbitrary future
work absent. Applications without that boundary must fail setup or remain outside
this profile. This is a design proposal; implementation approval is pending.

## Pinned inputs and scope

- Product baseline: main `3ced89330997d711675a303df831680b699ebd8c`.
- Approved scope and hook contract: candidate
  `ec3b7c1d6dc1b1c74608ad517f75be7230a108f8`,
  [scope](https://github.com/masahitojp/mariamem/blob/ec3b7c1d6dc1b1c74608ad517f75be7230a108f8/docs/reviews/v06x-dogfood-scope-draft.md),
  [hook contract](https://github.com/masahitojp/mariamem/blob/ec3b7c1d6dc1b1c74608ad517f75be7230a108f8/docs/reviews/v06x-e2e-entry-contract.md).
- Completion owner: [#18](https://github.com/masahitojp/mariamem/issues/18).
  P1/Go fixture candidates #26/#6 retain their own adoption conditions.
- EP1 uses the existing Django/Playwright application and locked dependencies;
  EG1 uses the existing Go orders HTTP application, Go1.26.10/mysql1.9.3.
  Hosts: macOS15 arm64, Ubuntu24.04 x86_64; Python3.11/3.14.
- One application, Live and baseline per fixture owner; one active case per
  owner. Parallelism uses two entirely independent owners. A worker never shares
  a mutable Live or browser context with another worker.

No SDK/runtime implementation is included in this proposal. D1 prepared-state
restoration remains separate. This proposes no new guest, wire command,
post-start capture, automatic pool retirement, scheduler or general framework
adapter. Selecting this design does not adopt its future candidate or release it.

## Product evidence and the delta

| Source at baseline | Confirmed mechanism | Entry must add |
| --- | --- | --- |
| [Go Live](../../live.go), `Snapshot.Live`, `Live.Reset`, `Live.Close` | Non-nil cleanup-only Live may accompany creation error. Busy preserves data; failed replacement blocks SQL. Reset cancellation after commit returns success; cleanup can outlast deadline | Register partial owner before inspecting error; gate case admission; never automatically retry failed setup |
| [Python Live](../../python/mariamem/live.py) | Snapshot owns creation route; reset reports authoritative host outcome; close retains its result | Keep original exceptions, worker-local debt, independent cleanup attempts; preserve current creation-error semantics |
| [Live acceptance](../../tests/live_acceptance/README.md), [fixtures](../../tests/live_acceptance/conftest.py) | Fixed app, endpoint/generation checks, browser contexts, actual drain/replacement controls | Public supplied entry instead of test-only wiring; hook-failure/overlap controls and resource campaign |
| [Public examples](../examples/live/README.md) | Django CONN_MAX_AGE=0 / Go MaxIdleConns(0), app-before-DB teardown | Explicit quiescence/Stop obligations; examples alone do not validate arbitrary hooks |

CI40492426087 at `3ed2c8e0790499c215869e33154272b062c35a88`
provides both-host regression anchors; the
[adoption record](v06x-dogfood-main-adoption.md) preserves their scope. Those
receipts are not evidence that the entry proposed here already exists.

## Proposed configuration and owner API

Names below are proposed public names, to be approved with the lifecycle.
Keep Go code in package `mariamemtest` after #6 integration; Python uses a
`mariamem.e2e` module and explicit user fixtures, without adding Playwright as a
mandatory SDK dependency. Share lifecycle semantics, not cross-language code.

Both configurations require:

- Existing database startup options and `prepare(source)`: a callback receiving
  the owned source DB. The entry starts the source, executes preparation once,
  waits for physical disconnect, captures Snapshot and owns source/baseline/Live
  cleanup. Callback owns its application migration connections/processes and
  must join/close them before returning. Failure discards preparation, admits no
  body, and preserves the original error. No implicit rerun or baseline cache.
- `start_ready(ctx, target, register_app)`: the exact Live connection target and
  a registration callback. Register each partial app handle as soon as it exists,
  before readiness can fail. Handle exposes stable identity and the mandatory
  quiesce/stop hooks below. Return one registered ready handle; a missing or
  unregistered handle is setup failure. A hook throwing/returning error still
  leaves registered handles owned. Allocation-to-registration is the hook's
  responsibility; work never registered is reported as outside proven cleanup.
- Positive finite setup/reset/drain/cleanup budgets. Proposed defaults match
  existing reset: reset120s, drain5s; setup120s and cleanup30s are proposed
  cooperative budgets requiring campaign confirmation. Reject invalid values
  and missing required hooks before starting any source. No detached timeout
  goroutine/thread may be called safely cleaned up.
- Optional `resume` and `external_state` hooks. Resume may be omitted only with
  a declared sole-work-source model: no other work starts before body admission.
  External-state reset owns its own partial resources via case registration.

The app handle must expose `quiesce_and_retire(ctx)` and `stop_reap(cleanup_ctx)`.
Quiescence holds the no-new-work barrier until Resume/admission, joins admitted
work, finishes transactions and closes every physical connection including idle
pools. A no-op hook is allowed only for an explicitly sole-work-source app whose
requests already retire connections; the actual Live drain still runs. StopReap
is idempotent, works after partial startup, and confirms termination/join and
connection retirement or reports uncertainty. The entry records app identity,
endpoint and Reset generation; it never logs connection passwords.

### Python browser usage sketch

Proposed interfaces, not executable current SDK code:

```python
from mariamem.e2e import BrowserEntry, Config

@pytest.fixture(scope="session")
def orders_entry():
    # Each xdist worker invokes this separately; prepare/start are app hooks.
    with BrowserEntry(Config(prepare=prepare_orders,
                             start_ready=start_orders,
                             sole_work_source=True)) as entry:
        yield entry

@pytest.fixture
def orders_page(orders_entry, browser):
    with orders_entry.case(browser=browser) as case:
        yield case.page

def test_create(orders_page):
    # ordinary Playwright actions/assertions; next case restores the seed
    ...
```

`browser` is supplied by the existing Playwright fixture and remains caller-owned.
The entry creates/registers a fresh context before creating its page and closes
it before releasing case admission on every exit. `case.app` exposes the app
handle/base URL. The test author supplies preparation and app hooks once, then
adds tests without DB lifecycle wiring. Implement the context manager so pytest
retains original setup/call/teardown outcomes and KeyboardInterrupt/SystemExit;
cleanup failures are additionally reported, never replacing a primary interrupt.
No automatic browser installation or plugin-based app discovery is proposed.

### Go HTTP usage sketch

```go
func TestOrders(t *testing.T) {
    fixture := mariamemtest.NewHTTP(t, mariamemtest.HTTPConfig{
        Prepare: prepareOrders, StartReady: startOrders,
        SoleWorkSource: true,
    })
    t.Run("create", func(t *testing.T) {
        c := fixture.Case(t)
        // c.BaseURL; ordinary HTTP assertions
    })
    t.Run("seed restored", func(t *testing.T) {
        c := fixture.Case(t)
        // same UNIQUE value can be inserted again
    })
}
```

Proposed signatures: Prepare(context.Context, *mariamem.Database) error;
StartReady(context.Context, mariamem.ConnectionInfo, func(HTTPApp) error)
(HTTPApp, error). HTTPApp provides BaseURL/Identity plus
QuiesceAndRetire(context.Context) error and StopReap(context.Context) error.
NewHTTP registers cleanup immediately with the parent test; Case(t) acquires a
nonblocking exclusive lease and registers cleanup with that subtest before
returning. The lease lasts until t.Cleanup, including after t.Fatal/Goexit or
when t.Parallel suspends the test. It is never released merely because t.Run
returns. This is why the proposal uses Case(t), rather than a callback wrapper
around t.Run. Concurrent acquisition fails before hooks/Reset; parent cleanup
runs after its subtests. Cases sharing one owner are documented as sequential;
t.Parallel is supported only across independent fixture owners. A deliberate
same-owner parallel control must prove safe rejection and no Reset of the active
case. Case must be called from its owning test goroutine. NewHTTP is registered
on their common parent; do not let a subtest's owner die before other cases.
HTTPCase owns an HTTP transport/client, closes idle connections and joins its
registered requests before release. Arbitrary user goroutines require explicit
join. Cleanup failure latches owner failure even when t.Errorf reports it on an
already failed test. No claim that every user misuse is statically detectable.

## State transitions, cleanup and diagnostics

| State / event | Action | Next admission |
| --- | --- | --- |
| NEW → PREPARING | Validate all configuration; register source immediately; prepare, disconnect, capture; register any partial Live | None |
| STARTING | Register app before readiness inspection; identify app/endpoint | None until ready |
| IDLE → SETTING_UP | Acquire exclusive lease; QuiesceAndRetire → Reset (including first case) → verify stable target, ready state, generation+1 → Resume → external state/context | None until every step succeeds |
| CASE_ACTIVE | Body owns work only for this lease; later acquisition rejected before hook/Reset | Current case only |
| Body failure/cancellation with confirmed cleanup | Preserve original result; finish registered work/context before releasing lease | Next case may reset; normal test failure does not poison owner |
| Any setup error, case cleanup debt or identity mismatch | Latch FAILED before diagnostics/finalization; no retry, no Resume after failed Reset | No later case; report prior failure stage |
| Closing | StopReap all registered apps → Live.Close → baseline.Close → remaining source close | No case; wait for active case/setup to finish cooperatively |
| Any cleanup error | Continue all remaining cleanup attempts; retain attempted/confirmed/unknown per owner | FAILED/CLOSED with debt; no success label |

Partial creation handles are registered before inspecting errors; registration
rejects duplicates and preserves all unique handles for cleanup. A non-nil Live
plus error in Go is never discarded. Python creation failures retain original
and cleanup exceptions from the existing API; the helper must not invent a handle
it did not receive or claim those internals confirmed.

A separate cleanup deadline/context is derived independently of canceled case
contexts. A hook exceeding a cooperative deadline latches failure and blocks
admission; the entry cannot safely abandon it and reset/close underneath it.
No thread/goroutine forced termination or hard wall-clock shutdown is promised.
Repeated Close preserves the first outcome; concurrent Close requests serialize
without running hooks twice. Close inside an active case is rejected before
waiting on its own lease; framework teardown closes after case finalizers.

`readable-owned` reports stage, original error/code, admission, cleanup outcome
and a supported next action or explicit unknown. Assertion/SQL errors remain
ordinary framework output. Go wrapping/joining must retain errors.Is/As identity;
Python retains original control exceptions and independently reported cleanup
failures under the supported Python3.11 minimum. Application log/output boundedness
must be explicit in the implementation; reuse P1's bounded command mechanism
only after that code is adopted, without importing an unmerged dependency here.

## Finite acceptance and detection plan

Existing CI does not detect missing public hooks or their ordering: this is a
planned detector matrix, not a current test result. Preserve the old Live oracles.

| Obligation | Planned evidence / negative control |
| --- | --- |
| Partial source/Live/start ownership | Controlled owners fail each construction step; handle+error/exception cleanup attempts recorded exactly once; actual guest partial Live path where reachable |
| Hook order / no invalid admission | Event trace for first and next case; missing hook, failed readiness/quiescence/Reset/Resume/external setup each gives body=0 and no later implicit retry |
| Physical sessions and delayed work | Actual idle pool survives a lying-success hook → drain rejects body; registered delayed job pause/join through Reset; deliberately skipped hook detected |
| Body failure/interruption / cleanup debt | Original assertion/cancellation/interrupt retained; healthy next case only after confirmed cleanup; browser-close and app+DB combined failures stop later admission |
| Identity / isolation | Native-controlled same inputs; two cases reuse UNIQUE value with seed restored, PID/endpoint unchanged and generation incremented; skip-reset/restart-app/original-target fallback mutations rejected |
| Exclusive case / independent owners | Overlap rejected before hooks, no damage to active case; explicit Go t.Parallel edge; two owners with disjoint PID/endpoint/data and Python contexts |
| Public installed entry | Exact-source wheel for both Python minors; external Go module consumer; no source-tree fallback; dependency/input hashes and source-bound host receipts |
| Timing/resource / guard | First-test commands/edits and phase times; second-test authored diff; warmup1 + observed3 × four-case batches, serial/two-owner modes; retained baselines1/2/3; RSS/available memory/FD/physical connections/temp/cleanup; guard STOP control |

Observe transient old/new Reset children and idle sessions, not just steady
Live counts. Apply the approved 2GiB incremental RSS,8GiB owned disk,16GiB free
and FD headroom64 ceilings; absent counters are UNVERIFIED. Report warm/cold/
unmeasured acquisition honestly. Existing native controls are reused only for
identical inputs; changed hook/pool variant gets fresh MariaDB12.3.3 control.
Both supported hosts and Python minors need exact-source receipts. Cooperative
cleanup limits and arbitrary unregistered work remain stated limitations.

## Implementation sequence and decision conditions

1. Approve the bounded lifecycle and API direction, with readable-owned retained.
2. Demonstrate Go lease lifetime across t.Parallel/Goexit and partial-start
   registration ergonomics with small controller/fake-owner probes before product
   code. If a probe contradicts this design, return its concrete alternative
   for decision.
3. Implement language entry cores/adapters without guest/Live semantics changes;
   add finite fault controls and public examples. G1 package integration and any
   P1 command reuse follow their own approved candidates.
4. Obtain native/actual guest, installed-consumer and resource receipts using
   existing Live jobs where practical; submit CI and hand off. Keep all existing
   required contexts/oracles. New receipt validators reject wrong source/host,
   incomplete cases and cleanup debt. Component PASS cannot replace these runs.
5. Review against #18; main adoption remains a later decision, followed by
   version/Qualification/Product Validation/publication in the approved order.

Exit for this design task: proposal and claim-to-source checks, sketches and
planned finite oracles saved; no runtime PASS or implementation authorization
inferred. The remaining adapter uncertainties are concentrated in two small probes,
not a broad engine experiment. Those probes need a bounded task after the design
decision; no new runtime campaign was run while writing this proposal.
