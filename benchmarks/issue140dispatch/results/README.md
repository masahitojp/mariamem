# Issue140: read dispatch and completion dispatch separated

**Two naturally long PREPAREs were bound to the same read request generation,
and the delay was dispatch before a worker/callback began.** One was before
synchronous I/O; the other was after I/O, before its completion callback.
The measured read operations themselves took2–3µs. This does not yet decide
whether generic-pool admission or read task-group admission held the task.

| Captured foreground | PREPARE whole call | Initial submit → I/O worker start | Synchronous I/O | Completion submit → callback entry | Callback entry → notify | Notify-after → resume |
|---|---:|---:|---:|---:|---:|---:|
| 16MiB, natural-2, db-14/scope1 | 801.172ms | 1.071ms | 0.003ms | **795.146ms** | 0.017ms | 0.030ms |
| 8MiB, natural-3, db-20/scope2 | 389.732ms | **385.218ms** | 0.002ms | 1.777ms | 0.027ms | 0.048ms |

These stages cover the selected request, not every part of PREPARE. They must
not be summed as an exact decomposition of the entire caller time. Initial
submission may predate the call or the read_wait scope. Dispatch intervals
include API submission and both potential admission layers, not a timestamp
at the internal queue push. In these two cases the submission calls had already
returned, and using return rather than entry gives the same displayed values.

16MiB captured PREPARE ordinal3 (stock UPDATE preparation),
`TestShipOrder/pending_rejected`, page `(space=2,page=7)`, trx non-null.
8MiB captured ordinal1 (orders INSERT preparation),
`TestDeleteUser/user_36`, page `(space=10,page=0)`, trx null.
The SQL statement types and pages differ: this is mechanism attribution,
not a matched 16MiB/8MiB performance comparison. `db-*` abbreviates retained
`issue68-db-*`; addresses/IDs only identify objects inside their own process/DB.

## Evidence and scope

Measured source_commit is in [inputs.json](inputs.json), with exact product
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22` and origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
It extends [the prior page/channel step](../../issue140read/results/README.md)
without relabeling that receipt. Runtime changes are overlay-only; committed
internal/, guest/, release/ and root Go module files remain equal to that product.
New files after the measured commit are analysis/source excerpts/records only.

The pinned simulated AIO implementation first submits an internal task to read,
then changes its callback and submits it again for completion. The observation
wraps current generated Fn18241 (initial submit), Fn18242 (I/O worker and its
post-I/O completion submission), and Fn18280 (read completion callback).
Original function bodies are guarded before overlay generation; table indices
are bound by the exact product source and observed submit/callback identity.
Full original/overlaid file hashes and binary digest are in inputs.json.
Primary C file hashes and selected exact excerpts are retained separately.
No guest recompile or setting sweep was used.

An aiocb pointer may be reused. Each submission therefore creates a distinct
observer ID scoped to its DB/ThreadPool. The read wait records the pending
request ID at parking; the **actual notifying callback's Module context**
records its own ID at close(ch). Both IDs must agree. DB, block, page, pprof
read_scope, active wait IDs before/after the profile, and caller window are
checked as well. Callback entry is before page unlock; its stack still identifies
the same completion/unlock path. No cross-process pointer join is permitted.

Six synthetic controls pass with race detection: the previous three plus
pipeline-to-notifier identity, cb reuse/write exclusion and wrong-page notifier
rejection. One live SQL SLEEP control passes before the fixed8 natural suites.
Same shop70/Pipe/P8/cap9, Go1.27.3/GOMAXPROCS8/GOGC100, two reversed blocks of
16/8MiB × watcher on/off, one binary, unchanged SQL order/cases. All630 cases,
all9 active-mappings-after=0 and all198 observer closes pass. No truncation;
maximum observed per-instance I/O records217 against cap4096. Scope256/wait1024
caps remain unchanged. No extra sampling followed the fixed exit.

The corpus has28227 read requests. Compact retention keeps all read/park/page
records, every request referenced by them, and **all** requests with ≥50ms from
submit to callback. Unreferenced shorter requests become explicit per-instance
counts and an original-record digest; their individual timings are not retained.
No claim about the distribution of all short I/O timings depends on that digest.
All three bounded profiles and all SQL phase records/traces remain available.
This avoids retaining cache/build outputs or repetitive short-request records.

Observer locks, labels and profiling perturb scheduling. These are two local-Mac
mechanism examples, not frequency estimates, a production-overhead bound, a
performance A/B or Ubuntu acceptance. No pool counters, worker kind, maintenance
tick or live load/recovery phase was captured; notification-call presence alone
does not prove effective waiting accounting.

## Related settings / recommendation

The [settings source map](settings.md) separates read-group concurrency,
transient startup global-pool concurrency and possible background demand.
It also distinguishes explicit argv, newly observed execution paths and values
not freshly queried. Read1 is not proof of a permanent global pool limit of1.
400ms maintenance and500ms long-task constants are hypotheses, not observed causes.

**Next useful observation:** distinguish the global pool from the read task
group using their existing-lock-protected counters and admission events for the
same request. Only then choose a targeted setting or code experiment. Broad flush
or memory-size sweeps would mix the two currently visible dispatch delays.
#140 stays open; no product fix/default, main, Qualification or release decision
is made. This step answers the requested partition and stops here.

## Replay / reproduce

```sh
python3 benchmarks/issue140dispatch/results/analyze.py --check
```

This is read-only and works after cleanup with no network/temp tree. It verifies
summary bytes, profile/window/page/request-generation/notifier binding, phase
ordering, four request-binding mutations, retained/census counts, cases/cleanup
and all checksums. Primary source excerpts can be checked against files fetched
from their exact upstream commit using `fetch_source.py WORKSPACE`.

A separately authorized fresh collection uses a clean checkout of this experiment,
worktree/, temp/, evidence/, recorded toolchain/host and the fixed plan:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue140dispatch/run.py WORKSPACE
```

Exact git identity and unchanged committed runtime inputs are checked before
builds. Initial budget2h active/30min tooling, CI0, disk10GiB/minimum free8GiB.
One guarded run completed; no failed run is recast as a successful receipt.
Source/layout discovery is not authorization for further experiments or a fix.
