# Issue156: controlled generated-guest mechanism

**The pending-clear stall also reproduces through actual generated MariaDB
pool code and the Go/WASIX thread/futex implementation. All 18 fixed cases PASS.
The cause of the original PREPARE tail remains UNPROVEN.**

Together with the [native control](https://github.com/masahitojp/mariamem/tree/158cea31ddcd7c96a514ac8ad616f95a5ada4177/benchmarks/pool-pending-control),
this establishes a scheduling mechanism that does not require a missing WASIX
syscall. Recommend next connecting the real PREPARE/read task and its unreported
wait to this exact sequence, by a bounded source-path analysis before more
sampling. Do not select a pending-clear policy change, read4 setting, or shorter
timer solely from this constructed case. Keep #140/#156 open. UCA integration is
already complete and independent.

## Fixed observations

| Condition | Cases | Observed behavior |
| --- | ---: | --- |
| Pending overlap + unreported A wait | 6/6 PASS | B stays queued until explicit maintenance |
| Same overlap + A wait_begin/end | 6/6 PASS | B progresses without the later maintenance trigger |
| B submitted after A begins | 6/6 PASS | No pending refusal; B progresses |

Each condition runs requested/effective concurrency1 and16, three repetitions.
Dynamic pool min1/max500 is the actual generated factory's default. It differs
from native's min1/max32, but neither maximum binds (two workers each).
Read-group limits and real InnoDB task contents are not modeled.

The first worker is held in its existing init callback, after the original
callback runs. Submitting B while creation_pending is set hits the actual refusal
branch. Releasing init clears pending; actual task::execute invokes synthetic A,
which waits through the real host Futex_wait. In the unreported arm, the measured
50.483–52.070ms deliberately imposed observation windows all show
queued1/active1/waiting0/long0/pending0. Actual maintenance then supplies progress.
The window is not a reproduction of the earlier approximately400ms latency.
All 18 cases invoke the real futex wait once; source hooks and exact event order
are checked. Merely setting concurrency16 does not supply the missing progress
check. This says nothing about production throughput at16.

All task refs reach zero; two controlled workers retire and the pool destructor
returns. Normal guest shutdown then completes through StartInstance, including
WaitThreads and mapping disposal. Active mappings are0 before and after every
case. This is stronger lifetime observation than native detached-worker callback
counts alone, but not a resource-exhaustion campaign or performance measurement.

## Execution and boundaries

- Product baseline source_commit: `8df45792a927e440972266ee799d6f7223713e14`.
- Successful harness source_commit: `43185bc4565089cc4e218da1b3e1ac8e05966c32`.
- Guest SHA256: `332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22`.
- MariaDB source: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- macOS27.2 arm64, Go1.26.10; one observed host, no Ubuntu/matrix claim.
- Three Go build invocations (108.3s,8.1s,100.1s); final test0.78s.
  No guest C rebuild, CI, application SQL/PREPARE workload or natural sampling.
  Normal guest startup still initializes its ordinary background workers.

Exact-function hashes guard the diagnostic overlay. The pool's actual
submit/get_task/add_thread/worker_main/wait_begin/end/maintenance and task execute
run unchanged except event taps and suppression of this controlled factory's
periodic timer scheduling. Maintenance is first primed on an empty queue to avoid
an artificial long-task classification. Normal guest timers remain active.
Synthetic task callbacks/refcounts and the first init barrier are harness code.
The test does not measure periodic timer accuracy or claim an upstream bug:
unreported blocking is an essential precondition.

Two harness attempts are **INVALID**, not negative mechanism results:

1. The initial allocator call was incorrectly assumed to zero memory. Fn157 is
   aligned allocation with a malloc fast path. First execution trapped on an
   unaligned atomic before A started; explicit zeroing/alignment checks fixed
   the invalid task construction. The exact offending address was not captured.
2. The next attempt reached the final event-count assertion after the controlled
   pool operations, but also counted ordinary startup pools and suppressed their
   timer scheduling. A root assertion bypassed normal guest shutdown, so join
   waited for ordinary background workers. One extra3s stack-only execution of
   the same binary localized that assertion. The final harness scopes timer
   suppression to the controlled construction, filters by its pool pointer, and
   lets normal shutdown run before reporting a harness assertion.

The initial one-build estimate was therefore exceeded by two harness repairs;
no natural results were rerolled or selected. See [assessment](results/assessment.json)
for every source identity, cost and raw/published hashes. These diagnostics are
not production timer, pool or cleanup fixes.

## Replay and reproduction

`python3 benchmarks/pool-pending-guest/check_results.py` is read-only. It checks
all18 cases/event ordering/state/lifetime and rejects six corrupt-evidence
controls (missing case, false PASS, wrong queue state, mapping debt, foreign pool,
reordered events). `SHA256SUMS.json` covers the retained harness/report/results.
All cases and events are kept in compact JSON; no CI raw REST data or build tree.
Selected diagnostic stack paths are normalized with original/published hashes.

For execution, use a disposable worktree with its parent `temp/` and `evidence/`,
Go1.26.10 available, and the experiment-workspace budget guard (5GiB/free6GiB).
At the retained source, run:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 benchmarks/pool-pending-guest/run.py
```

The driver refuses a dirty tracked/untracked tree, validates bindings, constructs
an overlay under temp, builds only the diagnostic test and executes the fixed
matrix. New outputs go to sibling evidence, not checked-in results. Set an owned
GOTMPDIR under temp when running under manual disk supervision. Final report and
replay tooling were added after the successful measured source; the controlled
harness/bindings and all product runtime bytes are unchanged from that source.
Owned build/cache/overlay cleanup is part of completion.
