# Issue123: bounded Close wait diagnosis

## Conclusion and recommendation

**INCONCLUSIVE_NO_REPRODUCTION**, 2026-11-10. The original question was which
Close stage blocked for about40 seconds in the post-merge comparison. That stage
remains unknown: the fixed10 alternating pairs completed without a slow Close.
Do not label the earlier failure fixed, dismiss it as noise, or infer that the
static cache caused it. Preserve a delayed stack observer for the next authorized
workload/measurement that encounters the failure; do not extend this campaign by
adding repetitions. No product change, rollback or release follows from this run.

The original [failed run](issue123-postmerge-evidence/failure-after-fork-p4-r1.json)
remains part of the [speed comparison](issue123-postmerge-measurement.md).
All48 SQL checks passed there, but child43 Close took40002.453375ms and one
mapping remained unreaped at process exit. Successful timing subsets do not erase
that failure.

## Bound inputs and result

The Human authorized this diagnosis after the original failure. External harness
source_commit `9edc93e59ee53cda4437b579a9e8760d3cae89c3`, branch
`experiment/issue123-close-wait`, adds only `benchmarks/issue123close/`.
Both product checkouts were clean and checked with `scripts/git_identity.py`.

- Before: `c375edbc1e77bf078f50abc75c9de32ce23a641a`.
- After: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`, its direct child (PR147).
- Single Apple M1/macOS27.2 arm64 host; Go1.26.10, GOMAXPROCS8, GOGC100,
  CGO disabled, Go Pipe. Same1000-row seed,48 children, Fork/P4, cap4.
- Same SQL/lifecycle probe as the earlier comparison. Guest input and generated
  input manifests match between arms; host provenance differs as expected.
-20 primary processes, alternating arm order within10 pairs; no retries. Four
  separate controls: two positive SQL/cleanup controls and two forced observer
  controls. No additional warmup or primary repetitions.

| Primary result | Before | After |
|---|---:|---:|
| Processes completed |10/10|10/10|
| Child SQL and cleanup checks |480/480|480/480|
| Close p50, ms |4.226|3.725|
| Close p95 (nearest rank), ms |8.820|8.752|
| Maximum child Close, ms |14.976|16.453|
| Close over2 seconds |0|0|
| Processes with outstanding mappings/bytes |0|0|

All24 processes exited0 with empty scratch and successful cleanup. The observer
adds a goroutine/timer per Close and can perturb scheduling; these durations
characterize this diagnostic run, **not a fresh speed acceptance or a causal
before/after comparison**. No Ubuntu result is claimed.

## What the source narrows, and what it does not

Source references below are at after source `b1218737`; both arms already contain
the Issue145 shutdown-mode selection.

1. `mariamem.go` creates the default30-second ShutdownTimeout. In
   `internal/host/server.go:finish`, an error triggers Abort and then a separate
   10-second wait for Guest.Done. The original error, `guest cleanup timed out:
   context deadline exceeded`, and40-second duration fit these two budgets.
   This identifies timeout layers, not which engine operation blocked.
2. Every `setShutdownMode` call error is wrapped with `configure guest shutdown`.
   `finish` and `errors.go:HostError` preserve that text. Its absence in the
   original full error rules out a directly returned timeout from that private
   session/SET/close sequence on this source. This is source/error-chain reasoning,
   not an observed stack. The shutdown setting can still affect later behavior.
3. Remaining direct timeout paths include waiting for host session workers and
   `Guest.Shutdown` (sending the shutdown frame or waiting for guest completion).
   Successful WaitDisconnected makes unfinished public-session work less likely,
   but does not strictly prove workers.Done: attach's deferred client deletion
   and notification run before conn.Close and workers.Done.
4. `internal/guest/linked.go`, `runtime_instance.go` and host `disposal.go` wait
   for guest/root/worker completion before final disposal. Resident shutdown joins
   slot workers and closes the engine. The unreaped mapping is therefore evidence
   of incomplete disposal, **not proof of a failing unmap**. No captured slow stack
   separates engine shutdown, a worker join, pipe write or memory release.

## Capture contract and missing evidence

The external Close wrapper records all Go stacks (2MiB maximum, truncation flag)
and bounded DB Logs at2 and10 seconds for only the first slow DB in a process.
Default shutdown deadlines and product code are unchanged. A primary slow capture
or failure stops the campaign. A1ns forced threshold separately tests capture;
both arms produced nontruncated stacks with the observer present. Saved excerpts
are explicitly **forced controls**, not evidence of a hang.

What is still needed: a non-control delayed stack, its DB/child identity, logs and
exact source. That would locate the first blocking stage and justify a targeted
fault injection or fix. Reusing this observer in a future authorized workload is
cheaper than another unbounded repetition campaign. No occurrence probability,
platform-wide safety claim or exoneration of PR147 follows from zero failures here.

## Evidence, verification and reproduction

[Compact evidence](issue123-close-wait-evidence/summary.json) includes per-child
Close durations, all process outcomes/cleanup counters, bound source/binary/input
hashes, observer-control metadata and selected excerpts. SHA256SUMS.json covers
the retained files; original-files-sha256.json identifies discarded full successful
reports/control stacks. No unique failed trace was generated in this campaign.

Read-only verification, including after workspace cleanup:

```sh
python3 docs/reviews/issue123-close-wait-evidence/check.py
```

To reproduce a newly authorized campaign, prepare an experiment-workspace with
8GiB owned budget and12GiB free-space minimum, using the exact harness commit
above as its clean worktree. From that worktree run
`python3 benchmarks/issue123close/build.py` then
`python3 benchmarks/issue123close/run.py` through the workspace runner with
`--timeout 1800`. Go1.26.10 must be
available; pinned modules may need downloading. The plan caps primary runs at20
and stops first slow/failure. Build captures the actual harness HEAD; use the
measured commit, not a later documentation commit, to reproduce input identity.

Temporary product checkouts, binaries and task-local build/module caches are
recreatable and removed after preservation. Compact records and pushed diagnostic
source remain; the report PR contains documentation/evidence only.
