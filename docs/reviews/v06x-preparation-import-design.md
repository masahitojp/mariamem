# v0.6 preparation/import — next investment decision

2026-10-24. Design source_commit:
`22c647d39c94d1e912699613c70d762732c01598` (adopted main).
Existing source evidence is reused below; no new native import/migration run,
external-source refresh, performance measurement or runtime change is claimed.

## Human Review

Decision now: approve a bounded migration/preparation workflow check before
choosing a dump-import product API. Recommend first demonstrating an actual
ordered migration chain and seed using explicit DB settings through the adopted
`mariamem_prepare`, then two ordinary application tests through `shadow_maria`.
Use the same source schema/data as the input to the later dump comparison.

The user benefit is a complete first-test/second-test recipe: supply the existing
migration target once, prepare once per worker, and write independent application
tests. A working callback alone does not establish that real migration tooling
and its connection cleanup fit this lifecycle.

The strongest objection is that legacy applications may have only a dump; a
migration-first check would not help them yet. Keep dump import as an explicit
companion decision with native-client and library alternatives below, not as a
silently excluded capability. The bounded migration check exercises the common
preparation/capture/child/failure boundary without first committing to a SQL
script interpreter or a required external executable.

This is a proposal for Human Review, not authorization to implement an importer,
change guest/runtime semantics or reduce the agreed v0.6 capability map.

## What already exists and what is missing

| Boundary | Existing evidence | Remaining work |
| --- | --- | --- |
| Python preparation entry | Adopted `mariamem_prepare`: None/no-op or callback receiving source DB; native seed and two-worker child tests passed inCI40061580952 | Actual migration-tool configuration/ordered revision chain, user recipe and failure diagnostics |
| Test application entry | Adopted marker, supported drivers/pool ownership and same-child direct access | Connected preparation-to-application example; no claim of every framework |
| SQL/routines/Prepared | Adopted source supports bounded routines, text multiple results and Prepared | Not equivalent to interpreting a dump file or client commands |
| Dump input inventory | Pinned upstream12.3.3 expected dump segment already inspected | Fresh identified application dump, runtime import evidence and import-method choice |
| Errors | Driver/SQL causes and preparation-fixture failures are retained | Preparation phase/source location and concrete advice; do not guess app vs compatibility origin |

The current [entry implementation](v06x-shadow-maria-implementation.md) and
[guide](../connection-routing.md) own current support. The older capability map
and source reports are historical inventories; their then-pending Prepared or
routing statements do not reopen completed work.

## Ways to prepare the same baseline

| Direction | User supplies | Benefit | Cost or lost convenience |
| --- | --- | --- | --- |
| Existing migration/seed library | Preparation DB settings to the tool/configuration | Reuses application-owned schema evolution, no new mariamem SQL parser | Tool must accept explicit settings; one configuration adaptation can be needed |
| Existing dump client | File plus preparation target to a compatible MariaDB/MySQL client | Reuses handling of delimiters and client directives | Additional executable/install/version management; weakens the library-only setup experience if mandatory |
| Library dump reader | File plus preparation DB to a future helper | Could preserve a Docker-free, no-extra-client journey | Must define producer/options, lexical/client directives, errors and partial state; ordinary cursor.execute or splitting on semicolons is insufficient |

These are input routes to the same preparation -> close connections -> Snapshot
-> independent child lifecycle. Dump-client orchestration is an alternative and
comparison oracle, not a selected default. A library helper must not silently
strip unsupported SQL, alter engines/collations or remove routines to pass.

## Reused evidence and limits

The [prior MySQL workflow investigation](v06x-mysql-workflow-source-review.md#3-concrete-preparation-inventory)
records pinned MariaDB12.3.3 dump output, Django5.2.7 migration inputs and an
Alembic1.18.4 generic environment. These are source observations, not new PASSes.

- The existing decimal dump segment includes executable comments, a sandbox
  client directive, MyISAM/utf8mb4, exact DECIMAL values and transaction/session
  settings. Extract only the intended segment; the upstream result file also
  contains surrounding test input and cleanup. It is not a fresh application
  dump or comprehensive input corpus.
- The Django pair describes schema evolution, but needs its app configuration.
  The Alembic generic environment reads configuration, not an automatically
  supplied `Config.attributes['connection']`. Passing attributes alone is not a
  universal injection recipe. Preparation-time automatic routing is excluded
  from0.6.0; configure the explicit target.
- Current SQLAlchemy dogfood uses `create_all`; it is useful ORM evidence but
  not a versioned migration-chain PASS.
- Routines include procedures/functions; packages are outside product support
  and events remain an embedded restriction. An import path must explain such
  failures rather than remove statements or broaden engine support claims.

No support is inferred for unexecuted frameworks or formats. In particular,
Django/mysqlclient integration, arbitrary MySQL dumps, CSV and other externally
produced data remain visible coverage decisions in the capability map.

## Proposed bounded migration check

Use the existing supported SQLAlchemy/PyMySQL path and select/fix an executable
Alembic project and two ordered revisions before running. Record whether the
input is an existing external application or a repository-authored example;
do not describe a new toy chain as proof for arbitrary legacy applications.
Pin the development-only tool/source inputs; this does not update product
runtime dependencies or choose an installation extra.

1. Configure the migration tool with the source DB settings explicitly. Create
   the intended application schema, apply two ordered revisions, and seed data.
2. Verify the recorded revision plus final tables/columns/constraints/data;
   close/dispose tool connections before Snapshot. No preparation auto-routing.
3. Run a first child test committing a small change and a second child test
   starting from the prepared state. Check constraints and exact seed contents,
   not just SELECT1. Reuse the real application connection marker.
4. Inject a failure in the later revision and in seed. Preserve original cause
   and identify the preparation stage. Assert no successful Snapshot or child
   is admitted, and report cleanup independently. MariaDB DDL may leave partial
   source changes; discarding a failed preparation is not an all-DDL rollback
   guarantee or an implicit retry.
5. Produce one copyable user recipe and record configuration/setup steps plus
   per-test additions. Do not turn these observations into a speed benchmark.

Finish with PASS/FAIL/SKIP evidence, exact inputs/source and a Human Review on
whether that recipe/helper boundary should be adopted. If normal explicit
configuration cannot work, explain the concrete obstacle; do not automatically
reintroduce preparation routing or broaden guest changes.

## Following dump decision — still required

Choose a freshly produced, version-identified application dump with ordinary
InnoDB schema/data, escaping and procedure/function content. Compare the native
client/reference with a bounded library-reading candidate only after fixing
supported directives and success/failure oracles. Preserve values/schema,
statement order and error location; deliberate unsupported inputs must fail
clearly without publishing a partial baseline. Whether to include an importer,
document an optional external client or defer a specific format is a separate
Human decision; the migration check does not make that choice.

## Boundaries and other remaining work

No preparation-time automatic connection switching in0.6.0 (reconsider in0.6.x).
Live remains a separate task, including its0.6.0 scope decision. Actionable
failures/compatibility references and remaining framework coverage are companion
work, not completed by migration success. This design does not start final
Qualification, Product Validation or release.

Basis: [north star/capability map](v06x-capability-map.md),
[connected alternatives](v06x-workflow-design-options.md),
[MySQL source findings](v06x-mysql-workflow-source-review.md),
[Snapshot contract](../decisions/snapshot-product-contract.md),
[routing contract](../decisions/connection-routing-contract.md), and
[SQLAlchemy dogfood](../../tests/consumer/test_sqlalchemy_dogfood.py).
