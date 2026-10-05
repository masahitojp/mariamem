# Checked pure memory32 candidate

Basis: released v0.4.1 plus generic-memory experiment
`49817bb8c918be6215f6dfe5a4bdce98ab8d77ab`.

The production recipe applies `../wasm2go/pure-memory32.patch` to the pinned
converter. `-pure` memory32 has checked effective addresses by default, with no
unsafe opt-out. Memory64, non-pure/fused assembly backends and extra opt-in
translator modes are not covered. The current Go-heap backing is unchanged.

`check_fixture.py` generates a small binary WASM fixture and a Go consumer,
then compares every value/trap/memory hash with reviewed WASM-reference results.
It also checks maximum-boundary accesses, grow/base/data/zero-fill and unchanged
state after failed grow. It requires Go and a pinned patched converter, not Node
or Wasmer. Canonical `scripts/regenerate_release_guest.py` runs this gate before
importing regenerated source. Do not silently update `reference-results.json`;
fixture changes need review and execution with `reference.js` in a WASM engine.

From the repository root, in a guarded owned workspace:

```sh
python3 benchmarks/spikes/memory-candidate/check_fixture.py \
  --converter "$MARIAMEM_EXPERIMENT_TEMP/translation/wasm2go" \
  --output "$MARIAMEM_EXPERIMENT_TEMP/memory32-regression"
```

Four converter unit-test files in the patch cover width mapping, observable
trapping loads, actual DCE retention and a real store-merge opportunity that
must remain four separate stores in checked pure memory32. The unchecked merge
is a positive control; it would change partial writes before a later trap.

The remaining scripts are experiment mechanics, not product runtime:

- `run.py`: pinned converter/fixture/full-guest setup and focused acceptance;
  optional resumptions use `finish.py`, `prove.py`, `final_checks.py`,
  `final_rule.py`. They retain failed attempts, not synthetic passing receipts.
- `measure.py`: identical built probes, 20 fresh processes per mode in alternating
  order, one 20-generation process per mode, separate small CRUD CPU profiles.
- `probe.go.txt`: 1,000-row fixture, 50 CRUD loops (200 statements), CPU/time/heap/
  FD/goroutine counters; no explicit GC. Optional profiles are excluded from the
  primary timing table.
- `summarize.py`: all complete trials, nearest-rank p95, absolute/relative deltas.

Use the external experiment-workspace tooling. Set `MARIAMEM_CACHE` to the
reusable converter archive directory and `MARIAMEM_RELEASE_GUEST` to the exact
released WASM; the input checksum is verified. Keep shared caches outside temp.
The campaign samples descendant RSS/physical memory, uses CPU/FD/core/time
limits and must run under the disk/free-space guard. This is a macOS experiment
harness; its mechanics do not establish Linux acceptance.

See [the candidate report](../../v042-memory-candidate.md) and its compact evidence.
No mmap, CoW, forced GC, performance optimization, merge or release is authorized
by these scripts.

## Heap-only controlled-trap continuation

`controlled_traps.py` starts from the memory-semantics candidate
`56be628bf2d976048c5ea6d1949879781ed75342`. It regenerates using the additional
shared `controlled-thread-traps.patch`, replays the same reviewed fixtures,
checks root/worker error propagation and cooperative join ordering, and runs
focused SQL/session/Snapshot/Fork and runtime race acceptance. It also verifies
independent regeneration and retained license symbols. It runs no benchmarks.

Use a fresh workspace with minimum free space 16 GiB and disk budget 6 GiB:

```sh
python3 scripts/experiment_workspace.py prepare memory-traps \
  --min-free-gib 16 --budget-gib 6
python3 scripts/experiment_workspace.py run --timeout 2400 memory-traps -- \
  env MARIAMEM_CACHE="$cache" MARIAMEM_RELEASE_GUEST="$released_guest" \
  python3 "$candidate/benchmarks/spikes/memory-candidate/controlled_traps.py"
```

Run these commands from the experiment-tooling checkout; `candidate` is the
isolated correctness worktree. The cache and WASM inputs are checksum-bound.
The existing resource guard applies to child processes as well.

Worker failures are retained and relayed at the cooperative join boundary.
Root failure also joins workers before descriptor/prepared-file cleanup. This
prevents an uncaught worker panic from terminating the Go host and prevents
cleanup while cooperative workers still run. It does **not** interrupt a blocked
root or forcibly terminate non-cooperative peers. No success or snapshot export
is reported after the join observes a worker failure. A future mmap task must
keep that lifetime limitation explicit; this is not a hard-failure containment
design.
