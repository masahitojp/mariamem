# Same-cohort synchronous/async Close comparison

Conclusion: async Close provides a small, mixed whole-suite benefit, not a stable general speedup. P8 paired async/sync median-1.37% (6/10blocks); external process wall+0.82% (3/10faster); CPU-0.012% (5/10). Recommend retaining CloseAsync as an optional API and ordinary Close as baseline; no further product change from this campaign.

Product source_commit454121d62a9aba26a0516f022e0c0ed77b30b33e (fixed startup preloadOFF), comparison3433a40bd4167daea2d8e364666bd5fcf18ef654, harness1977fff480c2f976bc23f4d2e1b8ff8db36ad128. Same Go1.27.4/darwinarm64,CGO0,GOMAXPROCS8,GOGC100,SUM/status-column audit,preaggregated revenue,interpolation,readerFork,MaxForks16. Same Maria binary selects existing MARIA_ASYNC_CLOSE. Both semantic checks PASS.

Fixed63processes (3warmups+10blocks×6),4410case bodies PASS. Each block cycles permutations of sync/async/pg followed by reverse;20measured per arm. No adaptive repeats/exclusions or internal tracing. Cleanup includes Wait and Disposed for every async handle, Snapshot and shared-reader Close. Recursive storage guard only between processes. Physical cleanup semantics of comparison ordinary Close remain its own.

| P8 whole elapsed | Sync | Async | Comparison |
|---|---:|---:|---:|
|median ms|476.100|482.154|413.628|
|mean ms|488.023|484.335|420.547|
|max ms|581.529|527.616|510.467|
|runs>1.2ownmedian|2/20|0/20|1/20|
|final cleanup median ms|2.460|3.682|0.201|

Paired block gap vs comparison: sync+16.79%,async+14.69%. These are a new shared-host cohort, not an improvement/regression relative to previous+10.20% comparison. Independent median ratios are different statistics. Async median is1.27% slower than sync while mean0.76%faster; paired median favors async1.37%. Report all rather than selecting one statistic.

Sync max sample432.274ms,async159.974ms,comparison111.260ms. FixedOFF and async do not establish a cure for long waits; absence in20async observations cannot prove frequency reduction. Tails and typical latency differ. No whole-lifecycle termination costs were moved outside timing. No CI was polled, no code/API/main/release change.

Inputs,hashes,all process traces/logs,summary,build/measure/analyze scripts and pre-fixed plan retained. Reproduce in workspace/{worktree,temp,evidence} with pinned sources; shallow comparison clone must include exact commit. Budget8GiB/floor8GiB,build900s/measure900s. Cache/clone/binaries are disposable after preservation.
