# Issue156: worker progress hypothesis — finite diagnostic complete

**The >100ms foreground tail was NOT_REPRODUCED in eight fixed natural suites.**
Creation-pending refusals are real and common in this diagnostic, but every
observed read completed without a100ms global-queue interval. This supports
instrumenting that branch; it does not establish that it caused the earlier
400ms PREPAREs or that those waits are fixed.

Recommendation: keep the hypothesis under [Issue156](https://github.com/masahitojp/mariamem/issues/156),
linked to residual owner [Issue140](https://github.com/masahitojp/mariamem/issues/140).
Do not increase read threads, shorten the maintenance timer or patch worker
admission on this evidence. The next useful uncertainty reduction is a small
controlled interleaving at creation-pending clear/task wait, not more draws of
the same suite. That controlled test is not executed here. UCA private-copy
acceptance remains independent, as [recorded by the Human](../../docs/decisions/uca-default-private-copy.md).

## What ran

Plan committed before execution. One immutable experimental guest
f43257225e1fd65c58ea8f5d7b220c3a509c203b, exact guest SHA256
332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22;
source-only reconstruction matched the prior CI candidate inventory. The
uninstrumented host binary matched Mac CI43148033625 exactly:
05ccab0bf7ad40cb07c685392cbe70ec71550c52e7e486cf8c8243d4c662033e.
No C build or CI submission was used. Generated-Go observation overlays are
experimental only; canonical guest, runtime, API and release inputs are unchanged.

Mac arm64, Go1.26.10, GOMAXPROCS8/GOGC100, Go Pipe/P8/cap9,
16MiB/read1, immutable d24087ee shop70 harness (50 shared-child read cases,
20 independent-child write cases:21 Forks/suite). SQL literals/order remain
unchanged. Effective pool/read settings, case counts, mappings and scratch are
asserted. One successful SLEEP(0.25) capture-control suite precedes eight natural
suites. All nine valid processes/630 cases/198 observer closures pass;
all mappings are0 and owned runtime scratch is empty afterward.

Measured driver source_commit:3069c533 (full identity in results/inputs.json).
The diagnostic helper source was committed at bde37691; later pre-execution
changes only fixed the driver/expected environment. Installation source5fb68c2c
retains its original meaning. Binary and raw-artifact hashes are retained.
Two earlier driver attempts were INVALID: missing expected pool value before
SLEEP, then missing SHOP_PARALLEL before test cases. The latter invoked SLEEP
but did not serialize a completed control receipt. Neither ran natural cases.
They are retained separately, not silently retried measurements. A disk wrapper
also rejected a noncanonical ../ path before invoking the compiler. There was
one successful diagnostic workload build, no workload-binary change and no
natural outcome-selected retry.

## Results (diagnostic only)

| Natural eight-suite census | Result |
| --- | ---: |
| PREPARE calls ≥100ms |0 /504|
| Read requests, including background |28,174|
| Initial/completion global-stage intervals |56,348|
| Global-stage p50 / p95 / p99 |0.930 /6.169 /10.354ms|
| Longest global stage |22.790ms|
| Global stages ≥100ms |0|
| Creation-pending refusals |88,393|
| Outer concurrency rejections |4,319|
| Created / entered / pending-cleared / exited workers |1,927 each|
| Actual creation callers: submit / wait_begin / maintenance |1,889 /37 /1|
| Max-thread / throttle / creation-failure-clear events |0 /0 /0|

Counts are correlated operations across DBs and batches, not independent
failure probabilities. The observer writes about100,000 events per process;
removing prior repeated queue scans does not make it timing-neutral. Wall/CPU
speedup, frequency reduction and an observer-off comparison are not claimed.
The preceding observer-off UCA P8 disadvantage remains valid under its source.

| Worker startup wall interval | p50 | p95 | Maximum |
| --- | ---: | ---: | ---: |
| spawn call → worker entry |0.284ms|6.445ms|21.818ms|
| worker entry → init callback return |0.001ms|0.008ms|12.893ms|
| spawn call → pending-clear event |0.292ms|6.588ms|21.822ms|

These are overlapping wall intervals, not additive CPU cost or a measurement
of the exact atomic flag's residence time. Recording can itself delay either
thread. The return value recorded at spawn_return is the constructed thread
object address, **not errno**; worker-enter/clear/exit correspondence and the
exception-cleanup hook establish successful lifetimes in this corpus.

Selected actual examples are in [results/examples.json](results/examples.json):

- natural-1/root DB: pending refusals at38.972/38.989ms, new worker entry39.014ms,
  clear39.015ms. This demonstrates a short, normally recovering pending window.
- natural-7/db21: maintenance calls spawn at388.286ms, worker enters388.318ms,
  clears at388.319ms. This is the first recorded maintenance invocation for this
  DB, not proof of recovery after a400ms periodic tick. Other submit-triggered
  workers are being created around it; no foreground tail was present.

## Binding and observation limits

[source-bindings.json](source-bindings.json) retains old/current full-function
hashes and individually reviewed relocations. Existing collector callbacks,
request layout and pool field offsets are guarded; no old page/worker identity
is assigned to a new run. Most changed literals are static addresses shifted
by749632 bytes; two additional constructor-error diagnostic references move
separately. No wildcard execution-hash acceptance is used: complete generated
inventory is bound to the original CI guest and the actual hook preimages are
recorded. This is structural C correspondence, not a full guest symbol map.

The existing actual request generation/park/notifier observer is reused. Repeated
queue scanning under the guest mutex is replaced with enqueue/dequeue events
and bounded state records at existing synchronized sites. Worker-entry/init/
clear events inspect no unlocked shared guest counters. Per-module actor labels
distinguish submit/wait_begin/maintenance. Raw reduction checked every recorded
read's unique generation-bound enqueue/dequeue interval (64,634 stages including
control) and chronological I/O/group/callback ordering before discarding raw data.

Mutex-trylock skips are not directly tagged by a dedicated hook: maintenance
entry/return and its actual actions are recorded. With no long queued request,
no skip explanation or first-rescue cause is inferred. Pending-refusal is not
identical to unreported waiting; the full causal interleaving remains unknown.

Focused read/dispatch/progress race controls pass, including wrong notifier,
request reuse/write exclusion, retired scope/timeout/unrelated latch, wrapped
queue, invalid queue and journal overflow. The live control has a same-DB guest
profile inside the SLEEP interval. Every valid run has nonempty I/O and progress
records, no truncation and balanced worker/wait lifetimes. These controls validate
measurement mechanics, not completeness of C++ thread-pool correctness.

## Replay, reproduction and retention

```sh
python3 benchmarks/pool-worker-progress/analyze.py --check
```

Read-only replay checks exact compact timing histograms, spawn intervals, census,
summary and checksums without deleted temp or network. All original raw-file
hashes/sizes are retained, but full request and task histories are deliberately
not retained or reconstructible from the histograms. Selected event windows and
the control's complete matching-DB profile blocks retain original/published hashes.
No CI REST responses or raw build logs are added. Compact results are about0.5MiB.

A new authorized reproduction uses an owned8GiB workspace/free6GiB, this branch,
and a separate clean checkout of guest origin f4325722. Acquire original guest/
translation ZIP artifacts13895265003/13895086139 and use the existing
`tests/uca_copy_execution.py`; its archive/guest/inventory checks remain intact.
Copy progress.go.txt to temp/; run make_overlay.py with WORKTREE, isolated PRODUCT,
TEMP. Extract harness d24087ee into PRODUCT; apply the existing
uca-p8-attribution/reproduction/instrument.py, then finish_harness.py.
Add progress_test.go.txt to the overlay test mapping. Focused Go-race tests run
before one Go1.26.10 diagnostic compile. Build with private caches and disk guard;
run_probe.py WORKSPACE uses per-process140s watchdogs and disk checks between
processes. reduce.py WORKSPACE reduces raw results; analyze.py --check replays
saved results. Keep installation evidence bound to its actual execution source.
The eight natural suites are a ceiling, never repeated until favorable.

The finite investigation stops at NOT_REPRODUCED. Budget was active2h/tooling30min,
heavyCI0, C builds0, disk8GiB/free6GiB. Wall elapsed includes downloads, compilation
and command approval waits; active/tooling minutes were not separately metered,
so no exact time-budget compliance measurement is claimed. Cleanup removes owned
artifacts, generated sources, binaries, caches, raw journals and worktrees after
preserving this report. No product fix, main integration or release occurred.
