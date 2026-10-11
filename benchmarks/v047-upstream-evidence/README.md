# v0.4.7 paired product and qualification evidence

Purpose: detect translator-induced execution/resource regressions, not establish
a speed ranking. [Migration review](../../docs/reviews/v047-upstream-migration.md)
and [product report](../v047-product-validation.md) own interpretation.

The original v0.4.6 evidence is retained unchanged in `../v046-usability-evidence`.
This campaign rebuilds the released v0.4.6 source and candidate on the same host
with Go1.26.8, `GOTOOLCHAIN=local`, `CGO_ENABLED=1`, `-p 1 -trimpath -buildvcs=false`.
Benchmark source identity is recorded separately from binary hashes/build flags;
release artifacts require embedded clean VCS identity and use the canonical path.

## Reproduce

1. Prepare a guarded disposable workspace: 24 GiB budget, 20 GiB minimum free.
   Pin v0.4.6 using `release/baselines/v0.4.6.json` and `scripts/git_identity.py`.
   Create a separate detached baseline worktree and candidate worktree.
2. Copy **only** candidate `benchmarks/ownedprepared/{main.go,resources.go}` to the
   disposable baseline worktree. This gives both sides identical opt-in observers;
   no library/generated/SDK file is changed in the baseline.
3. Using the exact pinned Go1.26.8 compiler with switching disabled, build
   `./cmd/mariamem-host`, `./benchmarks/ownedprepared`, and the separate module
   `benchmarks/competitive` to `temp/binaries/{v046,v047}/` (binary names
   `mariamem-host`, `ownedprepared`, `competitive`). Use the flags above.
   Build `benchmarks/tools/process_cost.c` with `cc -O2` as
   `temp/binaries/process-cost`. Record compiler version and binary SHA-256.
4. Create a task-local Python3.14 venv using the historical product dependency
   pins. Pre-pull the immutable native MariaDB image in `product/inputs.json`.
   Docker CPU/memory configuration must match the report. Do not run competing
   benchmarks, builds or tests. Compilation/image pulls are excluded.
5. With Go1.26.8 first on PATH, `GOTOOLCHAIN=local`, task-local TMPDIR and no
   GOMAXPROCS override, invoke the existing-scenario orchestrator:

```sh
python benchmarks/v047-upstream-evidence/run-product.py \
  --baseline /absolute/workspace/temp/baseline \
  --candidate-binary-source <actual-build-source-commit> \
  --binaries /absolute/workspace/temp/binaries \
  --workspace /absolute/workspace --output /absolute/workspace/evidence/product
python benchmarks/v047-upstream-evidence/summarize.py /absolute/workspace/evidence/product
```

The output directory must be fresh. Warm-up pilots are excluded from summaries.
Normal scenarios retain three trials / four tests; 100 MiB retains one trial.
Paired order alternates; native anchors run once per original cell, since they
contain no translator. The guard samples disk every five seconds, with 900-second
cell timeout. Go process RSS above 8 GiB stops the campaign after that cell;
this is not a hard in-flight memory quota. Python containers retain 768 MiB / two
CPU limits and at most four parallel workers. Failed SQL assertions stop execution.

## Counter meanings

- Peak RSS: OS process high-water (`getrusage`), Go driver process only.
- Go heap peak: 25 ms sampled heap objects; may miss shorter peaks; excludes mmap.
- Cumulative allocation: TotalAlloc difference; never interpreted as retained RAM.
- Post-Close: explicit phase samples; final samples follow the existing diagnostic
  GC, not a product guarantee that Close forces Go heap return to the OS.
- `linear_memory_virtual`: reservation/protection and owner counts; **not physical
  memory**. Final active count and creates/releases prove ownership accounting,
  not page-residency attribution. Peak enabled range is not Peak RSS.
- Prepared file mapping extent: virtual extent, not unique/resident page count.
  MAP_PRIVATE can share clean pages but OS CoW sharing is not directly quantified.
- Observer goroutine is alive when the final Go point is recorded (+1 expected).
- Python after-SQL process samples are not peaks. Docker CPU/memory samples are
  separate; runner CPU excludes VM/container CPU. Do not add overlapping counters.

`cells.csv` retains every non-pilot cell; `summary.csv` has n/p50/p95/min/max;
`comparison.csv` gives absolute and relative paired medians. `phases.csv` keeps
ready, preparation, Snapshot, query and Close operations separate (overlapping
parallel-operation CPU must not be summed). Three-trial p95 is
interpolated/descriptive, not a stable tail estimate; n=1 has no inference power.
No slow sample is discarded. The separate `tail-probe/` has four paired repeats
each of Light Fresh and 10 MiB four-parallel Fresh, prompted by observed startup
and RSS tails. It is not pooled with the original matrix; its commands and summary
are retained in qualification records. `product/*.json` retains phase times and SQL-oracle
completion. `qualification/` preserves commands/outcomes, race visibility controls,
source/guest/generated identities and actual consumer versions. Personal paths
are normalized; original and retained hashes are recorded in `evidence-manifest.json`.
SHA256SUMS covers the retained evidence and reproduction files.

Reduce evidence, commit/push, then remove binaries, wheels, SDK/module/build
caches, source extracts and completed worktrees with Git-aware cleanup. Do not
retain these recreatable directories merely to preserve a result.
