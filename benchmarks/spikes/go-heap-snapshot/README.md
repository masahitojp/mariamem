# Same-process Go heap Snapshot spike

See [Human Review](../../../docs/reviews/go-heap-snapshot.md). This is an
experiment, not a product implementation. It retains immutable 16 KiB Go heap
blocks after guest shutdown; children allocate their own changed blocks. No
Snapshot payload file, file mapping, descriptor handoff or JSON data-layout
transfer is used. Existing startup management directories and the Wasm runtime's
own memory/transport implementation remain unchanged.

The same binary selects the conventional Go path (`--mode control`) or the
heap experiment (`--mode heap`). Both use the same SQL workflow. This does not
compare against the previous Python E/D2 campaigns. Source hashing, target-view
verification and ownership-acquisition verification remain three full scans.

## Reproduce in an owned workspace

Start from a clean checkout of this experiment branch. Set `GO_BIN` and `GOFMT`
to absolute paths in Go 1.26.8. The build uses only the workspace's disposable
Go caches; module dependencies remain pinned by go.mod/go.sum.

```sh
python3 scripts/experiment_workspace.py prepare go-heap-repro \
  --branch experiment/go-heap-repro --min-free-gib 16 --budget-gib 12
python3 build/experiment-work/go-heap-repro/worktree/scripts/git_identity.py inspect HEAD
python3 build/experiment-work/go-heap-repro/worktree/benchmarks/spikes/go-heap-snapshot/instrument.py
python3 scripts/experiment_disk.py --work-dir build/experiment-work/go-heap-repro \
  --min-free-gib 16 --budget-gib 12 --timeout 1200 -- \
  python3 build/experiment-work/go-heap-repro/worktree/benchmarks/spikes/go-heap-snapshot/build.py
```

`instrument.py` checks exact canonical preimages at
`a8137b8b444f86068d3128a291e3a848adfdfd56`, creates formatted overlay files and
records hashes. The prior block implementation/fixtures are read from the
committed `benchmarks/spikes/d2-guest` sources. `build.py` checks all postimages
before tests/build and records source commit, overlay/source hashes and binary
SHA256. Keep the overlay applied during verification and measurement.

Run `campaign.py` under the same disk guard with these stages:

- `pilot`: one small workflow per mode.
- `verify`: separate guest Export audit, then lifecycle/failure checks.
- `measure`: 5 alternating pairs per size for plain timing, followed by 3 pairs
  per size with separate MemStats/getrusage observations. Use timeout 600.

For example, from the checkout root:

```sh
python3 scripts/experiment_disk.py --work-dir build/experiment-work/go-heap-repro \
  --min-free-gib 16 --budget-gib 12 --timeout 300 -- \
  python3 build/experiment-work/go-heap-repro/worktree/benchmarks/spikes/go-heap-snapshot/campaign.py pilot
```

Campaign outputs must be new. Each case uses a fresh process and empty TMPDIR.
The SQL endpoint binds localhost, which needs permission in restricted sandboxes.
Record a sandbox denial as an execution restriction, not guest behavior.

Run the focused race test in the worktree, with GOCACHE/GOMODCACHE/GOTMPDIR/TMPDIR
set to its owned temp locations:

```sh
"$GO_BIN" test -race -p 2 ./internal/generatedgo/code/base \
  -run 'Test(Heap|DIntegration)' -count=1 -v
```

`summarize.py <workspace>/evidence` derives the final summary. `reduce.py` retains
compact JSON/text evidence and checksums. The initial campaign used append for
the disabled-path WriteFile copy; the final overlay preserves canonical
make(len)+copy. Keep those campaign identities/results separate.

Finally run `restore.py`, reapply the overlay and compare every postimage with
the build record, then restore again. Save only templates/harness/reports, not
modified canonical runtime files. Commit/push the experiment ref, preserve
compact evidence, finalize and clean the workspace using the repository helper.

## Limits

Heap blocks are immutable by internal ownership convention, not OS page
protection. Guest workers finish before capture. Children copy block descriptors
and allocate changed blocks; no child may mutate inherited data. Closing a
Snapshot removes its ownership reference while started children retain theirs.
Actual heap reclamation depends on GC, and GC does not promise immediate RSS
return to the OS. No large-generation compaction or forced worker termination
is implemented.

The internal capture request is registered only after Snapshot preconditions
pass and removed on completion/failure. Payload export has an experiment guard;
creation does not call the conventional disk publisher/importer. The fault
fixtures mutate fresh candidates only. They are not a proof about arbitrary
memory corruption of a shared parent.

Persisted destination/import and Python integration are not part of this
prototype. macOS arm64 was exercised; native Ubuntu x86_64 was not. Functional
checks and selected heap race fixtures are not full Release Qualification or
proof of all guest memory behavior.
