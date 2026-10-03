# Prepared-state crossover diagnostic

This isolated nested-module harness uses the exact released source in its
worktree through an explicit local `replace`. It is a runtime comparison, not a
module acquisition or external-consumer build experiment. Production source,
configuration and public API are unchanged.

Two existing preparations are used:

- `fixture-1000`: the canonical `benchmark_rows` InnoDB table and one transaction
  containing the existing 1,000-row/32-byte-payload bulk fixture.
- `gorm-user-address`: the actual GORM dogfood User/Address models, ordinary
  AutoMigrate/schema discovery, unique index, foreign key, timestamps and one
  parent/child seed. No synthetic heavier migrations are added.

`fresh` performs Start, preparation and fixture verification for every isolated
test. `fork` performs the identical preparation once, closes the SQL pool, waits
for disconnect acknowledgement, publishes a Snapshot and creates each child
through the public Fork API. Every test verifies pristine fixture data, commits
a private update, checks rollback, closes its pool, waits for disconnect and
closes its DB. No reset SQL is used. The next child's fixture checks detect any
committed-write leakage.

Readiness includes API entry, ordinary SQL/GORM connection setup and fixture
verification. Suite time includes preparation/Snapshot setup, all test work and
DB cleanup, and final Snapshot cleanup. Snapshot consumes its source. Slow runs
are retained. Each entire suite runs in a fresh independent process; OS caches
are not flushed and there is no forced GC/FreeOSMemory.

Run all heavy build/measurement work under the shared fan-out lock, or otherwise
ensure no competing CPU/memory workload:

```sh
GOTOOLCHAIN=go1.26.8 python3 benchmarks/fixturecrossover/run.py \
  --work /outside-checkout/crossover-raw --rounds 3 \
  --summary /outside-checkout/crossover-summary.json \
  --samples /outside-checkout/crossover-samples.csv
```

The runner builds once and runs one warmup per mode/preparation followed by
three order-balanced repetitions of actual 10/50/100-test suites. The stop
condition is any SQL/fixture/commit/rollback/cleanup failure, incomplete result,
or a 900-second suite deadline. Forced reclamation of a hung direct-linked
guest remains outside the product's supported contract; the diagnostic
supervisor can terminate its own independent child process on deadline.

A descriptive crossover uses mean complete per-test cost (including normal
cleanup), not startup median alone:

`ceil(mean one-time prepared setup / (mean fresh test - mean fork test))`.

If the denominator is nonpositive, there is no finite crossover in the measured
workload. Actual measured suite totals take precedence over that estimate.
Three suite repetitions are diagnostic evidence, not a canonical performance
campaign or a high-confidence tail estimate.
