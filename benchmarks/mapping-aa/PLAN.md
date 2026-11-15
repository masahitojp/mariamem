# Same-binary A/A repeatability check
Baseline mapping arm only, same binary path and identical environment for A and A-prime. Labels exist only in runner records; no rebuilt/copied binary.
B1 image, dirty0/1/64MiB, P1/P2,48 versus480cycles per worker. Same final-drain checks. One warmup per12 cells;6 pairs/cell, label order alternates, cell order shuffled by fixed seed119 per round. Total12 warmup+144 measurements. Pause150ms between processes. No extra sampling/outlier deletion.
Record batch wall/CPU, process wall/CPU/RSS/minor/major faults/context switches, UTC/load and label order. Counters from wait4 are process-wide, not batch-only. Compare signed and absolute paired ratios and duration spread. A/A measures repeatability, not prior candidate effect or a causal explanation. Larger batch only investigated as mitigation.
Go1.26.10,CGO0,GOMAXPROCS8/GOGC100;90m guard,12GiB scratch/free12GiB. Identity before build, safety/counter failure stops campaign. No runtime product changes.
