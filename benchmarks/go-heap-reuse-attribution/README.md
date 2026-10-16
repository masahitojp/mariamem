# Two-pair heap allocation attribution

Authorized continuation of [the released-source Fresh investigation](../../docs/reviews/go-large-fresh-investigation.md).
Scope: one hour including build/analysis/report; at most two alternating pairs of
v0.5.0/v0.5.1. Same 100 MiB, eight-table, four serial Fresh DB workload and unchanged
SQL/commit/rollback/cleanup oracle. No runtime, guest, generated-Go, GC policy,
block format or public API changes.

`run.py` creates clean standalone clones at both typed release baseline pins,
verifies commit/tag identity and actual clean Go binary VCS stamps, and builds
with Go1.26.8/CGO=0 using benchmark-only overlays. CPU sampling, default-rate
cumulative allocation profiles, and per-phase heap/GC/allocation-size counters
are enabled in all four cells. No new uninstrumented timing cohort is added.
ReadMemStats/metrics probes are outside phase timers but can affect subsequent
GC/scavenging; these timings do not establish uninstrumented product performance.
There is no additional forced GC or MemProfileRate adjustment.

Example, after preparing a workspace on this branch (absolute `W`/`GO_ROOT` paths):

```sh
python3 scripts/experiment_workspace.py prepare go-heap-reuse-attribution \
  --branch experiment/go-heap-reuse-attribution --min-free-gib 20 --budget-gib 8
# helper runs relative commands from its worktree:
python3 scripts/experiment_workspace.py run --timeout 2400 go-heap-reuse-attribution -- \
  python3 benchmarks/go-heap-reuse-attribution/run.py --workspace "$W" --go-root "$GO_ROOT"
python3 benchmarks/go-heap-reuse-attribution/analyze.py --workspace "$W"
python3 benchmarks/go-heap-reuse-attribution/collect.py --workspace "$W" --output evidence-public
```

Builds need dependency access, workload needs localhost TCP, and the unchanged
process helper needs normal macOS process accounting. Actual campaign recovered
from a pre-build helper cwd error and sandbox DNS error before any workload;
it was manually supervised with `run_guarded` per cell (180 seconds, 8 GiB owned
budget, 20 GiB free reserve), then finalized with the workspace helper. These
setup failures are not extra measured trials. `observer-inputs.json` records them.

`analyze.py` retains every phase, parses every allocation sample/location, and
classifies *estimated* allocated bytes exclusively: D block storage, other MemFS,
SQL driver/wire transport, other workload descendants, other/background.
The allocation histogram is allocation **counts** by approximate size bucket;
it cannot independently identify a caller. HeapReleased snapshots are current
page counts, not cumulative reuse/return syscalls. CPU parser is reused from the
prior investigation. Systemstack still may hide the allocating application;
if so, stop at unassigned reuse CPU instead of claiming causal attribution.

Public evidence retains complete raw profile text (all samples/locations/mappings),
results, overlays, hashes and analysis. Eight small original binary profiles remain
in the local compact evidence; caches, clones and binaries are disposable.
`collect.py` records original/stored hashes and normalizes only paths/whitespace.
Public text replay requires no binary profiles or new benchmark execution.
