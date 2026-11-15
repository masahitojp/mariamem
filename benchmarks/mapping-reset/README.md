# B1: same-address mapping reset spike

**結論:** 小領域での内容復元・保護・失敗owner・二重/旧owner返却を検証できた。単体比較では64MiB dirty条件がP1/P2各2/3ペア改善したが、全条件でペア間の逆転があり安定したcycle短縮は未確立。現候補の製品pool接続は保留を推奨する。改善の可能性を棄却する結果ではない。

強い継続理由は64MiBのpaired medianがP1−5.86%、P2−12.12%だった点。しかし各々1/3ペアは悪化し、0/1MiBでは数ms〜数十msの変動で大きな比率の逆転が出た。実SQL/全体時間、OS別失敗保証、製品poolの容量/所有権が未検証のため、製品変更へ進む根拠には足りない。

## Fixed scope

Measured source_commit `c5f4ad43f5a1de57f8b758f7bd8e13505d5451ed`; baseline production `c680bfe9ccbf80b012fce897c151fe5a7e42d1e3`. Added only build-tagged test files and reproduction tools. No production runtime/guest behavior changed. Go1.26.10 darwin/arm64, GOMAXPROCS8/GOGC100, measurement CGO0; race safety CGO1. Clean source and git_identity checked before build. All files/binary identities retained.

Initial image is reconstructed from the pinned generated Fn67 data segments and initialization completion flag, then its entire256MiB hash is checked against layout.json before measurements. It exactly matches cab8819c9f8f25760c374e776474f82bb3774dc1c194d9b6d93f8f7f8329d5e1. OS page16KiB gives23 nonzero ranges. File is sparse2GiB, both arms use identical image/ranges. This avoids compiling the whole SQL engine, without substituting a synthetic image layout.

Baseline: NewStaticPageMapping(256MiB initial,2GiB max), Grow to320MiB, dirty selected pages, Close. Candidate: reserve one2GiB address slot per worker, same initial protection/image ranges/Grow/dirty, replace entire owned slot with anonymous PROT_NONE using MAP_FIXED, then reuse. Initial reserve and final slotClose are included in wall/CPU. Retained slot cap=P (1 or2); no process/global pool. This is an address reset, not a live Module restart or server_init optimization.

Dirty0/1/64MiB means one byte written per16KiB page, half in initial memory starting8MiB (image plus anonymous), half in grown memory starting256MiB. Both arms do identical writes. 48cycles **per worker**, so P2 is96cycles/process; do not compare absolute totals directly with #206's48 total children. No guest engine runs. Equal growth to320MiB is performed even for dirty0.

## Safety and limits

PASS: full small-region byte oracle through4 generations, image bytes and anonymous/grown zero restoration; duplicate and stale release; concurrent denied acquire/stale release; injected protect error, actual invalid-FD overlay failure, reset pre-syscall failure, injected error after successful replacement; failed unmap retained and retried; PROT_NONE access faults in a subprocess; final active mapping/reserved/RW counters return to baseline. Existing static-page isolation/partial-overlay/failure-owner tests passed. Selected safety tests also passed race.

Not proven: forced real kernel ENOMEM mid-overwrite, all failure semantics of the installed kernel, Linux behavior, stale raw pointers after slot reuse, old Module.Grow callbacks, constructor panic while publishing a pooled Module, Snapshot/global pool lifecycle. No Module is pooled or guest thread stopped by this spike. All raw access is confined to the sole current test owner. The helper is not production-ready; failed performance paths abort the process and are not a public recovery implementation.

Apple source inspected at f6217f891ac0bb64f3d375211650a4c1ff8ca1ea, bsd/kern/kern_mman.c MAP_FIXED block describes VM_FLAGS_OVERWRITE for atomic replacement, not deallocate-then-reserve. This supports the bounded success-path experiment; it does not qualify every installed-kernel failure path. The original syscall.Mmap slice remains registered for one final syscall.Munmap; successful replacements and injected debt retry were exercised. Production must audit its exact Go/OS handling before accepting arbitrary failure recovery.
https://github.com/apple-oss-distributions/xnu/blob/f6217f891ac0bb64f3d375211650a4c1ff8ca1ea/bsd/kern/kern_mman.c

## Finite result

12 warmup +36 measured processes =48 total,3456cycles; all succeeded with final counter restoration. No outlier exclusion or added samples. 3 alternating pairs per cell; fixed P/dirty cell order,150ms between processes, shared host, no A/A or confidence interval. Wall is mapping-cycle work plus final drain; no per-step clocks. CPU is process getrusage around the same interval; peak RSS covers whole test process.

|P|dirty MiB|paired wall median ms|paired ratio median|faster|delta range ms|
|---|---:|---:|---:|---:|---:|
|1|0|+2.57|+31.74%|1/3|-10.95〜+9.86|
|1|1|-17.08|-60.66%|2/3|-21.85〜+16.42|
|1|64|-14.02|-5.86%|2/3|-17.59〜+25.60|
|2|0|+5.32|+51.01%|1/3|-2.35〜+5.53|
|2|1|+16.07|+157.82%|1/3|-5.47〜+16.87|
|2|64|-41.86|-12.12%|2/3|-48.87〜+22.94|

All values are reset minus baseline; negative is faster. Percentages of very short0/1MiB runs magnify variation; raw absolute values are retained. No causal attribution to VM locks, noise, power management or address placement is established. RSS has an outlier (+28.76% in one P2/64MiB pair), not a memory-saving guarantee.

Derived operation counts (source path, not syscall trace): per48cycle worker baseline=48 reserve mmap +1104 image MAP_FIXED +96mprotect +48munmap; reset=1 reserve mmap +48 anonymous MAP_FIXED +1104 image MAP_FIXED +96mprotect +1munmap. All image overlays and page destruction remain. Total listed calls1296→1250; it is not a removal of the whole prior mmap/munmap interval. For dirty workloads the page reclamation/page-fault work also remains. Neither factory lock nor Module construction is measured.

## Decision and reproduction

Original question answered: owned-slot reset is feasible under tested conditions, but this one finite campaign does not establish reliable cost reduction. Recommend preserve this result and do not connect a product pool or rerun automatically. If continued, choose explicitly between a new measurement hypothesis (for example larger fixed cycle batches/A-A to resolve short-run variance) and a different reset mechanism; neither is approved by this report.

run.py <workspace> reconstructs/checks the fixture, runs safety and race gates, builds one binary and executes both modes. Use managed experiment scratch12GiB/free12GiB,5400s guard. First safety run at9dc5d2c78c5985b3ac4e165734ff0d50b90416ff completed before expanded committed campaign. Since workspace run receipt was completed, the campaign used experiment_disk.py under explicit manual supervision rather than changing its receipt. Source hashes in inputs.json identify the measured version. Full raw runs, compact checks and recipe retained; worktree/cache/sparse fixture removed after commit/push.
