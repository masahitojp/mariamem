# macOS v0.5.1 Light Fork serial/parallel comparison

Ten alternating pairs of workers=1 and workers=4. Same existing ownedprepared
Go Light workload: payload=0 (one 1024-byte row), one table, four children,
app-connections, lifecycle=fork. One preparation/Snapshot precedes the child loop.
Each child runs count/point, commit visibility through two connections, rollback,
SQL disconnect/WaitDisconnected and Close; the baseline closes after all children.

`run.py` checks the typed v0.5.1 release pin, clean standalone checkout and actual
Go binary VCS revision/modified=false. A benchmark-main-only overlay records
operation start/end offsets plus final mmap counters. There are no host/runtime/
guest/generated-Go changes, no trace environment, and no oracle changes. Same
observer binary in both cohorts; no separate unmodified calibration. Default
GOMAXPROCS is retained, GOGC/GOMEMLIMIT/GOMAXPROCS overrides removed.

Use a fresh workspace and absolute W/GO_ROOT paths:

```sh
python3 scripts/experiment_workspace.py prepare light-fork-parallel \
  --branch experiment/light-fork-parallel --min-free-gib 20 --budget-gib 8
python3 scripts/experiment_workspace.py run --timeout 1800 light-fork-parallel -- \
  python3 benchmarks/light-fork-parallel/run.py --workspace "$W" --go-root "$GO_ROOT"
python3 benchmarks/light-fork-parallel/analyze.py --workspace "$W"
python3 benchmarks/light-fork-breakdown/collect.py --workspace "$W" --output evidence-public
```

Go1.26.8/CGO=0, build `-p 1 -trimpath -buildvcs=true`. Each workload timeout45s,
outer timeout1800s, owned budget8GiB, free reserve20GiB. Dependencies and localhost
TCP must be allowed. All 20 observations remain; five mmap creates/releases per
process must balance with final active/reserved/RW/failures zero.

Main metrics are full product elapsed time and four-child loop elapsed time.
At workers=4, the harness uses preparation+Snapshot+child-loop+baseline-Close for
product time. Sums of child Fork/SQL/Close times overlap and are diagnostics only.
Analyze each trial before taking medians; phase medians need not sum to total.
Interval overlap verifies concurrent calls/workflows, not simultaneous hardware
execution. Conservative ready-DB overlap stops before Close begins.

`analyze.py` replays result hashes, every operation interval, natural pairs,
median/min/max and overlap peaks without a binary. The previous collector stores
complete observations and path/whitespace normalization hashes. After preserving
and pushing evidence, delete clean source clones, Go caches, binaries and worktree.
No pgmem, Linux, Python, large fixture, memory peak, optimization or release work.
