# Public async Close fixed campaign

Base afe7d914, Snapshot cleanup-debt fix59b69894. No other runtime change.
Use CloseAsync/CloseHandle in the previous close-aa harness, with final handle
Wait/Disposed, lease0, mapping/reserved/RW and creates/releases checks retained.
Root/Fork consumed capture-debt regression must fail against old snapshot.go
semantically, then pass after fix. Focused root/guest/host/fixture and selected
actual guest checks precede benchmarking. No benchmark until these pass.
480totalchildren, P/cap1/1,1/2,2/2,2/4; same binary. Sync-AA and sync/async-AB,
4pairs each cell/comparison, alternating order, job shuffle seed119,150ms pause.
8warmup+64main=72processes/34,560children. No adaptive exclusions/repeats.
Go1.26.10 macOS arm64, CGO0,GOMAXPROCS8/GOGC100. Primary batch wall includes
final drain and Snapshot.Close. CPU/RSS/process counters retained; no stage
observers. Sync-AA measures same-mode variation, not async-AA. Four pairs/one
shared host cannot establish universal significance. Do not add old A1a gains.
If a comparable very long observation recurs, preserve all data and open an
Issue per Human direction; no automatic unlimited cause investigation.
10GiB scratch budget/free12GiB, timeout2400. Save all observations, reduce to
compact report, push fixed evidence, clean owned scratch. No main integration.
