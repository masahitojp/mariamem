# Comparative variability investigation

Product pins: mariamem6558ee8fb2211313a8aa0ea6070ac5256767811a;
pgmem3433a40bd4167daea2d8e364666bd5fcf18ef654. Same prior matched harness:
SUM/audit UPDATE OF status, interpolation, preaggregated revenue, shared reader
Fork, MaxForks16, synchronous Maria Close. No empty-write/Go-pipe prototypes.
Go1.27.4, CGO0/GOMAXPROCS8/GOGC100. P1/P8 refers test.parallel, not Go threads.

Question: is slowdown/dispersion shared, specific to mariamem, or concentrated
in a particular stage? Can a low-variability observation narrow the gap?
No claim that fast quantiles are noise-free or attainable performance guarantees.

Before build pin both Git identities. Build under disk monitor; STOP that monitor
before timing. No concurrent compile, recursive scan, profile, or background probe.
Only pre/post capacity checks and cheap load averages. Allow localhost bind.

Finite timing:1warmup each product/P=4;10 blocks per P of four sequential runs,
M,P,P,M on even blocks / P,M,M,P on odd. Interleave P1/P8 blocks with fixed seed218.
84suite processes,80measured,20samples/product/P. Both AA contrasts and paired
round geometric-mean ratios. No adaptive repetitions/exclusions; retain failures.
Whole elapsed/process CPU/RSS/rusage context switches, all existing phase spans,
new suite_run/writer_cleanup/final_cleanup spans, start/end Go runtime metrics.
Metrics are Go runtime only, not all engine/OS memory/scheduling.

Analyze medians, MAD, empirical quartiles/p90/max, slow count>1.2x own median;
within-block AA, cross-product ratios and co-movement. Compare fastest/slowest
quartiles of each product by exact sequential setup/run/final partition. Concurrent
Fork/sample span durations are descriptive, never summed into wall attribution.
Trace only if saved data needs a subsequent specifically chosen probe; not an
unbounded performance or causality claim. Baseline/performance changes unapproved.
8GiB budget/8GiB free, build1200s/timing900s, eachsuite180s. Preserve/cleanup.
