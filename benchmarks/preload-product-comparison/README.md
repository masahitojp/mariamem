# Fixed OFF product candidate matched comparison

Product source_commit454121d62a9aba26a0516f022e0c0ed77b30b33e, baseline mainac8849d806bdd8fd504c1e44c27a809e8beed658; comparison3433a40bd4167daea2d8e364666bd5fcf18ef654; harness1977fff480c2f976bc23f4d2e1b8ff8db36ad128. Go1.27.4/darwin arm64,CGO0,GOMAXPROCS8,GOGC100. Same SUM/status audit, preaggregated revenue, synchronous Close, reader Fork,MaxForks16. Existing comparison-variance method:4warmups+10blocks/P1/P8 with alternating MPPM/PMMP,20 observations/product/P. All84processes/5880bodies PASS, both semantics checks PASS. Recursive storage guard between processes only. No exclusions/adaptive reruns.

| P | Maria median ms | PG median ms | paired block gap median | Maria mean ms | PG mean ms |
|---|---:|---:|---:|---:|---:|
|1|1264.554|814.913|+55.55%|1262.544|817.047|
|8|472.571|416.138|+10.20%|486.613|459.048|

Independent median gap P8+13.56%,5/10 paired blocks <=10%; paired range-10.27..+28.41%. P8 >1.2ownmedian runs2/20 each. Maria max584.728ms,PG805.093ms; Maria max sample210.026ms. Thus fixed OFF does not eliminate every slow sample. This is a new shared-host cohort, not a before/after ON/OFF estimate; both products slow/drift later. Do not claim stable10% target achieved or a causal improvement from historical medians. P1 serial throughput remains materially different. Ordinary Close semantics remain each product's own; physical-reclamation guarantees are not identical.

Local product Go1.26.10 generatedmemory integration (including effective OFF/fresh/Fork/reSnapshot/isolation) PASS. Source/license88checks,Go unit tests and vet PASS. Full check on unsupported local Python3.9 failed12 tests (2137pass99skip), including missing ExceptionGroup and exception notes; user explicitly directed no deeper3.9 investigation. Full check is not reported PASS. Existing both-OS/consumer CI will be submitted as operationverify; no CI result claimed here.

build.py extracts the same harness from immutable Git identity without adding it to product source; use workspace/{worktree,temp,evidence} layout and fixed product checkout, clone/check out comparison source, run build/measure/analyze (analyze requires modern Python statistics.correlation). All scripts, identities,raw per-process JSON/text,summary and localcheck retained. Budget8GiB/floor8GiB. Productization authorizes this candidate, not main integration/release. Disposable caches and clone are removed after retention.
