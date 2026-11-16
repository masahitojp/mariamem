# Comparison variance investigation — 2026-11-16

## Conclusion and recommendation

Long-tail reduction could materially improve average P8 suite time. This campaign contains a real prolonged guest wait, not merely a noisy stopwatch. It does not establish why notification was delayed, or demonstrate a fix. Recommend a bounded follow-up connecting the observed prepared INSERT to its guest wait object, owner and notification path. Do not adopt transport changes or raise resource limits from these observations alone.

## Source and method

Product source_commit: `6558ee8fb2211313a8aa0ea6070ac5256767811a`.
Measured harness source_commit: `1977fff480c2f976bc23f4d2e1b8ff8db36ad128`.
Comparison source_commit: `3433a40bd4167daea2d8e364666bd5fcf18ef654`.
No product runtime changes: additions are suite/final/writer-cleanup spans and Go runtime metric snapshots in both harnesses. macOS 27.2.1 arm64, Go 1.27.4, CGO=0, GOMAXPROCS=8, GOGC=100. This is benchmark tooling, not Go 1.26.10 product qualification.

Matched 70-case suite: 50 reads and 20 writers, SUM triggers and audit enabled, MariaDB UPDATE OF status with same-value guard, parameter interpolation, preaggregated revenue SQL, shared reader Fork, MaxForks=16. Maria uses synchronous Close. Each library retains its ordinary close semantics; physical reclamation guarantees are not claimed identical.

Fixed 84 processes: four warmups plus ten blocks at each P1/P8; each block alternates M/P/P/M and P/M/M/P, with P order shuffled using seed 218. Twenty observations per product and parallelism. All 5,880 case bodies passed. No sample exclusions or adaptive repetitions. Recursive disk scans run only before/after each process, never concurrently with timing. Internal suite elapsed includes setup, test run and final cleanup; external process wall is separately retained. Runtime metrics do not measure guest heap or all OS scheduling effects.

## Results (internal suite elapsed, ms)

| Parallelism | Maria median | Comparison median | Median ratio gap | Maria mean | Comparison mean |
|---|---:|---:|---:|---:|---:|
| P1 | 1211.881 | 791.567 | +53.10% | See summary.json | See summary.json |
| P8 | 432.027 | 397.851 | +8.59% | 463.952 | 398.405 |

P8 block-paired geometric-mean ratio median is +8.03%; seven of ten blocks are within +10%, range +0.41% to +96.18%. P8 q25 is 411.878 versus 388.545 ms (+6.01%). This is not a new product improvement: Maria's previous cohort median was approximately 431 ms, whereas the comparison cohort changed from approximately 369 to 398 ms. Historical measurement/order/instrumentation differences prevent causal attribution.

P8 Maria has 2/20 observations above 1.2 times its median, versus 0/20 for the comparison. Adjacent A/A absolute difference medians are 3.34% and 3.85%. A/A does not rule out a level shift: both slow Maria observations are adjacent in the same block.

**Sensitivity calculation, not an achieved result:** actual P8 arithmetic-mean gap is +16.45%. Replacing only the two slow Maria elapsed values with its median, retaining the other 18 values and all comparison values, gives 427.127 versus 398.405 ms (+7.21%). Original samples remain included in every reported actual statistic. This shows the magnitude of the tail opportunity, not the outcome of any optimization.

P1 is relatively stable (relative MAD 0.93% / 1.19%) yet has a +53.10% median gap. Thus variability cannot explain all baseline work or serial throughput differences.

## Natural slow runs

`p8-b5-s1-maria`: elapsed 774.089 ms, CPU 2117 ms; final writer `TestShipOrder/pending_rejected` has LoadSample 486.833 ms. Its cleanup ends 343.941 ms after the previous writer's cleanup.

`p8-b5-s2-maria`: elapsed 826.465 ms, CPU 2159 ms; final writer `TestCancelOrder/pending` has LoadSample 487.722 ms. Its cleanup ends 425.050 ms after the previous writer's cleanup.

Surrounding comparison observations are 415.080 and 400.466 ms. Setup/final cleanup and GC CPU do not explain the large added suite interval. The natural cohort identifies the sample-loading phase, not its exact SQL or wait object.

## Separate bounded diagnostic campaign

Eight fixed P8 runs with Go runtime tracing plus harness regions all passed (560 cases). Trace overhead means these are excluded from speed statistics. Run 7 reproduced a 480.827 ms sample region in `TestDeleteUser/user_15`; elapsed 824.600 ms.

The caller G192 waits 398.106560 ms in `mysqlStmt.query` / `LoadSample`, seed.go line 171: already-prepared `INSERT INTO orders(user_id,status) VALUES (?,?) RETURNING id`. This is execution, not PREPARE, and is neither UPDATE nor order_items INSERT.

The response chain is G8430 (guest pipe reader, 398.083 ms) → G8919 (Process.Call, 397.919 ms) → G8654 (monitoredCall, 398.061 ms) → G192. Waiting on the pipe is an effect, not proof that the pipe is the cause.

Lineage links G192's Fork to runtime G8429, reader G8430 and guest worker G8817. G8817 waits 394.118720 ms in AtomicWait/Futex_wait, from trace time 323443543983936 to 323443938102656. G17598 wakes it through Futex_wake → AtomicNotify → ThreadPool.wake. It resumes at 323443938121792, only **19.136 microseconds after becoming runnable**. Thus this interval is predominantly waiting for notification, not waiting 394 ms for the Go scheduler after notification.

The trace does not identify the wait address, lock/page owner, queue membership, or why notification was delayed. Worker creation near completion is not proof of a worker limit. Generated Fn identities are preserved with the exact source; old guest C-symbol maps must not be assumed applicable. This diagnostic resembles the natural phase/duration but does not prove that both untraced slow observations have the same cause.

## Existing issues and next decision

#140's old PREPARE/task-queue tail and #143's deferred UPDATE/UNDO wait were consulted. Neither is declared the same cause or reopened: this diagnostic is prepared INSERT execution. #162's long Close behavior is separate; no recurrence of the roughly 69-second Close was observed here.

Next bounded investigation should identify this INSERT's futex address and module, map the current generated frames to current guest symbols, and bind enqueue/wait/notify to the actual owner or task. Only then choose between queue/worker policy, engine locking, or shim notification changes. Keep natural timing and intrusive diagnostics separate. This task does not implement or approve a product change.

## Evidence and reproduction

`evidence/manifest.json` hashes every retained original and compressed file. `records.json.gz`, `summary.json`, `tail-impact.json`, campaign JSON/text, all eight raw traces, extracted stacks/lineage, build identities and scripts are preserved. Large files are gzip compressed; decompress to their original names before running scripts. Raw 890 MiB parsed trace text is reproducible and not retained.

Scripts use an experiment workspace layout (`worktree`, `temp`, `evidence`), not their committed location. Check out the measured harness commit, restore scripts under workspace evidence, follow build.py, measure.py, analyze.py, diagnose.py in order. Inspect PLAN.md first; use an isolated workspace and pinned inputs. Reproduction requires Go 1.27.4 and the pinned comparison checkout. Build cmd/trace with that toolchain, then run `gotrace -d=parsed run-7.trace` for the streaming trace parsers. Their workspace paths must point to the new workspace. Do not run recursive workspace monitoring during timed processes.

Experimental evidence is not intended for direct main integration; public-source checks reject raw .gz/.log artifacts. No runtime rebuild or broad product acceptance is warranted for this reporting-only change.
