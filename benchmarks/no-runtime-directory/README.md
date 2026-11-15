# A1a: unused runtime directory allocation

Conclusion: removal is feasible in this limited spike, but consistent whole-batch speedup is not established. Recommend treating it as a small simplification candidate, not a demonstrated performance optimization. Integration requires removing residual dead field/helpers and updating ownership fixtures while retaining backend/capture-debt assertions. No adoption, main integration or release.

Measured source_commit: `4aa460d6001dc981423cef91e5f63f25e0ab48bb`; product baseline `c680bfe9ccbf80b012fce897c151fe5a7e42d1e3`. Baseline binary uses only mariamem.go from that commit through the recorded overlay recipe. Both arms share the added runtime-directory counter in the harness; path presence is counted, not a filesystem syscall trace. Candidate retains temporary field/helpers for fake-backend failure tests, but no real Database assigns a directory. Existing runtime_directory_ready timing marker remains for this spike and needs semantic cleanup before adoption.

Go1.26.10, macOS arm64, GOMAXPROCS8/GOGC100, CGO0. 48 children/process, same SQL and isolation checks as #206; synchronous Close in both arms. Timer includes final cleanup and Snapshot.Close. Eight warmups and 24 measurements, alternating baseline/candidate order per repetition; all 32 runs/1536 children succeeded. Each baseline run reports48 directory paths, each candidate run0. All mapping count/reserved/RW counters return to baseline; leases/handles checked by original harness. Transfer directories remain. No guest/runtime/engine patch changes.

|P/cap|paired wall median|paired percent median|faster pairs|paired batch CPU median|
|---|---:|---:|---:|---:|
|1/1|+6.77ms|+0.79%|1/3|+0.25%|
|1/2|-7.84ms|-0.90%|2/3|-1.74%|
|2/2|-6.96ms|-1.28%|3/3|-1.06%|
|2/4|+2.57ms|+0.51%|0/3|+1.97%|

All values are candidate minus baseline, with ratio medians computed per pair. P1/cap2 pair2 worsened+91.73ms (+10.42%); retained without exclusion or causal attribution. CPU medians range−1.74% to+1.97%; peak RSS paired medians+0.026% to+0.151%, no material RAM saving claim. Shared host, only3 pairs per cell, no A/A or confidence interval. Small effects and noise are not separated. No additional sampling.

Validation: root, mariamemtest and internal/host normal tests PASS, retaining existing concurrent-close, snapshot ownership and cleanup failure oracles. Selected actual guest TestPureMemory32* and TestProcessImageSurvivesIndependentRootsAndSnapshots PASS. Public source check PASS. No race rerun, explicit Live real-guest campaign, CLI/export qualification or other OS run: these are not established by this spike. Filesystem export/transfer is unchanged.

Reproduce: prepare a managed workspace at the measured SHA, retain a cache path per runner configuration (the recorded run borrowed the inactive paused close-stop-cost cache), run `run.py <workspace>` under guarded runner with5400s timeout,12GiB budget and12GiB reserve. inputs/binary buildinfo/raw runs and summaries are included. Baseline overlay recipe is in run.py; it restores the exact pinned baseline source. Initial source was clean and checked with scripts/git_identity.py before builds. The plan was committed first. Root user worktree was not changed.
