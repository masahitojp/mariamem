# v0.6 routing and preparation — first source findings

2026-10-18. mariamem basis: `61c5d12`.
Read-only source/documentation investigation; no new runtime validation.
Companion: [approved design alternatives](v06x-workflow-design-options.md).

Continuation: [MySQL workflow source review](v06x-mysql-workflow-source-review.md)
now records MySQL-specific seams, Django/moto source, concrete upstream dump and
migration inputs, and compatibility/diagnostic findings. The outstanding-work
statements below describe this first pass; the continuation owns current progress.

## Human Review

Recommendation: preserve the one-line entry goal, but describe its capability by
connection state and language. Python driver routing plus framework pool hooks
is a supported design pattern in the inspected reference; Go configuration
injection and test-owned pool helpers have a different scope. Do not advertise
either as replacing arbitrary existing connections. Keep all three mechanisms
as candidates while specifying the states below before a spike.

The strongest objection is that this distinction could push lifecycle knowledge
back onto users. Address it in the integration: install at an appropriate fixture
boundary, own and close resources it creates, and give concrete diagnostics when
an existing resource cannot be rebound. Do not silently call a checked-out
connection migrated. Same-process concurrent routing remains an unresolved design
question, not a reason to drop the parallel-use goal.

## 1. Fixed reference and observations

GitHub commit API resolved pgmem `a61005d` to commit
`a61005d37d01e6671f814fe8ca828222e8147df4`, tree
`6989b187a4b744fb06678d7673c9f29e11a19bd1`. No clone, build or test was run.

| Observation | Primary evidence | Consequence for mariamem |
| --- | --- | --- |
| Python routes newly created psycopg/psycopg2/asyncpg connections and removes target-related arguments | [_shadow.py](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/_shadow.py), `install_driver_routes` | A useful mechanism pattern, not evidence that MySQL drivers share these interception points |
| SQLAlchemy guard tags connections with target identity and rejects a different identity at checkout | Same file, `install_sqlalchemy_pool_guard` | Routing creation alone misses pooled reuse; library integration needs a generation/ownership check |
| Tests cover a previously constructed cold engine and sequential reuse of one pool across two forks | [tests lines 163–192](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/tests/test_pytest_plugin.py#L163) | Test source documents intended coverage; it does not prove already-checked-out migration or concurrent target scopes, and these tests were not executed here |
| Marker installs routes/guard and removes guard after yield | [plugin lines 178–196](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/pytest_plugin.py#L178) | Read fixture ordering and patch cleanup together; a process-global hook does not by itself establish task-local isolation |
| Go ShadowPG sets environment before application/pool construction; comments explicitly exclude parallel tests/ancestors and already-open pool replacement | [Go helper lines 201–257](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/pgmemtest/pgmemtest.go#L201) | Corrects any inference that the Go helper transparently intercepts all drivers; configuration injection and returned test-owned pools are distinct options |
| Separate prepare fixture is a dependency of baseline construction | [plugin lines 45–58](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/pytest_plugin.py#L45) | Reusable lifecycle pattern; migration work can be user-defined without requiring users to reimplement Snapshot ownership |

Our [SQLAlchemy anchor](../../tests/consumer/test_sqlalchemy_dogfood.py) constructs
an engine from `connection_info`; our [GORM anchor](../../tests/consumer/gorm/dogfood_test.go)
constructs GORM from `db.DSN()`. These establish existing explicit connection
seams, not transparent legacy-application routing. The existing
[Snapshot contract](../decisions/snapshot-product-contract.md) still governs
source consumption, child independence, worker-local baselines and host lifetime.

## 2. Connection-state contract to specify before implementation

| State at integration entry | Candidate handling | Evidence status |
| --- | --- | --- |
| Application has not constructed its pool | Inject configuration or install supported creation route before construction | Reference supports both approaches in different languages |
| Engine exists but has no open connection | Supported driver creation route may suffice | pgmem has a cold-engine test; MySQL equivalent unverified |
| Pool contains idle connections from earlier test | Reject wrong generation at checkout, then reconnect via active route; define disposal ownership | pgmem guard and sequential reuse test are source evidence |
| Application holds an active connection/transaction | Do not silently move it; supported adapter must require/reach a release boundary or reject with a useful action | No migration proof; source guard is only at checkout |
| Two tests target different children in one process | Scoped injection/owned pool, or a proven task-aware routing mechanism | Global target hooks/environment are insufficient evidence of isolation |
| Child closes while an old handle survives | Detect stale ownership and report how to acquire a new test resource | mariamem design requirement, not implemented behavior |

SQLAlchemy 2.0's [engine disposal documentation](https://docs.sqlalchemy.org/en/20/core/connections.html#engine-disposal)
confirms that checked-out connections are not closed by engine disposal. Therefore
`dispose()` alone cannot establish that all application connections have ended.
The page was read on 2026-10-18 (displayed release 2.0.55); this is documentation
evidence, not a newly tested dependency version.

## 3. Preparation paths: what the source review establishes

Alembic's [connection-sharing recipe](https://alembic.sqlalchemy.org/en/latest/cookbook.html#sharing-a-connection-across-one-or-more-programmatic-migration-commands)
(read 2026-10-18; displayed 1.20.0) supplies a connection through
`Config.attributes`, with `env.py` explicitly consuming it. This is a concrete
migration integration path, but not zero-change compatibility with every existing
`env.py`. Compare that adapter with routing connections created by an unchanged
migration environment. No migration was executed in this investigation.

MariaDB's [dump documentation](https://mariadb.com/docs/server/clients-and-utilities/backup-restore-and-import-clients/mariadb-dump)
(read 2026-10-18) describes an initial sandbox command that older MariaDB clients
and the MySQL CLI cannot interpret. Thus server SQL compatibility alone does not
describe dump-import compatibility: producer options, client directives and
consumer versions matter. Existing-client orchestration and built-in import
remain alternatives; neither is validated by this documentation read.

Outstanding preparation evidence: acquire a concrete version-identified dump,
inventory its actual directives/statements and choose a bounded import oracle;
inspect a real Alembic environment and migration chain. This source review does
not satisfy the design plan's concrete dump inventory or migration execution.

## 4. Completion, remaining work and checks

Completed: fixed-reference Python/Go routing inspection; relevant pool/fixture
test source inspection; current SQLAlchemy/GORM construction seams; official
pool-disposal, migration-entry and dump-format constraints. No reference test is
reported PASS. No same-process routing isolation has been demonstrated.

Remaining: MySQL driver-specific interception points and saved function aliases;
framework adapter lifecycle (including Django); concrete preparation inputs;
comparison with additional reference patterns such as moto; diagnostic categories
and official MySQL/MariaDB compatibility links. The broader approved investigation
is not complete. Existing CI does not detect these external-source design gaps.

Next unit of work: specify the MySQL-side equivalents for new/cold/idle/active
connections and concurrent scopes, and inventory a concrete migration/dump pair.
Use those results to select a bounded prototype through Human Review. No runtime,
guest, public API, fixture semantics or compatibility promise changed here.
