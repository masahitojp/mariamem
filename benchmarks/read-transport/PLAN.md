# Response transport counterfactual
Baseline product source_commit 6558ee8fb2211313a8aa0ea6070ac5256767811a.
Only guest stdout os.Pipe -> unbuffered io.Pipe; request OS pipe, SQL, triggers,
frame decoder, lifecycle unchanged. Experimental selector/counters, no adoption.
One binary, Go 1.27.4, GOMAXPROCS=8, CGO=0, sync Close, MaxForks16.
Correctness: guest controlled transport and explicit response-pipe boundary tests;
matched SQL assertions and all 70 suite bodies both arms.
Diagnostic: each arm 1 GetOrder4000 counter process, 1 profile process.
No timing inference from observer/profile runs. Counter writes are io method calls,
not direct kernel syscall counts. 2 SELECT/order; all fixture setup outside probe.
Timing: each arm 1 warmup then five AA and five AB pairs for query4000 and P8 suite,
interleaved fixed seeded ordering. No adaptive reruns/exclusions. All 44 process
runs retained including warmups. CPU, process wall, suite wall, phase spans saved.
Abort if correctness fails; fix only concrete defects and retain failure evidence.
Recommend further work only if mechanism and wall/CPU evidence support it; shared
Mac noise/semantic/platform limits explicit. No 10% guarantee or main integration.
