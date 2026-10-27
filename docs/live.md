# Stable endpoints for browser E2E — unreleased candidate

This guide describes the approved implementation candidate, not the published
v0.5.3 package. It is verified only as specified in the [candidate record](reviews/v06x-live-main-candidate.md).

Use Live when an application stays running while sequential tests each need the
same initial database. Prepare with explicit settings, commit and close the
preparation connections, then capture a Snapshot. Keep that Snapshot open until
all resets finish. A Live owns one stable localhost endpoint over private Forks.

```python
with source.snapshot() as prepared:
    with prepared.live() as live:
        app = start_application(live.connection_info())
        try:
            for case in cases:
                wait_for_requests_and_close_database_connections(app)
                live.reset(timeout=120, drain_timeout=5)
                run_browser_case(app, case)
        finally:
            stop_application(app)
```

The application helpers above belong to the test harness. Ordinary Django settings
can use the supplied host/port/database with django.db.backends.mysql. The bounded
browser example uses CONN_MAX_AGE=0. A retained idle pool connection also prevents
reset; retire it explicitly. Live cannot detect a delayed job that opens a new
connection after reset. Finish requests/jobs and stop new work before resetting.

```go
live, err := prepared.Live(ctx)
if err != nil {
    // Rare creation-cleanup failure can return a closed cleanup-only owner.
    if live != nil { defer live.Close() }
    return err
}
defer live.Close()
// Configure the application once with live.ConnectionInfo() or live.DSN().
// Quiesce its work and retire physical connections before each Reset.
if err := live.Reset(ctx, mariamem.ResetOptions{}); err != nil {
    return err
}
```

Zero Go DrainTimeout defaults to5 seconds. Go ctx governs operation admission,
drain and replacement startup; startup also has the inherited bound. Python's
host-side timeout defaults to120 seconds. Compensation/Close has its own shutdown
bound and can outlast the operation deadline. Cancellation after the atomic reset
commit is success; cancellation before commit does not publish a ready generation.

Busy (Python Busy / Go ErrBusy) preserves the original data and generation. A
replacement error enters failed and refuses new SQL until explicit successful
reset or close. A precondition error from a closed parent preserves the current
child, but no test should proceed after any failed setup/reset. Existing physical
sessions, transactions and prepared handles are not transferred to a new child.
A reset restores database contents, not application caches/cookies or worker state.

Use status()/Status() for state, generation and active physical connections.
After close, endpoint metadata stays readable but the address is unusable. Close
preserves its original error on repeated calls. Go repeated Close retries unresolved child disposal. Python retains failed
children in its shared host for retry at host shutdown; repeated Python close
raises its stored error. Successful disposal retry does not erase the original error. Context-manager cleanup preserves an
application exception together with a cleanup error. A failed Live does not
terminate other databases sharing the Python host.

Python requires a matching host advertising live-v1. An older protocol2 host can
continue serving ordinary Database/Fork, but the Live entry refuses before
creating resources. There is no automatic alternative host or cross-host handoff.
