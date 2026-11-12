# Issue156: actual dictionary wait notification control

**The localized notification restores queue progress in the controlled
pending-clear sequence using the actual dictionary eviction lock. All27 cases
pass. Original natural PREPARE causality remains UNPROVEN.**

Recommend continuing with the same narrow boundary as an experimental C patch,
then a fixed ordinary-workload comparison before product review. There is now a
concrete remedy for the demonstrated dependency, rather than only a synthetic
futex example. Do not change global pool policy or read/timer settings from this
result. The strongest objection remains: no natural capture binds pending refusal,
the same read request, and recovery in one timeline. Purge's shared dictionary
wait is also outside this prototype. A master-only patch may not remove the
original tail, and no whole-suite speedup has been measured.

## Result

| Condition | Fixed cases | Outcome |
| --- | ---: | --- |
| Pending overlap, no notification | 6/6 | Actual dictionary waiter leaves B queued until explicit maintenance |
| Same overlap, TLS-aware notification | 6/6 | B progresses without maintenance; waiting1 during contention, then0 |
| B submitted after A begins waiting | 6/6 | No pending refusal; B progresses without maintenance |
| Uncontended eviction | 6/6 | No slow-path hook, notification or futex wait |
| Contended caller outside pool | 3/3 | Null pool/worker TLS; notifications do not change pool accounting |

The first four conditions run concurrency1/16, three repetitions. Non-pool
control runs concurrency1, three repetitions. The first unreported observation
window was deliberately fixed at50ms; observed windows were52.015–52.063ms.
This is **not a measured reduction of a natural400ms SQL delay**.

Each of the21 contended cases enters the real host Futex_wait once at the actual
dictionary latch. Eviction cannot acquire it until the harness owner releases it;
its original unlock code remains in use. The reported arm uses public
`tpool_wait_begin/end` via TLS, not a direct method call on an arbitrary pool.
The dictionary remains below its configured eviction threshold and removed table
count is0 in all cases. Full table/cache mutation behavior is not exercised.

All27 cases dispose their task references, retire the expected workers (one for
fast/non-pool, two otherwise), return from pool destruction, finish normal guest
shutdown/WaitThreads, and restore active mappings0→0. The source-bound overlay
suppresses periodic maintenance only for the controlled pool; ordinary guest
background tasks/timers remain active and unmodified.

## What was changed

Only the failed try-lock branch of generated `Fn17744` (`evict_table_LRU`)
receives a diagnostic callback before/after its unchanged `Fn17733` lock wait.
The callback selects one guest TLS and arm, calls the real generated notification
functions, and records/checks accounting. Both arms therefore use one binary.
Canonical `guest/source.patch`, generated input files, host runtime and API are
unchanged. The callback is not proposed as a product API.

[The pre-execution plan](PLAN.md) records the prospective C form and caller
boundary. The two known master eviction paths have no lexical notification scope
around this call. The generic wait API is not nesting-safe; the selected caller
must have neither WAITING nor LONG set. Tests enforce this precondition and
balanced exit. Nested waits, LONG inputs, exceptional exits and an exhaustive
transitive caller audit are not covered. Purge's shared lock is explicitly out
of scope. Do not apply this wrapper indiscriminately to `dict_sys_t::lock`.

This extends the previous [generated pool control](../pool-pending-guest/README.md)
and [saved-stack source analysis](../../docs/reviews/issue156-source-path/README.md):
A now runs the **real eviction function and real initialized dictionary latch**.
A test owner holds the latch, and B represents work needed before that owner can
release it. No real PREPARE, disk-page task or request generation is present.
The full timer/master callback is not run by the controlled task.

## Identity, cost and reproducibility

- Measured source_commit: `59c5cda12473a34634dfc304525b1c15fad5dabc`.
- Product baseline: `8df45792a927e440972266ee799d6f7223713e14`.
- Guest SHA256: `332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22`.
- Upstream MariaDB: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
- macOS27.2 arm64, Go1.26.10. One Go build104.9s; one27-case test1.00s.
  No INVALID/retries, C build, CI, race build or natural sampling.
- Guard peak owned storage1,755,103,232 bytes, minimum free26,330,402,816 bytes;
  limits5GiB/free6GiB. Tooling time was not independently timed.

[Assessment](results/assessment.json) retains source identity, cost, raw/published
hashes and limitations. All rows/events are kept in compact JSON with whitespace
normalization only. No raw console/REST/source dumps or generated copies enter
this package. Post-execution changes add only replay/report/results/status;
measured overlay, harness and product bytes remain the recorded source.

Read-only verification:

```sh
python3 benchmarks/pool-dict-wait/check_results.py --checksums
```

It checks all27 fixed rows, progress/event order, lock exclusion, waiting state,
reference/worker/mapping cleanup and rejects eight corrupt-evidence controls.
Checksums bind the plan, harness, selected source hashes and results. This is not
a natural-causality or performance oracle.

To reproduce, create a disposable experiment worktree at the measured source,
with owned parent temp/evidence, Go1.26.10 and5GiB/free6GiB guard. The run driver
checks Git identity/cleanliness and full function hashes before overlay build:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 benchmarks/pool-dict-wait/run.py
```

Use the experiment-workspace runner for the900s deadline/disk guard. The script
has a120s test deadline, and fixed matrix; no random repetition/selection loop.
Delete owned caches/binary/downloaded sources/worktree after preserving compact
knowledge. UCA adoption remains independent; #140/#156 remain open.
