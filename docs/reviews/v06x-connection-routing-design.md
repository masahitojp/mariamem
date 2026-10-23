# v0.6 connection switching — design and Human Review

2026-10-23. Source_commit: `9f29194bbddd6a9431a4a250bd2f93ee813734af`,
confirmed as a commit by `scripts/git_identity.py inspect HEAD`.
Branch: `design/v06-connection-routing`. Documentation only; no routing code or
runtime experiment has been added. The request and review inputs are reconstructed
from the Human's request to proceed with easy connection switching and the
approved workflow-design direction. This is not a new implementation approval.

## Human Review — decision requested

**Approve a bounded connection-switching spike, not production adoption.**
Recommendation: compare explicit configuration injection with Python driver
routing plus a SQLAlchemy pool adapter; use child-owned configuration/pools for
Go. This offers a small test entry while keeping each test on its own DB. The
decisive prerequisite is now satisfied: Prepared has been adopted, so the spike
can retain ordinary driver behavior instead of disguising missing protocol
support with interpolation or a different cursor mode.

The strongest objection is that interception can make a test appear isolated
while an old pool still sends work elsewhere. Keep configuration injection as
the control and require destination, pool-generation and original-destination
oracles before recommending interception. If the supported entry cannot prevent
that mistake, recommend the explicit/adapter path for that case; do not declare
the one-line goal achieved or silently drop the case. This is a reason to test
the seam, not to reopen the completed Prepared implementation.

The requested decision does not select final API names, narrow overall v0.6
coverage, authorize main adoption, or initiate Qualification/release.

## 1. What a user should experience

For a new application, the test integration supplies the connection settings or
pool through the application's normal construction seam. For an existing Python
application, a test fixture can instead bind a named application connection
profile to an independent child before invoking existing application code.
Migration/seed prepares a baseline once; each test gets its own child. The second
test reuses that setup without repeating redirection or cleanup plumbing.

Proposed usage shape, **not an available API**:

```text
session fixture: prepare -> close setup connections -> snapshot
test fixture:   fork -> bind named application profile -> run test
teardown:      stop new admissions -> close owned connections/pools
               -> close child -> restore binding
```

The normal test body should not need a new query interface. SQL, explicit
Prepare, prepared=True, commit/rollback and driver exception handling remain.
One small entry is the aim for supported applications, not a promise that an
arbitrary already-running application needs no lifecycle integration.

Preparation/import tooling is a companion workstream. This spike uses a small
known migration/seed callback to exercise the lifecycle; it does not implement a
dump parser or close the separate migration/dump acceptance work.

## 2. Evidence carried forward and what changed

| Finding | Evidence | Effect on this design |
| --- | --- | --- |
| Built-in Python fixtures already expose worker-local session baseline and function child | [pytest_plugin.py](../../python/mariamem/pytest_plugin.py), lines 12–33 | Add routing around child use, not a new storage/lifetime model |
| SQLAlchemy/GORM anchors explicitly build from the child's endpoint | [Python anchor](../../tests/consumer/test_sqlalchemy_dogfood.py), `engine_for`; [Go anchor](../../tests/consumer/gorm/dogfood_test.go), `open` | Existing regression PASS is an injection control, not routing proof |
| Driver entry, saved aliases, cold engines, idle pools and active handles differ | [pinned MySQL source findings](v06x-mysql-workflow-source-review.md#2-connection-seams-and-their-limits) | Reuse that inventory; do not rerun the entire external survey |
| Prepared P1–P6, routine/text multiple results and canonical ownership are adopted | [current status](../project-status.md#prepared-p6-canonical-ownership--complete-adopted-on-main), [P6 review](v06x-prepared-p6-human-review.md) | Previous blanket “Prepared unsupported” findings are historical, not current blockers |
| Connection reset is different from statement reset | [wire.go](../../internal/mysqlwire/wire.go), command switch: 22–26 implemented, 31 absent | Use a new physical connection for another child; do not rely on COM_RESET_CONNECTION or port reuse |
| Snapshot consumes a disconnected source and children own separate endpoints | [product contract](../decisions/snapshot-product-contract.md#lifecycle-and-persistence) | Routing must release preparation connections and cannot turn capture into in-place reset |

Existing fixed samples remain PyMySQL1.2.3, SQLAlchemy2.0.54 and
go-sql-driver/mysql1.9.3 from the consumer pins. Connector/Python26.7.0 is also
required in the spike because the Human made its default/prepared path part of
the goal; the older routing review's Connector9.4 source sample is insufficient
to establish its current interception seam. Determine/pin that seam at spike
preflight. Preserve the [accepted consumer exceptions](../decisions/prepared-consumer-exceptions.md)
exactly; do not count their functional FAILs as PASS or change defaults to hide them.

Primary documentation rechecked on 2026-10-23:

- [SQLAlchemy disposal](https://docs.sqlalchemy.org/en/20/core/connections.html#engine-disposal)
  does not close checked-out connections. Disposal alone cannot retarget them.
- [SQLAlchemy pool events](https://docs.sqlalchemy.org/en/20/core/pooling.html#pool-events)
  provide creation/checkout hooks; the [invalidation description](https://docs.sqlalchemy.org/en/20/core/pooling.html#more-on-invalidation)
  provides a possible reject/reconnect mechanism. These are design seams, not a
  tested MySQL routing implementation.
- [Python3.14 contextvars](https://docs.python.org/3.14/library/contextvars.html)
  provides context-local selection and restoration. It neither assigns ownership
  to existing SQL handles nor proves propagation to every application thread.
- [database/sql OpenDB](https://pkg.go.dev/database/sql#OpenDB)
  accepts a Connector and returns a pool; one child-owned pool is the proposed
  Go unit. The fetched page describes Go1.27.3, not new Go1.26.10 acceptance;
  the spike must use the repository's pinned Go1.26.10 source/toolchain.

## 3. Alternatives under the same criteria

| Method | User effort | Existing objects | Parallel use | Maintenance / limitation |
| --- | --- | --- | --- | --- |
| Configuration injection | Small if the app already accepts DSN/options | Rebuild the test-owned pool at the construction seam | Separate child/pool per test | Lowest dependency on driver internals; cannot replace a hard-coded connection factory by itself |
| Framework adapter | Small fixture entry for its supported framework | Can manage engine/pool checkout and cleanup | Requires target ownership checks | Versioned framework support; Django needs its own migration/test-runner lifecycle, not only driver routing |
| Driver routing plus pool adapter | Closest to unchanged Python connection creation | Cold engines and idle pools are candidates; held handles require rejection/release | Scoped target plus per-checkout identity, not one global target | Highest hook/alias/version maintenance; must prove no original-target fallback within its declared boundary |
| Stable endpoint / relay | Potentially helps a long-lived application | Does not itself move/reset SQL sessions | Session ownership still required | Separate lifecycle/engine design; no evidence it is necessary for this first spike |

Recommendation is complementary paths, not a single global monkeypatch for both
languages. A Go pool fixed to one child can be passed through GORM's connection
seam or ordinary application configuration. Do not introduce a context-switching
Connector behind one shared sql.DB: idle physical connections could outlive the
selected target. Do not mutate process-wide environment or network dial rules
to claim support for parallel tests.

## 4. Proposed routing boundary

**Select what is being redirected.** Bind a named application profile or
explicitly registered engine/factory, not every MySQL connection in the process.
Unregistered routes are outside the interception claim. A raw/native/custom
factory that bypasses supported hooks cannot be advertised as protected. Report
known unsupported creators at registration; do not claim every bypass can be
discovered automatically.

For the registered profile, missing/expired/ambiguous target selection must fail
before a new connection reaches the original endpoint. Keep the test-session
guard installed through background-work cleanup; popping a ContextVar must not
reenable original-target fallback for registered work. Full hook removal happens
only after registered users finish. Calls after that explicit uninstall, or
through an unregistered raw handle, are not contained by this helper.

**Separate destination from SQL behavior.** Replace endpoint/transport and
credentials with the child's metadata. Preserve charset, autocommit, timeouts,
client flags, prepared settings and SQL initialization options where supported.
Resolve socket/option-file/DSN precedence before dialing. Unsupported TLS or
custom transports must produce an actionable rejection, not silent option loss.
Keep the requested logical schema name: prepare that schema in the child and
verify DATABASE() plus qualified table access. Do not silently map all schema
names to `test` or rewrite SQL. Multi-profile/cross-schema inputs must be
explicitly mapped or rejected in the prototype, not collapsed into one DB.

**Bind physical connections.** Candidate metadata is profile identity, child ID
and scope generation, attached at physical creation and checked at checkout.
An idle connection from another child is invalidated and recreated before use.
Unknown ownership is rejected/recreated only through an explicitly enrolled
adapter; external handles are not silently adopted. A live statement/transaction
stays with its original physical connection and is never replayed on another DB.
Registration of an engine with already checked-out handles must reject that
transition with a release/recreate action. Testing a cold engine cannot prove
this state covered.

**Make concurrency explicit.** Python uses context-local binding with a shared
revocable scope lifetime; nested bindings restore the outer token. A copied
context whose scope has ended must reject, even if it retains a child reference.
Test separate threads with explicit propagation, a thread without propagation,
and asyncio task scopes separately. Shared pools may invalidate one another's
idle entries; the spike must record reconnect/churn or timeout rather than
claiming good parallel throughput from isolation PASS. Go uses separate pools.
xdist retains one baseline per worker; no cross-worker sharing is introduced.

**Own only enrolled resources.** Test-created connections/pools are closed by
the integration. An enrolled pre-created engine needs an explicit lifecycle
policy; registration is not permission to close arbitrary application handles.
On teardown, reject new admissions, join tracked work, close owned pools, wait
for disconnect, then close the child and restore scope. Preserve the original
test/setup error and attach cleanup failures. Non-cooperative work is not made
safe by force-closing a route; preserve the existing forced-stop limitation.

Diagnostic fields: operation/stage, stable reason, profile and child/generation,
driver mode, original cause and one next action. Never emit passwords or complete
DSNs. A SQL error is not evidence of an application bug or MariaDB incompatibility.

## 5. Bounded spike and finite exit conditions — proposed

Use an `experiment/<short-purpose>` branch. Keep changes in authored prototype
helpers and tests; no guest/converter/generated-source, public API, canonical
fixture or package-default changes. Pin exact source/toolchain/driver inputs
before execution. Start with the current real guest, two children with distinct
marker rows, and a controlled local original-destination sentinel. Never point
the negative oracle at an actual application/production DB.

| ID | Required case | Success / failure oracle |
| --- | --- | --- |
| R1 | Python PyMySQL direct connection; saved alias; delayed connect/reconnect | Actual marker, schema and profile agree; captured original endpoint untouched |
| R2 | SQLAlchemy normal cold engine and sequential reuse of a warm idle pool across two children | Each checkout reaches the current child; old prepared/session state not reused |
| R3 | Pre-existing checked-out connection/transaction, custom creator, unknown ownership | Supported adapter rejects before presenting the transition as complete; explicit cause/action; no silent fallback or statement replay |
| R4 | Two concurrent targets, nested scope, propagated/unpropagated threads and asyncio tasks | Distinct markers and committed writes remain isolated; missing/expired bindings reject; reconnects/timeouts recorded separately |
| R5 | Setup/test/cleanup exception; delayed task after scope exit; child closed | Original error retained, owned resources released, stale route rejected, outer scope restored, sentinel untouched |
| R6 | Socket/option-file conflicts, named schema/qualified SQL, charset/autocommit, unsupported TLS | Explicit destination precedence; SQL-affecting settings preserved or rejected before connection, no credential leak |
| R7 | Connector/Python26.7.0 default/prepared path; Go1.9.3 explicit Prepare and parameterized non-interpolated execution | Bound marker and commit/rollback correct; retain ordinary driver mode and exact prior exceptions; Go pools differ per child |
| R8 | Prepare once, close setup pool, Snapshot, two tests/children through both injection control and candidate route | Same baseline state, sibling isolation after commit, clean teardown; report first/second-test setup steps without a speed promise |

Run macOS arm64 first; supported Ubuntu x86_64 remains required before any
production-adoption recommendation. An unavailable environment is SKIP, never
PASS. Pure/C modes are separate where available; use the existing explicit
unsupported-import policy rather than quietly excluding a required mode.
This proposal covers these drivers as a first experiment, not the whole v0.6
compatibility matrix. Django, mysqlclient, asyncmy/aiomysql and other framework
adapters remain visible decisions, not implicitly supported or rejected.

Mutation controls must deliberately remove the pool-generation check, allow
original-target fallback, ignore the retired scope and use a single global
target. The corresponding negative oracle must detect each defect. Runtime
oracles must observe executed SQL/marker and original-target attempts, not only
the wrapper's metadata. Existing ORM/Prepared CI cannot detect these mistakes.

Deliver one R1–R8 PASS/FAIL/SKIP table with fixed inputs, logs, target observations,
helper diff, mode/OS and reproduced user consequences. A necessary hook repair
stays in the prototype; unexpected guest/protocol changes stop for a separate
scope decision. If a row remains inconclusive, specify the failed boundary and
bounded next action; do not label the spike complete at a time limit. Human
Review then chooses continue / productize / prefer explicit integration per case.

The largest expected work is Python saved-reference coverage, pool admission and
scope teardown, not DB startup or storage. Configuration injection is the cheaper
control; a driver hook adds version-specific maintenance and failure tests.
No measured implementation duration or performance benefit is available yet.

## 6. Prior-condition cross-check and review limits

| Prior condition | Judgment now | Detection / remaining work |
| --- | --- | --- |
| Preserve the full capability space and complementary methods | Satisfied for design | Alternatives above; full map still owns unselected framework/lifecycle axes |
| Keep Prepared and multi-result semantics, not text substitution | Adopted prerequisite satisfied | P6 evidence; R7 checks routing composition, not a new all-driver promise |
| Specify new/cold/idle/active/custom/concurrent states before a spike | Satisfied as proposed contract | Sections 4–5; runtime behavior remains unverified |
| Preserve consuming Snapshot, child independence, worker-local baseline | Design consistent | Existing ownership contract; R8 still required |
| Wrong-target/no-context must not silently use original DB | Unverified implementation | R1–R7 sentinel/mutations proposed; no existing routing CI |
| Give useful errors without unsupported attribution | Design specified, not implemented | R3/R5/R6 and original-cause assertions proposed |

Missing-things scan: no runtime/public-API change, generated ownership update,
release ledger or independent regeneration is needed for this documentation-only
step. No new CI, driver compatibility, platform execution, benchmark, integration
or publication PASS is claimed. Current guides describe explicit connection
configuration and do not promise this proposed routing. Historical source
reviews retain their dated “Prepared unsupported” observations; current status
now links the adopted prerequisite and this proposal instead of treating those
sentences as current support. Known gaps are exactly the unexecuted routing
matrix, current Connector hook inspection and later framework coverage above.

Basis: [north star](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven),
[capability map](v06x-capability-map.md),
[approved alternatives](v06x-workflow-design-options.md),
[first routing source findings](v06x-routing-source-findings.md),
[MySQL continuation](v06x-mysql-workflow-source-review.md),
[Snapshot contract](../decisions/snapshot-product-contract.md),
[accepted Prepared exceptions](../decisions/prepared-consumer-exceptions.md).
Documentation checks completed: source identity confirmed as a commit; all146
local file-link targets across this document and project-status exist;
`scripts/check_version.py` PASS for published0.5.3; `git diff --check` PASS.
Source and primary-documentation checks above were read-only. Runtime tests,
benchmarks and regeneration were not run for unchanged code. The experiment
and production decisions remain with the Human.
