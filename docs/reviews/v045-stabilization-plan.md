# v0.4.5 stabilization plan

## Inputs and preserved decisions

Start: released main/source `8ede4ad65def07436b64801076004ff80aec0799`.
Audit: `experiment/infra-audit-v044` at `d7b1c0f60591843b0e72327fba7c62d26b7a3ee4`.
[Full audit and its JSON/CSV inventories](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
remain the source of the six decisions and their supporting/counter evidence.

1. Boundary-selected check/integration; native qualification, measurement and release remain distinct.
2. Preserve layered unit/runtime/SDK/artifact oracles; restore orphan wire coverage before retirement.
3. Extract live helpers, migrate callers, then retire historical harnesses; preserve development/artifact adapters.
4. Keep release/workspace Skills, consolidate instructions in existing developer docs, mechanically bind identities.
5. Development source selection must not depend on expiring release receipts; release evidence remains authenticated and fail-closed.
6. Reuse OwnedPrepared capture, internal timing and process counters for Snapshot measurements, not a new framework.

## Bounded implementation order

- P0: compare every legacy integration/wire invariant with existing owners. Promote supported unique cases into real-host pytest and canonical integration; preserve unsupported forced-failure diagnostics separately.
- P0: replace Development remote-receipt selection with local event-diff classification. Unknown inputs require full check/integration; all test/tooling inputs remain checked. Keep release validation unchanged.
- Verify migrated cases against current MariaDB and selector negative cases with no external evidence available. No broad platform rerun for classifier edits.
- P1: extract live download/statistic/resource functions; consolidate ORM loops without changing case sets; update canonical scope documentation and agent instructions. Inspect generated recipe inclusion/reproduction checks.
- Review checkpoint: before narrowing published acceptance, changing reusable runtime receipt guarantees or significant canonical execution behavior, present exact retained/replaced evidence and await Human Review.
- P2 after infrastructure stability: narrow capture stage instrumentation, 0/10/100 MiB repeated full-public Snapshot measurements; Fresh/Fork suite crossover; bounded real product controls if dependencies are available. No automatic performance optimization.

## Evidence and scope

Each coherent change gets focused tests and compact receipts with commands, source SHA and results. Actual runtime evidence is not claimed for tooling-only commits. No merge/release, no guest change, no cache manager. Dedicated branch/workspace, 8 GiB scratch budget and 8 GiB free-space floor; preserve compact evidence and remove disposable scratch on completion/checkpoint.
