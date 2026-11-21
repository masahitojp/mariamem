# Issue 233 reproduction

The product checkout must resolve to commit `5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c`. The harness imports the seed, schema, module and checksums from `706072d8dbfa76acb23d302d6bfaa08b91c444b5`. Fetch both commits in the reproduction repository. Keep this bundle available outside the product worktree.

For an archived result, run the following from the bundle. It reads the original pprof payloads, replays the integrity checks on the saved records and reconciles the exclusive CPU totals.

```sh
shasum -a 256 -c SHA256SUMS
python3 recipe/verify_results.py .
```

## Rebuild

In a fresh checkout, create the experiment branch at the fixed product commit. Prepare the owned workspace using the repository helper with an 8 GiB budget and an 8 GiB free-space reserve. In the commands below, W is the absolute workspace directory containing worktree, evidence and temp. B is the absolute path to the archived bundle.

```sh
git branch experiment/trigger-sum-bottleneck 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c
python3 scripts/experiment_workspace.py prepare trigger-sum-bottleneck \
  --branch experiment/trigger-sum-bottleneck --budget-gib 8 --min-free-gib 8
W="$PWD/build/experiment-work/trigger-sum-bottleneck"
(cd "$W/worktree" && python3 scripts/git_identity.py inspect HEAD)
cp "$B/recipe/regenerate.sh" "$B/recipe/run-builder.py" "$W/evidence/"
git clone --bare --depth 1 --single-branch --branch experiment/trigger-sum-bottleneck \
  "file://$PWD" "$W/temp/source.git"
python3 "$W/evidence/run-builder.py" > "$W/evidence/builder-space.jsonl"
python3 "$B/recipe/verify-map.py" "$W/worktree" "$W/temp/output" "$W/evidence"
```

The builder uses Docker Linux arm64 and the repository's Ubuntu image digest. It downloads and checks the pinned SDK, compiles at the canonical paths, hashes the linked and optimized WASM, then runs the same post-optimization with Binaryen 133 and a symbol map. Budget the entire first phase for at most two hours and two regeneration attempts.

## Replay

Use macOS arm64 with Go 1.27.4 for the measured configuration. The build reads the locked Go modules from the Go module cache. The replay uses one active database and one process at a time, GOMAXPROCS 8 and GOGC 100. The raw INSERT wall timer surrounds only the 100 prepared executions. The process CPU profile covers the whole process. Parent orders are committed into the snapshot before replay. Checks and invalid constraint probes use text SQL. The CPU binary has no counter overlay.

```sh
python3 "$B/recipe/restore.py" "$W/temp/harness" "$W/worktree"
python3 "$B/recipe/guard.py" "$W" 1200 python3 "$B/recipe/build.py" "$W"
python3 "$B/recipe/guard.py" "$W" 900 python3 "$B/recipe/campaign.py" \
  "$W/temp/cpu-probe" "$W/evidence/cpu"
python3 "$B/recipe/guard.py" "$W" 1200 python3 "$B/recipe/build.py" "$W" --counters
python3 "$B/recipe/guard.py" "$W" 900 python3 "$B/recipe/campaign.py" \
  "$W/temp/counter-probe" "$W/evidence/events" --counters
cp "$W/temp/overlay/bindings.json" "$W/evidence/"
GOCACHE="$W/temp/analysis-cache" python3 "$B/recipe/reduce_cpu.py" \
  "$W/evidence/cpu" "$W/evidence/functions.txt.gz" "$W/worktree" "$W/temp/cpu-probe"
python3 "$B/recipe/reduce_events.py" "$W/evidence/events"
python3 "$B/recipe/tables.py" "$W/evidence"
GOCACHE="$W/temp/analysis-cache" python3 "$B/recipe/allocator_site.py" "$W/evidence" "$W/temp/cpu-probe"
```

Each campaign checks A, B and C before recording the ABC, BCA and CAB triplets. A failed correctness check terminates the comparison. The CPU campaign divides its 15-minute allowance across the nine processes. The counter campaign replays one 100-INSERT fork per process and records foreground requests and completed waits on the same clock. Finish by preserving and verifying compact evidence before finalizing and cleaning the named workspace.
