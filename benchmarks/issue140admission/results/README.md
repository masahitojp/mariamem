# Issue140: global pool versus read task group

**The captured long PREPARE waited in global dispatch, before the read task
group. The same request was actually in the global queue while the global
worker wake/create gate rejected progress.** The read group was not full when
this request arrived. This closes the requested admission-layer partition,
not the choice of a fix or an explanation of each worker's waiting accounting.

## Profile-bound foreground example

`natural-7-pool16-on`, `issue68-db-19`,
`TestApplyDiscount/books_10`, PREPARE ordinal1 (orders INSERT): **815.432ms**.
The foreground read scope1 waits on page `(space=10,page=0)`, trx=null.
Park ID1 and both its pending and actual notifying request IDs are9.
The same request's initial and completion stages are:

| Stage | Initial I/O task | Completion task |
|---|---:|---:|
| Submit entry → global dequeue | 22.338ms | **791.395ms** |
| Global dequeue → group entry | 0.001ms | 0.000ms |
| Group entry → actual run | 0.000ms | 0.001ms |
| Group running / limit at admission | 0 / 1 | 0 / 1 |
| Queued by group? | false | false |

Synchronous I/O took0.002ms. Callback entry → actual notification took0.035ms;
notification-after → waiter resume took0.036ms. Stages describe one read request,
not a complete additive decomposition of the entire PREPARE caller. Hook overhead,
queue scanning under the mutex and profiling perturb these timings; especially
the initial22ms is not a new production performance estimate.

For the **completion** task, exact global-queue membership was present at these
locked gate snapshots (same pool address as the later dequeue):

| Snapshot | Recorder time | active | long | waiting | cap | active−long−waiting | Gate |
|---|---:|---:|---:|---:|---:|---:|---|
| first blocked | 529.219ms | 3 | 0 | 1 | 1 | 2 | reject wake/create |
| last retained blocked | 901.769ms | 3 | 0 | 1 | 1 | 2 | reject wake/create |
| last retained allowed | 1320.447ms | 4 | 2 | 1 | 1 | 1 | allow |

The task is globally dequeued at1320.613ms, and runs at1320.614ms. There were35
blocked gate samples for this completion task. First/last are sparse retained
samples, **not continuous proof that the gate rejected throughout791ms**.
The last allowed sample is not the first reopening and is not proof of which
specific timer event released work.

Current caller binding maps Fn16605 to submit_task, Fn16606 to wait_begin and
Fn16603 to maintenance, using current generated preimages and pinned C structure.
The last blocked sample came through maintenance; the last allowed sample came
through submit_task. We retain those exact callers and counters rather than
claiming that the last allowed sample itself was a maintenance tick.

## Complete natural-run census

All requests retain a compact timing tuple, so the layer-level census can be
recomputed without the discarded short-request metadata:

| Natural process | Read requests ≥100ms | With global stage ≥100ms | With group stage ≥100ms | Maximum group entry→run, all its reads |
|---|---:|---:|---:|---:|
| 1:16MiB/watcher off | 208 | 208 | 0 | 6.213ms |
| 2:16MiB/on | 0 | 0 | 0 | 5.724ms |
| 3:8MiB/on | 91 | 91 | 0 | 3.513ms |
| 4:8MiB/off | 125 | 125 | 0 | 8.800ms |
| 5:8MiB/off | 0 | 0 | 0 | 2.392ms |
| 6:8MiB/on | 0 | 0 | 0 | 4.732ms |
| 7:16MiB/on | 215 | 215 | 0 | 7.534ms |
| 8:16MiB/off | 119 | 119 | 0 | 24.864ms |

These are **758 correlated read requests across5 processes**, not758 independent
stalls or758 PREPARE profiles. Startup/background reads are included. Only the
16MiB foreground above has a live PREPARE profile in this step; no8MiB foreground
profile is newly claimed. Prior captures retain their original source and cannot
be relabeled as this admission evidence. No incidence, overhead or8/16MiB ranking
is estimated from the fixed corpus.

## Observation and checks

Measured diagnostic source: see [inputs.json](inputs.json), exact product
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`, origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
This builds on [the dispatch partition](../../issue140dispatch/results/README.md)
at `cb4cdbe2308e496ccb0585239b437d0b1dd632fa`. All runtime edits remain deterministic
build overlays, recorded with original/overlaid hashes and binary digest.
Committed internal/, guest/, release/ and root Go module inputs remain unchanged.
Files added after measurement are only source acquisition/analysis/records.

Source-bound hooks:

- Fn16594 records actual global queue removal under the original pool mutex.
- Fn16586 records task/group entry; the original locked running/limit reads and
  the exact queue-versus-run branch; and actual callback invocation, including
  tasks drained from the group queue by another worker.
- Fn16596 records the existing global gate under its callers' original pool
  mutex. It scans actual circular-queue members, including wraparound, rather
  than treating every unfinished request as queued. Only recognized current
  read-task callback/index/aiocb generation tuples are matched.

Raw layout is bound to current generated function preimages and primary C
[excerpts](source-excerpts.json),
[file identities](upstream-files.json),
[hook preimages](../source-functions.json) and
[caller preimages](caller-binding.json). Generic pool counters are offsets
180(active),344(cap),368(long),372(waiting); group running/limit112/116.
Queue layouts and group pointer offsets are separately guarded by exact source.
No unlocked polling of these guest structures is introduced. Observer locks
never acquire the guest mutexes; hooks add work inside existing locked paths.

All10 synthetic helper controls pass with `-race`: previous request/page/park
controls plus exact queue membership, wrapped queue, long-count exclusion,
stage separation, group queue/run and negative callback/task/scan-cap cases.
These controls test extraction/binding, not an independent implementation of
C++ locks. The live C/Go workload validates the actual instrumented paths.

One SQL SLEEP control precedes the same fixed8 natural suites, two reversed
16/8MiB × watcher on/off blocks, same binary/shop70/Pipe/P8/cap9,
Go1.27.3/GOMAXPROCS8/GOGC100. All630 cases pass; active mappings after every run0;
all198 observers close; no cap/truncation breach. Source identity is checked
before builds. One guarded run completed, without further natural sampling.
Budget2h active/30min tooling, CI0, disk10GiB/minimum free8GiB.

Retention keeps all scope/park/SQL records, both bounded profiles (control and
one natural), every referenced request generation and every request ≥50ms.
All requests additionally retain timing tuples with this schema:

```text
[id, submit_to_callback_us, initial_submit_to_dequeue_us,
 initial_group_enter_to_run_us, completion_submit_to_dequeue_us,
 completion_group_enter_to_run_us, initial_group_queued, completion_group_queued]
```

Short unreferenced requests' full metadata is reduced to explicit census/digest;
not all of their counter snapshots remain. Their timing tuples are retained,
so all-request group maxima and the≥100ms census are reproducible. For each
retained request/stage, first/last blocked and last allowed snapshots are retained,
not every gate observation. This is a single local Mac diagnostic, not Ubuntu
acceptance, a product benchmark or a continuously sampled ownership trace.

## Recommendation / remaining question

Focus the next design on **global-pool admission and worker waiting accounting**,
including the temporary startup/load cap, rather than increasing the read-group
limit to cure this observed delay. The [settings map](../../issue140dispatch/results/settings.md)
already distinguishes those two controls: changing read_io_threads can change
both the task-group limit and transient global concurrency, so it is not an
isolated group-limit experiment.

The actual global cap was1 during the captured stalls. We observed long-task
exclusions change and the gate allow progress later. We have not bound each
active worker to its waiting flag, established the first reopening, or proved
which particular load/recovery phase set that cap. In particular, a foreground
trx=null does not identify an unreported pool worker. Do not conclude that merely
moving read_wait's conditional notification fixes this case.

#140 remains open for a small remedy/design decision; **the requested global
versus group observation is complete**. No setting or product code fix, main
integration, Qualification or release is performed. Do not begin another general
parameter sweep or indefinitely repeat the rare-event capture.

## Replay / reproduction

```sh
python3 benchmarks/issue140admission/results/analyze.py --check
```

Read-only replay works after cleanup without network/temp. It checks profile,
caller/page/request generation and actual notifier binding; chronological
submit/dequeue/group/run/callback ordering; locked gate formulas and pool IDs;
all-request timing census; four admission-binding mutations; cases/cleanup;
summary bytes and retained checksums. Full short-request counter traces are not
reconstructed from their digest.

For a separately authorized fresh collection, a clean disposable checkout of
this experiment with worktree/,temp/,evidence/ and the recorded inputs can use:

```sh
python3 WORKTREE/benchmarks/issue140admission/fetch_source.py WORKSPACE
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue140admission/run.py WORKSPACE
```

Save new receipts separately; future capture is not guaranteed. Preserve compact
results and remove owned source copies, overlays, binaries and caches afterward.
