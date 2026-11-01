# D1 lightweight prototype: materialized class setup + per-test children

2026-11-01, experiment/d1-class-fork. Recommendation: continue with a bounded real-mariamem adapter pilot; do not adopt this prototype as product code. The framework seam works on SQLite, but the actual MariaDB ownership/disconnect path has not been exercised.

## Result and material objection

An explicit prepared test base can materialize class setup once, capture that class state and supply a fresh child before each per-test Django setup. Both runner routes executed this model with normal, failure and skip cases. The Django-specific part is an opted-in test-class mixin plus runner/pytest setup; Snapshot/child/close ownership is separate.

The material objection is semantic: Django normally wraps TestCase class setup in an atomic transaction. This prototype deliberately removes that outer atomic and commits class setup into the class baseline. The existing per-test atomic/rollback and TestData object-copying remain, but transaction/on_commit behavior during setUpTestData/user setUpClass changes. It is not transparent support for arbitrary existing TestCase subclasses. The experiment makes this change explicit, not a selected product contract.

## Fixed workload and code

- Product source_commit: b3b3b46a8807482ad3f96725af86e031fe369b01; initial design83b47c4d7b8b1b170b60f372dfc863ef29a97664.
- Executed final prototype source_commit:7379e5aec9977c58d05e2df7ea7526e69f586d59. Git identity was checked before the run. Assessment also binds each Python source hash.
- Python3.11.18, Django5.2.8, pytest9.0.2, pytest-django4.12.0, local macOS arm64. Full dependency versions are preserved with evidence.
- Reused authored `orders` models and both migrations from `tests/e2e_native_control/pythonapp`, including migration SEED. Preparation adds a non-model SQL sentinel table. No new framework compatibility matrix or independent external app.
- [Prototype/reproduction](../../benchmarks/d1-prototype/README.md), [final assessment](d1-v061-prototype-evidence/final/assessment.json), [raw logs/events/checksums](d1-v061-prototype-evidence/).

## Ownership and framework seam

1. Let Django create/migrate a file-backed SQLite test DB. Add the preparation sentinel once, close connections and capture a consuming source Snapshot analogue.
2. Each explicit prepared class gets a child from that run baseline. SimpleTestCase's class guards/cleanups are installed; standard class atomics/eager pre-setup are bypassed deliberately. PreparedTestCase loads class fixtures and calls setUpTestData once, preserving Django's TestData wrapping. User setUpClass code after super can still modify that class source.
3. Delay class capture until the first per-test _pre_setup, after user class setup has completed. Close connections, consume the class source, create a child and update the alias. The normal TestCase method atomic or TransactionTestCase setup now runs on that child.
4. Framework teardown runs, then physical Django connections are closed and the child is discarded. Class cleanup disposes the class baseline/uncaptured source, including setup failure/skip. Unconfirmed owner-close blocks further admission; a final cleanup may retire the retained child, but does not erase the first error/debt.
5. Django's final DB teardown needs its own valid disposable owner. The initial probe exposed a FileNotFound error because it targeted the consumed preparation DB; the final version gives framework teardown a separate child and then closes that owner too. A real MariaDB adapter must map the same boundary to endpoint/schema settings and actual SDK owners.

SQLiteCopy is an experimental file-copy stand-in, not mariamem Snapshot. The ownership manager currently uses SQLite names/SQL and is not a production backend interface. The hypothesis that the existing mariamem source/snapshot/fork objects can implement it still needs a real-engine test. No custom Django database backend, guest patch or wire feature was added.

## Final finite checks

Each row was assessed under both DiscoverRunner (manage.py path) and pytest-django:20 outcome checks in total.

| Case | Observed / expected |
| --- | --- |
| Normal two Atomic + two Transactional methods |4 bodies; migration/seed/raw sentinel present; class data prepared once; class setup after super retained; both runners exit0 |
| Reverse order |4 bodies, same assertions; both exit0 |
| Failure after committed write/schema mutation |Original assertion FAIL retained; second transactional body sees the original prepared state |
| User class setup raises |No body from failed class; following transactional class runs; original setup error retained |
| User class setup skips |No skipped-class body; following class runs; SKIP retained |
| Child close fails before deleting its owner file |File still exists at injected failure; next test body refused by cleanup debt; final cleanup removes owner |
| Original test failure + close failure |Both raw errors retained; next body refused; run nonzero |
| Preparation fails after partial sentinel DDL |No test bodies; original preparation error retained; source discarded |
| Class capture fails |No bodies; uncaptured sources discarded; capture error retained |
| Disable child replacement (negative control) |Next transactional test fails baseline assertions; control is not relabelled as functional PASS |

Every case ended with no remaining .sqlite database files in its scratch directory. This is observed file cleanup, not a process-tree/FD census or proof of MariaDB disconnect. Expected failing runs remain nonzero; the assessment PASS means the specified oracle matched, not that those tests became successful.

## Original failures and corrections

The first manual4-case probe passed its bodies but failed final DB destruction; the raw output is retained. The first full campaign then exposed pytest-django's access blocker during preparation and insufficient verbosity to observe manage.py skip reasons. Preparation/cleanup now use the framework's unblock context, and skip reasons are recorded. Attempt1 remains FAIL; attempt2 matched18 cases; the final source strengthens the close-failure control and adds combined failure for20 matching outcomes. One initial command was launched from the wrong directory and failed before prototype execution; its log is separate. Nothing from these attempts is presented as MariaDB evidence.

## Limits and next decision

Not executed: real mariamem/MariaDB, mysqlclient, both supported hosts/Python minors, function-style pytest-db tests, xdist/parallel/async, multiple aliases/routers, external retained connections, serialized rollback, available_apps, and arbitrary setUpClass transaction usage. The prototype rejects selected unsupported options rather than implying broad support. It provides no speed claim.

Next recommended experiment: one local supported host, real SDK owner + mysqlclient, same migration/seed/raw-sentinel case, first the healthy/reverse/commit-failure/cleanup boundaries under both runners. Reuse the existing published exact-source host if available; assess build cost before extending the budget. Do not launch Release CI or the full six-cell standard-runner campaign to answer this small question. The class-materialization semantic choice needs an explicit product decision before implementation/adoption.

No production code/main change, release approval or D1 completion is claimed. Original Issue43 remains open.
