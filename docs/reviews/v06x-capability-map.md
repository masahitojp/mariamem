# v0.6 capability map — from north star to design decisions

2026-10-18. Source reviewed: `32450f659dab3717d503b342b26aabd76590ecf0`.
Planning artifact based on repository inspection, not new runtime/dogfood results.
The [north star](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven)
owns the intent. This map preserves its breadth; sample tests prioritize work,
not define the entire capability space. No implementation or API choice is approved.

## Human Review

Outcome: the Human agreed to the planning direction on 2026-10-18 and requested
the release-state documentation corrections recorded below. Implementation and
API choices remain separate decisions. The original recommendation follows.

Decision now: use this capability map and dependency order as the basis for v0.6
design, with explicit coverage decisions for every row before closing the scope.
Recommendation: proceed to connected designs for (1) entry/routing/lifecycle,
(2) preparation/import, and (3) compatibility/actionable failures. All three are
necessary to lower the user's total burden; designing only a driver feature or
a fixture would leave essential work with the user. Wire work follows requirements
from these designs and targeted consumer evidence, not a blanket protocol backlog.

Strongest objection: covering three areas across frameworks could make the
iteration unbounded. Keep the full map visible, but give each row a concrete
design decision and evidence requirement. A deferral must be explicit and agreed;
absence from a sample test is not evidence that a capability is unnecessary.
This review does not select a monkeypatch strategy, import API, wire emulation,
resource cap or release coverage promise.

## 1. User outcomes and existing foundations

Status vocabulary: **present** means code or documented contract exists, not that
every consumer is verified; **partial** means an existing foundation lacks the
intended experience; **gap** is missing from the inspected public surface;
**unverified** means this inspection cannot establish practical support.

| ID | Capability / user outcome | Current status and evidence | Design or evidence needed | Dependencies |
| --- | --- | --- | --- | --- |
| A | Start without environment management | Present: Go Start, Python managed host; supported macOS/Ubuntu only [S1,S2] | First-run journey, install failure and sandbox constraints; no all-platform claim | Platform contract |
| B | One small addition redirects existing application connections | Gap: guides explicitly pass DSN/connection_info; fixture returns arguments [S1–S3] | Compare explicit injection, framework adapter and driver routing; expose actual destination; handle already-created pools and concurrent tests | C, D, H |
| C | Independent tests with predictable ownership/cleanup | Present: consuming Snapshot, independent Fork, function fixture; connection/pool closure remains user-managed [S1–S4] | Who owns pools, teardown order, cleanup after test failure, stale connections, session/class/function use | Existing isolation contract |
| D | Work with familiar drivers/frameworks | Partial: SQLAlchemy/GORM test anchors exist [S7]; other combinations unverified | Matrix of exact driver versions/settings and requested commands; framework lifecycle requirements | H; B for transparent use |
| E | Prepare from migration/seed | Partial: guide demonstrates custom fixture preparation [S2,S3] | Standard prepare entry, framework migrations, failure context and repeatability | C, D |
| F | Prepare from SQL dump or externally produced data | Partial: ordinary SQL is available; no import helper in inspected public entry points [S1,S2,S5] | Inventory input dialects/formats and tools; demonstrate supported import, partial failure and unsupported constructs; select helper vs documented external tool | H; E/C for baseline handoff |
| G | Reuse preparation and safely run tests concurrently | Present process-local baseline; worker-local xdist; concurrent Fork documented [S1–S4] | Connected serial/parallel examples, resource demand and ownership visibility; distinguish DB count from connections per DB | C; E/F for preparation |
| H | Know what compatibility permits | Partial: text-only constraint is explicit; four wire commands and generic unsupported replies [S1,S5,S6] | Separate MariaDB/MySQL semantics, mariamem wire limits and framework integration; official version-relevant references and actionable settings | Consumer evidence; full matrix below |
| I | Failure identifies a useful next action | Partial: HostError code/stage/cause, logs, and some reinstall guidance already exist; generic wire and timeout messages remain [S1,S2,S5,S8] | Error inventory, original-code preservation, concise advice and detailed diagnostics; avoid unsupported attribution to app bugs | Cross-cutting A–H; diagnostic context designed early |
| J | Stable endpoint while resetting DB state | Design candidate, not current contract: child owns new endpoint, Snapshot consumes source [S4,S9] | Decide whether target long-lived apps need it; design old sessions/transactions/pools before bounded feasibility work | B/C/D; separate lifecycle decision |
| K | Reuse across processes/runs | Public Snapshot persistence/loading intentionally removed [S4] | Keep candidate visible; quantify preparation burden before deciding whether to reopen contract | E/F/G; separate contract decision |
| L | Resource limits appropriate to parallel use | Partial: 16 SQL sessions per DB documented; application-wide DB budget not provided by documented API [S1,S2] | Observe retained baselines, DB concurrency, FD/memory, pool demand; decide cap/guidance/connection tuning | C/G and representative workloads |
| M | Controlled failures and deterministic tests | Unverified as a product capability: no public fault-injection/time/scheduler facility in inspected entry points [S1,S2] | Define intended user scenarios; distinguish control of host from guest behavior; reference study before design | Separate capability decision; not prerequisite for all tests |
| N | Easy second test and rapid iteration | Partial: examples reuse fixture/baseline [S1–S3]; authoring burden not measured | Observe first-test setup, second-test edits and failure recovery separately from execution time | B–I |

## 2. Coverage axes that remain visible

This enumerates candidates, not promises. No new compatibility campaign ran here.

| Axis | Candidates retained | What is known / what is still required |
| --- | --- | --- |
| Go drivers | go-sql-driver/mysql with interpolation; default prepared path; explicit Prepare | Existing DSN enables interpolation; prepared commands unsupported. Assess all three separately |
| Python drivers | PyMySQL, mysqlclient, asyncmy, aiomysql, MySQL Connector | PyMySQL usage exists. Do not infer the others from ORM name or text-protocol support |
| Frameworks | SQLAlchemy, GORM, Django, Alembic, dbt-like workloads | SQLAlchemy/GORM test sources are anchors, not framework-wide proof. Others require consumer scenarios |
| Other ecosystems | Node/mysql2, JDBC, Rails, Spring | Keep in map; language SDK and wire-client compatibility are separate questions; no v0.6 commitment |
| Wire | prepared statements, multi-statements/results, reset, auth/TLS, flags, LOAD DATA | Use [inventory](wire-gap-inventory.md), but its host-only classifications are hypotheses until semantic design. Emulation is not automatically equivalent |
| Preparation | migrations, SQL dump, seed script, externally generated SQL/CSV/other data | Decide concrete formats and procedures; do not promise arbitrary dump parsing or raw data-directory import |
| Lifetime | function/class/session, xdist, manual parallelism, long-lived app, cross-run | Existing worker-local/function isolation is a foundation; broader sharing/reset needs explicit contract decisions |
| Environment | supported macOS/Ubuntu, Docker-free CI, restricted execution | Library delivery exists; Docker-free does not imply every sandbox permits local networking/process creation |
| UX | routing, preparation, baseline capture, cleanup, diagnostics, fault injection | Routing/import/diagnosis must be understandable as a complete workflow; not all require new public API |
| Determinism | test order independence, clock control, scheduler control | DB isolation exists; clock/scheduler control are distinct, unverified capabilities |
| CDC/binlog | emission, SQL inspection, replication streaming | Existing low-priority/watch position retained; demand and guest/API consequences remain explicit |

## 3. Dependency order and design alternatives

1. Define a first-test and second-test journey for both an existing application
   and a new application. Include preparation and one failure, not only successful
   CRUD. Use the complete matrix to identify capabilities the examples miss.
2. Design routing and lifecycle together: explicit connection injection,
   framework adapters and driver interception remain alternatives. A one-line
   entry is a user outcome, not approval for global monkeypatching. Existing
   pools, parallel tests and restoring application state are essential boundaries.
3. In parallel as design work, define preparation inputs and actionable failure
   information. Import does not universally require multi-statements: determine
   the actual tool/protocol path before selecting wire changes. Diagnostics need
   context from routing, preparation and lifecycle and should not be a final polish.
4. Cross-check actual consumer requirements against the wire gap inventory.
   Compare host implementation/emulation and guest changes where necessary;
   statement typing, session state and multi-result behavior must be preserved.
   Existing docs' blanket host-only wording is not proof that every candidate
   fits the current guest API.
5. Select version-specific coverage with Human Review, recording reach/defer and
   reasons for every row. Then implement approved boundaries, verify combined
   use and evaluate resource controls from observed demand.

Fixed endpoint/reset, cross-run storage, new language SDKs and fault/time control
are retained decision branches, not silently excluded and not dependencies of
every usable fixture. Guest-initialization optimization stays in the approved
v0.7 stream. Resource observations for v0.6 do not reopen that optimization scope.

## 4. Evidence, checks and completion of this planning step

- S1: [Go public guide](../go.md), [Go API](../../mariamem.go).
- S2: [Python public guide](../python.md), [Python API](../../python/mariamem/__init__.py).
- S3: [pytest fixtures](../../python/mariamem/pytest_plugin.py).
- S4: [ownership/lifecycle contract](../decisions/snapshot-product-contract.md).
- S5: [wire dispatch and capability handling](../../internal/mysqlwire/wire.go)
  (`capabilities`, `Serve`, command switch at source lines 450–459).
- S6: [wire inventory](wire-gap-inventory.md); derived layer predictions are not
  verified implementation plans.
- S7: [SQLAlchemy dogfood](../../tests/consumer/test_sqlalchemy_dogfood.py),
  [GORM dogfood](../../tests/consumer/gorm/dogfood_test.go).
- S8: [Python host errors](../../python/mariamem/_session.py),
  [artifact diagnostics](../../python/mariamem/_artifacts.py), Go `Logs`/`Err` in S1.
- S9: [host endpoint allocation](../../internal/host/server.go), `Start` listener.

Confirmed foundations: Snapshot independence, existing fixture entry points,
documented lifecycle, diagnostic fields and text-wire dispatch. These are not
newly requested engine implementations. Inspection found no need to regenerate
guest/Go or run unchanged runtime tests for this documentation step.

Existing consumer and lifecycle tests can catch regressions in their covered
operations; they do not measure first-test learning burden, validate every
driver, or check that error advice helps a user. Those are explicit evidence
gaps, not CI PASS claims. This step checked source, wording, references and diff;
no new benchmark, compatibility campaign or external-reference review ran.

The map and dependency proposal are complete for this planning step. Version
scope, design alternatives and their acceptance tests remain to be decided.
Release-state documentation correction (2026-10-18): project-status now records
published v0.5.3 with its release/CI references; the ownership contract header
records publication of the optimization in v0.5.2 and its retention in v0.5.3.
This resolves the two chronology gaps observed during inspection without changing
the contract or using release chronology as evidence of new capabilities.
