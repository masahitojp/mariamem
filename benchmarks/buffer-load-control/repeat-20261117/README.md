# Independent startup-preload repeat, 2026-11-17

## Conclusion and recommendation
OFF again improved observed whole-lifecycle time, with stronger directional support than the first campaign: block-paired elapsed median -3.35%, 9/10 blocks favorable; mean -5.06%. Two ON executions contained one approximately450ms sample-insertion region and prolonged the final writer; OFF had no comparable event in20 observations. These are real recorded application intervals, not just external stopwatch noise. They do not identify the responsible SQL/guest wait or establish that OFF prevents recurrence.

Recommend keeping OFF as a candidate for a bounded adoption/representative-workload check, rather than discarding it merely because individual A/A variation is larger. Production defaults remain unchanged until that decision; this task authorizes only the independent repeat. No further diagnostic trace/repetition was started. A rare-event fix, platform-wide benefit and a reduced cross-engine gap are not established.

## Fixed method and identity
Built source_commit `a0b61c8a05c4d81b8859e14cc08ef6c025c8ca6f`. Product/runtime/guest/harness code is identical to first measured source_commit `dec0054edb856b4f74eafae96bad24d0ac01166c` (Git diff checked); changes between them are report/evidence/docs. Product baseline6558ee8fb2211313a8aa0ea6070ac5256767811a and guest77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450 remain fixed.

Same Go1.27.4, darwin arm64, GOMAXPROCS8, GOGC100, CGO0, P8, MaxForks16, synchronous Close,70 cases, SUM+audit and preaggregated revenue SQL. Rebuilt executable has its own recorded hash (new path/VCS identity); within the campaign ON/OFF use exactly the same binary. Fresh/restored setting checks and SQL/trigger semantics PASS for both arms.

Fixed42 processes: ON/OFF warmups, then ten alternating ABBA/BAAB blocks (20 measured observations per arm). All2940 bodies PASS. No exclusions, adaptive reruns or tracing. All elapsed includes setup and final cleanup. Power snapshots before/after each process were added outside timing windows; this is the sole measurement-observer addition. Recursive disk scans run only between processes. See PLAN.md, build.py, measure.py, analyze.py and tails.py; these scripts expect workspace/{worktree,temp,evidence} siblings. This is an independent new cohort on the same shared host, not an independent host or proof of statistically independent samples.

## Power context
84/84 pre/post-process observations report AC Power, battery80%, AC attached/not charging. AC lowpowermode=0 before and after. pmset thermal/performance status failed with0xe00002bc (despite command returncode0); temperature/throttling therefore **unknown**. No power policy was changed. The Human reports AC had already been used during recent turns; first campaign did not record power. Do not label the first campaign battery-powered or attribute cohort differences to power.

## Whole-lifecycle results

| Metric | ON | OFF |
|---|---:|---:|
| elapsed median ms | 434.055 | 415.527 |
| elapsed arithmetic mean ms | 445.731 | 423.185 |
| elapsed range ms | 397.315–572.435 | 400.493–477.640 |
| external process wall median ms | 467.238 | 451.530 |
| CPU median ms | 2138.575 | 2067.895 |
| >1.2× own-arm median | 2/20 | 0/20 |
| elapsed >500ms | 2/20 | 0/20 |
| any sample region >200ms | 2/20 | 0/20 |

Block-paired OFF/ON medians: elapsed **-3.352% (9/10)**, external wall **-1.672% (6/10)**, CPU **-3.118% (8/10)**. Independent elapsed median difference-4.269%; mean difference-5.058%. All observations retained, including both slow ON runs. Prior campaign paired elapsed-1.166% (6/10), wall+0.135% (5/10), CPU-0.694% (7/10). Cohorts are reported separately, not subtracted as an intervention comparison.

Adjacent same-arm absolute A/A median is7.200% ON and7.213% OFF (five adjacent pairs each). A/A captures substantial local variability but does not itself invalidate a consistent paired direction. No formal significance or population tail-frequency claim is made. Both flagged ON runs are the last slot of ABBA blocks4 and8; deterministic order/shared-host effects remain plausible confounding, even though start/end arm alternates across blocks.

## Slow observations

| Run | Whole ms | Long sample ms | Lane | Last-writer gap ms |
|---|---:|---:|---|---:|
| p8-b4-s3-ON | 572.435 | 451.350 | TestDeleteUser/user_36 | 176.880 |
| p8-b8-s3-ON | 572.418 | 449.682 | TestCreateOrder/one_line | 156.863 |

Setup90.641/91.897ms and final cleanup2.044/2.140ms are not the large interval. The long sample ends566.719/566.853ms, followed by that writer's cleanup ending570.270/570.141ms; other writers finished176.880/156.863ms earlier. Thus the sample lies on the observed completion tail. It is sample preparation, not execution of the named DeleteUser/CreateOrder test body. CPU2170.332/2248.625ms; these do not prove a particular waiting mechanism. No SQL-level or guest trace was added, so similarity to the earlier~400ms wait is only a hypothesis. OFF's largest sample interval was110.309ms.

The third-slowest ON run477.792ms and slowest OFF477.640ms had sample maxima124.310/103.511ms: broader slowdown without the one450ms sample. This distinction matters: all slow values need not share one cause. Full top3/flagged phase records and load/context-switch observations are in tails.json. CPU load averages are contextual, not causal proof.

Run-level phase p50 medians also changed direction from the first cohort: Fork ON26.109/OFF27.605ms, sample72.105/70.668ms, test1.684/1.542ms. Do not generalize the first cohort's “Fork faster, sample slower” mechanism. Concurrent phase statistics cannot be added to explain total wall.

## Limits and completion
Only20 measured runs/arm in this repeat. OFF0/20 does not mean zero risk; ON2/20 versus OFF0/20 does not prove a tail-frequency reduction. No battery A/B, P1, other OS, large-table workload, cross-engine rerun or productization acceptance. The requested fixed repeat is complete. Evidence hashes, scripts and all observations are retained; binaries/cache/copied harness and completed worktree are disposable. Original user changes and unrelated worktrees are untouched.
