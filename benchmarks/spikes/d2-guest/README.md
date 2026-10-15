# D2 real-guest spike (experiment only)

See [Human Review and measured results](../../../docs/reviews/d2-guest.md).
This is not a supported storage implementation. It applies exact-preimage
overlays in a disposable worktree, builds one E/D2 host, and restores every
canonical file afterward. Never publish the experimental host.

Input runtime: `a8137b8b444f86068d3128a291e3a848adfdfd56`.
The branch also contains the preceding component evidence; those reports are
historical. Guest Wasm and converter inputs are unchanged. The measured input
is the recorded source commit **plus** the overlay, not just the branch HEAD.

## Reproduce

From a clean checkout of this experiment branch, create a fresh owned workspace.
Use Go 1.26.8 and Python with venv. Set `GO_BIN` and `GOFMT` to that toolchain's
absolute binary paths; neither is downloaded by this script. Commands below
run from the checkout root. Do not reuse an existing campaign output directory.

```sh
python3 scripts/experiment_workspace.py prepare d2-guest-repro \
  --branch experiment/d2-guest-repro --min-free-gib 16 --budget-gib 12
python3 build/experiment-work/d2-guest-repro/worktree/scripts/git_identity.py inspect HEAD
python3 build/experiment-work/d2-guest-repro/worktree/benchmarks/spikes/d2-guest/instrument.py
python3 scripts/experiment_disk.py --work-dir build/experiment-work/d2-guest-repro \
  --min-free-gib 16 --budget-gib 12 --timeout 1200 -- \
  python3 build/experiment-work/d2-guest-repro/worktree/benchmarks/spikes/d2-guest/build.py
python3 -m venv build/experiment-work/d2-guest-repro/temp/venv
build/experiment-work/d2-guest-repro/temp/venv/bin/python -m pip install --no-cache-dir pymysql==1.2.3
```

Run `campaign.py` with the following stages, each under the same disk guard
(`--timeout 300`, or 600 for `measure`):

1. `pilot`: one E/D2 small workflow, excluded from the main summary.
2. `audit`: D2 with guest Export enabled; all logical file hashes/inventory must match.
3. `boundaries-d2`: transaction rejection, live children after parent Close,
   derived baseline, persisted-format fallback, injected failure/corruption.
4. `measure`: E boundaries, `plain` (5 alternating pairs per size), then
   `resources` (3 pairs per size). Runs sequentially, not parallel benchmarks.

For example:

```sh
python3 scripts/experiment_disk.py --work-dir build/experiment-work/d2-guest-repro \
  --min-free-gib 16 --budget-gib 12 --timeout 300 -- \
  python3 build/experiment-work/d2-guest-repro/worktree/benchmarks/spikes/d2-guest/campaign.py pilot
```

The host uses localhost SQL connections. Use the environment's approved
execution mechanism if the sandbox blocks bind/connect. Do not turn such a
denial into a guest failure or PASS.

`receiver_checks.py <host-path>` runs small acquisition fixtures with the actual
guest identity. `summarize.py <workspace>/evidence` derives the timing/resource
summary from individual `result.json` files. `reduce.py` preserves compact
observations under `docs/reviews/d2-guest-evidence/`; it replaces workspace paths
and does not preserve DB files, binaries or caches.

Before saving the experiment, run `restore.py`, reapply `instrument.py` and
compare the entire `instrumentation.json` with the build's overlay record.
Run `restore.py` again. This checks deterministic overlay construction, not
independent binary reproduction. Commit only templates, harness and evidence.
Reduce/preserve changes, push the experiment ref, then use the repository
experiment-workspace finalize/cleanup workflow. Never remove unpreserved work.

## Boundaries

- E is an earlier experimental direct-handoff candidate, not stock main.
- The Python adapter is installed only by this harness. It owns readonly,
  unlinked segment descriptors, checks full logical content and pins parents
  through child/derived operations. It does not alter the shipped Python package.
- Temporary `snapshot()` uses D2. `snapshot_to()` retains the existing file
  format/Export path. Import of that format remains legacy-backed.
- All writers stop before sharing. Source expectation, descriptor-based target
  verification and Python pread verification are distinct checks.
- Segments are 4 MiB, blocks 16 KiB; slot reclamation and generation compaction
  are deliberately absent in this bounded prototype. Shared mapping remains
  OS-dependent. Native Ubuntu x86_64 was not exercised.
- Plain reports contain lightweight counters in both modes. Resource runs add
  MemStats/getrusage. Neither campaign proves instrumentation-free performance.
