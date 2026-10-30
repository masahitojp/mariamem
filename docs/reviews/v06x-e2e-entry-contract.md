# Prepared E2E entry contract — EP1/EG1 design proposal

Current completion tracking: the [2026-10-30 sequencing decision](../decisions/e2e-v060-work-sequencing.md)
supersedes this historical proposal's detailed resource-campaign prerequisite.
The functional lifecycle/hook obligations below remain in force.

2026-10-28. Shared contract for Python browser E2E and Go HTTP E2E, awaiting
concrete entry API design. The Human approved this scope/contract against39f9757.
Django-specific implementation is nonblocking for v0.6.0: if necessary, pin a
non-Django Python application while retaining browser E2E acceptance. Live is an existing mechanism; no new entry is
implemented by this document. Both entries use the declared diagnostic milestone
in the [scope draft](v06x-dogfood-scope-draft.md).

## Ownership and hook inputs

The user supplies application-specific hooks. The entry supplies call ordering,
deadlines, case admission, Live Reset, owner tracking and error/cleanup reporting.
Hook names below describe a contract, not committed public API names.

| Hook | User obligation | Entry obligation and failure behavior |
| --- | --- | --- |
| StartReady(ctx, target) → app handle, error | Start against exactly the provided Live target, complete readiness/health checking, return an owned handle. On partial failure return a cleanup-capable handle, or prove local cleanup before returning none. Do not silently fall back to the original DB. | Register any returned handle before inspecting error; invoke StopReap on partial failure, then close Live/baseline. No case admission. Record process/endpoint identity. |
| QuiesceAndRetire(ctx, app) → error | Stop or prevent new request/background-job DB activity, await admitted work, finish transactions and retire **all physical** SQL connections including idle pools. Hold this condition until Resume/case admission. Closing a logical handle alone is insufficient. | Invoke before every case, including the first. After hook success, Live's drain check independently verifies physical disconnect. Hook/drain/Reset failure latches setup failure and admits no further cases. Never automatically retry the failed case setup. |
| Resume(ctx, app) → error (optional) | Re-enable application work only if QuiesceAndRetire paused it. May be absent only when the test harness is the sole work source and case admission itself releases that condition. | Invoke only after successful Reset/identity validation. If it fails, admit no case, latch failure and attempt shutdown. Never resume old/uncertain data after failed Reset. |
| StopReap(cleanupCtx, app) → error | Stop application work, terminate/join the owned process or in-process tasks and retire owned connections. Safe for partial startup and repeated cleanup. Return failure if shutdown/reaping cannot be confirmed. | Attempt before Live.Close and baseline.Close using cleanup context independent of a canceled case context. Continue best-effort cleanup of DB owners even on Stop failure; report the unconfirmed app separately, never claim complete cleanup. |

A required StartReady/QuiesceAndRetire/StopReap hook cannot be silently omitted.
Only an application whose explicit semantics already provide quiescence/connection
retirement may supply a no-op quiescence hook; the actual Live drain remains
required. The entry cannot discover arbitrary delayed jobs or unregistered pools.
Uncooperative work or hard-kill/machine-loss recovery is not a new guarantee.

Optional per-case external-state hooks may reset application memory/caches and
other owned state, with the same failure/admission rules. The browser entry owns
and closes a fresh browser context for each case; sharing the application does
not mean sharing cookies/storage. Go HTTP is not browser coverage. Reset does
not clear non-DB state. An app needing extra reset must declare that hook and
cannot be reported isolated on the basis of DB rows alone.

## Lifecycle and admission

1. Worker/fixture owns preparation and its successful baseline. Complete schema
   and seed before Live and application startup. Startup migrations/seed must be
   made part of declared preparation; capturing extra application-startup writes
   into a new baseline is not implemented by this proposal. Workloads that require
   post-start capture remain an explicit design question, not a silent PASS.
2. Create Live; retain any non-nil cleanup-only result even if creation errors.
   Run StartReady, retaining the baseline until every case/Reset ends.
3. Before every case: acquire exclusive case admission; QuiesceAndRetire → Live
   drain/Reset → verify stable endpoint and committed generation → optional Resume
   → external-state preparation/browser-context creation → admit body.
4. Finish/await case HTTP/browser work and dispose its case resources before
   another setup starts. A normal test assertion failure is retained; the next
   case may run only after successful quiescence and fresh Reset. Setup/Reset or
   unresolved per-case cleanup failures stop future admission.
5. StopReap → Live.Close → baseline.Close, preserving original and cleanup errors.
   Track partial construction and distinguish resources never created from
   resources not successfully reclaimed. Do not use canceled t.Context for all
   cleanup calls or detach work and label it cleaned up.

One owner admits only one active case. Concurrent use is rejected before hooks
or Reset and must not reset underneath an already-admitted case. Parallel workers
own independent applications, endpoints and baselines; no shared mutable Live
endpoint is parallel-safe by declaration. Context deadlines are cooperative;
existing noninterruptible Snapshot/cleanup behavior is not changed here.

## Finite failure/resource acceptance

On each supported host/minor, verify two cases preserve application PID and Live
endpoint while reusing the same UNIQUE value: first commits it, second sees only
seed. Verify the actual hook event order, not just hook presence in source.

- Partial StartReady failure with returned app: StopReap occurs and no body runs.
- Quiescence timeout and a surviving idle SQL connection: the hook's nil error
  cannot override the Live drain; preserve Busy/drain errors and admit no body.
  For a registered delayed-job control, prove the supplied hook pauses/joins it
  through Reset. The entry cannot detect an unregistered future job merely by
  observing zero sessions now; do not claim a lying/insufficient hook is always
  detectable or silently label that application safe.
- Reset replacement failure, Resume failure and external-state setup failure:
  no case body or later implicit retry; the original cause remains inspectable.
- Assertion failure/cancellation: case resources finish; any subsequent admitted
  case begins at the declared DB state. Browser context is closed on every exit.
- StopReap failure plus Live/baseline cleanup failure: all attempts are visible
  and none replaces the original failure. Partial Live creation's cleanup owner
  is retained. Distinguish cleanup attempted from cleanup confirmed.
- Overlapping cases are rejected without Reset or damage to the current case;
  two independent owners can run with no cross-owner mutation/identity leak.
- Apply the scope draft's first-test/second-test/repeat timings and resource
  counters; count idle retained connections and transient old/new Reset children.
  One logical Live can temporarily own two physical children during replacement;
  reserve that memory in the two-worker observation instead of counting only
  steady-state databases. No dynamic governor is claimed.

Existing Live acceptance and numeric-bind/browser controls are regression
anchors. They do not prove this as-yet-unimplemented hook entry. Hook defects,
original-endpoint fallback, skipped Reset and restarted application must be
negative controls; the new entry must reject them rather than merely pass its
happy-path application example.
