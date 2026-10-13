# v0.5.0 paired Product Verification

Approved after final Qualification of source_commit
`bb637c49e6d6b50ec6761dead172a35f0b051f7e`. Baseline is released v0.4.7,
checked with [the typed release pin](../../release/baselines/v0.4.7.json).
Report/evidence source and the frozen runtime source are distinct identities.

Replay the previously reviewed Go/Python Fresh/Fork workload: Light, 10 MiB
serial, 10 MiB four-parallel, 100 MiB serial; four tests per suite. Normal
cases have three trials, the large case one. Eight one-test warm-up pilots
precede 80 measured cells. Alternate paired order and retain slow samples.
SQL count/payload, separate connections, commit, rollback and child isolation
oracles remain in the unchanged observers. Native container comparison cells
are outside this approved paired scope.

Prepare one task workspace with 24 GiB budget / 20 GiB free reserve and separate
clean detached baseline/candidate worktrees at their exact source commits.
Use task-local Go/Python caches and scratch. Obtain Go1.26.8, Python3.14 and the
dependency pins from `benchmarks/v046-usability-evidence/python-dependencies.txt`.
Build identical observers and both runtimes using `build-pair.py`; fixed native
compiler switching is disabled. No guest/converter/library changes are made.

```sh
python3 build-pair.py --workspace "$WORKSPACE" --go-root "$GO126_ROOT"
python3 run-product.py --workspace "$WORKSPACE" --output "$WORKSPACE/evidence/product"
python3 summarize.py "$WORKSPACE/evidence/product"
```

Build/pull/dependency preparation is excluded from product time. Run the campaign
with Go1.26.8 first on PATH, `GOTOOLCHAIN=local`, no GOMAXPROCS override,
task-owned TMPDIR, and no competing builds/tests/benchmarks. Each cell has a
900-second timeout; sampled disk guards run every five seconds. A completed Go
cell above 8 GiB Peak RSS stops the campaign; this is not an in-flight RAM quota.

Wall/CPU, startup, preparation, Snapshot, SQL and Close costs are separate.
Go Peak RSS is an OS high-water; sampled heap peaks may miss short events.
Cumulative allocation is not retained RAM. Go cleanup counters, final heap,
FDs, mapping extent and physical footprint answer different questions. Python
host after-SQL samples are not peaks. Existing diagnostic GC/observer overhead
and the expected live observer goroutine remain explicit. Do not sum overlapping
memory counters or infer race freedom from successful SQL.

Commit/push compact results, input identities, binary hashes, recipe and
interpretation; remove owned caches/binaries/data and completed worktrees.
