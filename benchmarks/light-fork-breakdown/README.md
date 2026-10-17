# macOS v0.5.1 Light Fork breakdown

`run.py` verifies the typed v0.5.1 pin and builds a clean standalone checkout with
Go1.26.8/CGO=0. Go overlays add observational timing events only to handwritten
host lifecycle files and a final benchmark mapping counter. Complete overlay
sources and original/observer hashes are retained. No guest/generated Go,
public API, lifecycle branch, failure oracle or GC policy is changed.

Workload: existing `ownedprepared`, payload-mib=0 (one 1024-byte row), tables=1,
workers=1, forks=4, app-connections, lifecycle=fork. It includes count/point,
commit visibility across two connections, rollback, independent children and
SQL disconnect before Close. It is not established identical to the user-supplied
Linux/pgmem Light fixture. No pgmem or Linux results are produced by this recipe.

Ten alternating trace-off/on pairs use the same observer binary. Traces are
opt-in through existing `MARIAMEM_TIMING_DIR`; off is not a separately built
unmodified calibration. Trace filesystem writes can alter scheduling and timing.
Each process must pass its unchanged SQL oracle and balance all five mmap
lifecycles with final active/reserved/RW/failures zero. No selected-trial deletion.
Workload timeout=45s; outer timeout=1800s; owned budget=8GiB; free reserve=20GiB.

From a fresh workspace on this branch, using absolute W and GO_ROOT paths:

```sh
python3 scripts/experiment_workspace.py prepare light-fork-timing \
  --branch experiment/light-fork-breakdown --min-free-gib 20 --budget-gib 8
python3 scripts/experiment_workspace.py run --timeout 1800 light-fork-timing -- \
  python3 benchmarks/light-fork-breakdown/run.py --workspace "$W" --go-root "$GO_ROOT"
python3 benchmarks/light-fork-breakdown/analyze.py --workspace "$W"
python3 benchmarks/light-fork-breakdown/collect.py --workspace "$W" --output evidence-public
```

Build needs dependency access and workload needs localhost TCP. `analyze.py`
replays all result hashes, cohort phase sums and nested trace envelopes.
Snapshot finish includes FreezeHeap: the reported outside-freeze remainder is
subtraction of nested envelopes, not separately measured pure InnoDB shutdown.
Child close operation includes disconnect/WaitDisconnected plus Database.Close;
finish_breakdown is a smaller host shutdown envelope. startup excludes earlier
API/platform work, so both boundaries are retained. Multiple medians do not sum
to the median total. Cleanup preserves evidence while discarding clones/cache/binary.
