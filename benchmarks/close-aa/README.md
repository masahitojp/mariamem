# #119: interleaved Close A/A and A/B

**結論:** 空き枠あり480子ではP1/cap2とP2/cap4の両方で非同期側が6/6ペア速く、全解放込みwallのpaired中央値−1.65%/−1.42%。同時期A/Aの絶対比中央値0.29〜0.83%に対し一貫した方向が観測され、以前より「小さい実益がある」根拠は強まった。飽和条件の利益は明確ではない。A/Aの最大変動はA/Bに重なるため、雑音から完全分離・統計的確証・他環境での保証とはしない。

推薦: これまでの「一貫した利益が未確立」をこのcohortの範囲で更新し、採用判断は改善幅約1〜2%と公開API/回収契約の複雑さの釣合いとしてHumanに戻す。性能が不安定という理由だけで否定しないが、製品採用を自動承認しない。強い反対論は利益が小さく空き枠に依存すること。飽和時や実アプリのsuite全体にも同じ利益を約束できない。

## Fixed scope

Measured source_commit `ed5fa339eb9f3b87488f6785da97053fae050073`; product f563128520fc49097ac83ef47cdea2dee21ff62a, report/harness base c680bfe9ccbf80b012fce897c151fe5a7e42d1e3. Only close_evaluation_test child-count input changed48→48/480. No A1a/A2/B changes. evalDiagnostic=false. One binary path/hash for all comparisons; within A/A, identical argument/env values and labels only in runner. A/B changes only CLOSE_MODE. Clean/git_identity checked before build. Go1.26.10 macOS arm64,CGO0,GOMAXPROCS8/GOGC100, buildinfo/hostplatform saved.

Same1000row snapshot, SQL read/update/read and WaitDisconnected per child. P/cap1/1,1/2,2/2,2/4 ×48/480children ×sync-AA/stop-AA/AB ×6pairs.16warmups+288measurements=304processes,80,256children. All passed SQL/isolation/handle Wait/Disposed/lease zero and mapping count/reserved/RW recovery; creates/releases delta equals child count. No per-stage trace or simultaneous builds/tests. Existing runtime unchanged; broad integration/race/otherOS acceptance was not rerun. Warmups validate the expanded harness through actual guest.

Round jobs shuffle with seed119, pair label order alternates, pair members adjacent,150ms pause. Six pairs/cell. No exclusion/adaptive extra runs. UTC2026-11-15T07:36:35Z–07:58:36Z. Primary batch timer includes final handle drain and Snapshot.Close. Process counters include prep/exit; don't confuse them with batch CPU/wall. Shared host, power/thermal/CPU-placement not controlled.480children are a different batching condition, not a rerun relabelled as48.

## Results

A/B is stop−sync; ratio is100×(stop/sync−1). AA columns are medians of absolute per-pair ratios, not confidence bounds or a noise amount to subtract. Separate-arm medians are not substituted for paired differences.

|P/cap|children|AB median ms|AB median ratio|stop faster|sync AA abs median|stop AA abs median|
|---|---:|---:|---:|---:|---:|---:|
|1/1|48|+5.21|+0.56%|1/6|0.68%|2.72%|
|1/1|480|-62.73|-0.67%|5/6|0.41%|0.37%|
|1/2|48|-27.69|-2.94%|5/6|1.05%|1.34%|
|1/2|480|-150.51|-1.65%|6/6|0.40%|0.29%|
|2/2|48|-5.27|-0.94%|4/6|0.32%|1.17%|
|2/2|480|-24.25|-0.42%|4/6|0.82%|0.72%|
|2/4|48|-9.44|-1.71%|6/6|1.70%|1.00%|
|2/4|480|-81.67|-1.42%|6/6|0.83%|0.54%|

480children spare capacity: P1 AB ratio range−2.08..−1.27%, P2−1.85..−0.71%. A/A signed ranges P1 sync−0.28..+1.75%,stop−0.33..+1.79%; P2 sync−1.02..+1.04%,stop−2.05..+0.69%. Thus6/6 direction is encouraging but distributions are not disjoint. No inferential test/CI or equivalence claim is made. P1 saves paired median150.51ms/480children;P2 saves81.67ms. Not old48-child claims multiplied by10.

480children spare AB CPU paired medians P1+0.73%,P2+0.03%;RSS medians−0.02%/−0.03%. No substantial CPU/RAM-saving claim. Final drain independent medians sync→stop are about0.114→1.122ms(P1),0.115→1.802ms(P2), already included in totals.

Saturated480children: P1−0.67%(5/6) but range−1.23..+1.20%;P2−0.42%(4/6),range−4.21..+2.59%, alongside AA abs medians0.41/0.37% and0.82/0.72%. No robust universal saturated-speedup conclusion. The mechanism still retains leases until disposal; observed residual variation is not proof that saturation semantics changed.

48children reproduces a modest benefit in spare cells(P1−2.94%,5/6;P2−1.71%,6/6), but P1 range−6.79..+6.00%. Longer batches reduce several variations but not universally. This A/A workload is much steadier than the separate mapping microbenchmark; that earlier noise percentage must not be transferred here. The current experiment does not prove VM-lock causes or explain #162's historical tail.

## Reproduce and retention

PLAN.md fixed before run;run.py <workspace> builds then executes304processes under experiment_workspace.py run --timeout5400,12GiB scratch/free12GiB. analyze.py validates pair shape/mode identity and computes all tables from runs.jsonl. Additional record-time checks verified full count and resource restoration. Raw runs include wall/CPU/RSS/process faults/context switches/UTC/load, no dropped observations. Inputs,binary hash/buildinfo,source and scripts retained. Final artifacts pushed; ownedworktree/build/cache are disposable and cleaned after preservation. No public API adoption,main integration,release,or extra campaign initiated.
