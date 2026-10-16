# Qualified main versus published v0.5.0 performance

Finite macOS arm64 measurement after Qualification of candidate
`c97e55fc065f6ee7b560325077726da53e5d95d7`; baseline is the typed
[release pin](../../release/baselines/v0.5.0.json). No runtime changes.

- Existing Go/Python Fresh/Fork matrix: Light, 10 MiB/8-table serial,
  10 MiB/8-table four-parallel, 100 MiB/8-table serial. Four tests per suite;
  three trials except one large trial. 80 measured cells plus eight one-test pilots.
- Existing Python sharedhost workflow: small/medium two children and 100 MiB
  sixteen children; six ordinary pairs plus three separate RSS-observed pairs
  per scale. 54 cells. This is a different schema from the Go/Python matrix.
- Repeat the prior slow small-case workflow: 30 ordinary pairs and 30 RSS pairs,
  120 cells. Each case uses a fresh Python process. Observe whole >=1000ms and
  start >=900ms separately, with every phase retained. No deletion of slow samples.

Stop on failed SQL/isolation/cleanup oracle, timeout (900s matrix;180s sharedhost),
disk budget (12 GiB) or free reserve (20 GiB). Overall supervised run <=7200s.
A stop is incomplete, not PASS; no corrective runtime work is bundled.
All 262 executions must be accounted for (including eight excluded pilots).

Only one campaign at a time. Same Go1.26.8, CGO_ENABLED=0, stamped clean inputs,
Python3.14.8 and pinned prior Python dependencies. Build/setup time is excluded.
Go resources use the existing 25ms observer/helper; Python matrix is after-SQL,
not peak. Sharedhost ordinary and sampled sum-of-live-host RSS remain separate.
Small repetition counts describe observed frequency, not a universal tail bound.

Build command: `python build-pair.py --workspace WORK --go-root GO_ROOT`.
Then run `run-product.py --workspace WORK --output NEW_OUTPUT` and the sharedhost
campaign twice (default 6/3 all scales, then --scales small --plain-repeats 30
--resource-repeats 30). Both receive exact clean roots and stamped hosts.
The orchestrator and actual input/binary/dependency hashes are saved with results.

Input checkout note: the first linked-worktree builds recorded the parent repo's
SHA in Go VCS metadata and were rejected before any measurement. Independent
Git checkouts with real .git directories replace them; inputs and runtime code
are unchanged. The initial failure receipt/build metadata are retained. A locked,
disk-guarded manual continuation uses the remaining original two-hour budget;
completion is judged only after all 262 executions and identity checks succeed.
