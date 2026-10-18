# v0.6 MySQL workflow source review

2026-10-18. mariamem source basis: `61c5d12` (unchanged runtime).
Continuation of [first source findings](v06x-routing-source-findings.md), within
the approved [workflow alternatives](v06x-workflow-design-options.md).
Source inspection only; no dependency was installed and no guest/test was run.

## Human Review

Recommendation: prototype complementary routes, with one common preparation and
lifecycle contract: Python driver entry interception plus a SQLAlchemy pool
adapter; Go test-owned connector/pool or application configuration injection.
Retain Django as a framework lifecycle adapter design, rather than assuming that
changing its driver's destination completes integration. Keep native dump-client
orchestration and built-in import as alternatives until their input oracle is run.

Decisive finding: new connection creation has identifiable seams in the inspected
MySQL drivers, but neither redirecting creation nor replacing an idle pool moves
an application-held connection. This is a lifecycle boundary the integration
must handle. It need not become a setup exercise for every user: install at the
right test boundary, own resources created there, and report a specific action
when a pre-existing handle cannot be adopted.

Strongest objection: making the simple entry depend on a clean application startup
could exclude valuable legacy use. Do not discard pre-created engines or idle
pools: the candidate matrix below includes them. Keep active handles and
long-lived endpoints visible as distinct cases. The recommendation is a bounded
prototype to test these seams, not a claim of universal routing or a narrowed
v0.6 support contract. Implementation still needs Human approval.

## 1. Source identities and coverage

GitHub commit endpoints resolved the named versions to these commit objects.
No build/benchmark inputs were produced; tag object IDs are not substituted for
source commits. Files were read at those commits, not mutable branch heads.

| Project / version | source_commit | Files inspected |
| --- | --- | --- |
| PyMySQL 1.2.3 (existing consumer pin) | `c990e86083c26493f3285b1e047902994c4b1811` | `pymysql/__init__.py`, `pymysql/connections.py` |
| SQLAlchemy 2.0.54 (existing consumer pin) | `bb8a90153888a5ca55576044dcdbcb20cd795afc` | `lib/sqlalchemy/engine/create.py`, `default.py` |
| go-sql-driver/mysql 1.9.3 (existing consumer pin) | `62984ada4402df6571557bc3fed2bcbde48ec908` | `driver.go`, `connector.go` |
| mysqlclient 2.2.7 (reference) | `2076d161e2f09f3fb99e00134c9f415063924ad9` | `src/MySQLdb/__init__.py` |
| Django 5.2.7 (reference) | `3cff3209e35a560f94801d428cf7f2a3ecb2a051` | MySQL backend, base connection/creation, migration pair below |
| Alembic 1.18.4 (reference) | `766b5ee98e0aeea85a18f272a1ac813712ee0697` | generic `env.py`, `tests/test_command.py` |
| moto 5.1.15 (pattern reference) | `98bf6b5b9b1f0919560824f512dfdadd6bec5a6b` | `moto/core/models.py` |
| MariaDB 12.3.3 (dump source reference) | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` | bounded sections of `mysql-test/main/mysqldump.test` and `.result` |

Reference versions are investigative samples, not newly supported dependencies
or claims to be the latest release. Existing consumer pins are read from
`tests/consumer/sqlalchemy-requirements.txt` and `tests/consumer/gorm/go.mod`.

## 2. Connection seams and their limits

| Path | Confirmed source behavior | Candidate implication / unresolved boundary |
| --- | --- | --- |
| PyMySQL entry | [`__init__.py`](https://github.com/PyMySQL/PyMySQL/blob/c990e86083c26493f3285b1e047902994c4b1811/pymysql/__init__.py#L136) aliases `Connect`, `connect`, `Connection` to the class; [constructor](https://github.com/PyMySQL/PyMySQL/blob/c990e86083c26493f3285b1e047902994c4b1811/pymysql/connections.py#L177) stores options and normally calls `self.connect()` | Replacing only the module's `connect` does not rewrite previously imported aliases. Class-method interception could cover saved class aliases, but constructor vs connect seams must be compared, including deferred connect and reconnect |
| PyMySQL target selection | Constructor accepts host/port/user/password/database, Unix socket, option files and TLS parameters | Changing host/port alone is not enough; option-file/socket/auth handling needs an explicit policy. Preserve SQL-affecting options rather than silently dropping charset, autocommit or init commands |
| SQLAlchemy normal creator | [`create.py:632`](https://github.com/sqlalchemy/sqlalchemy/blob/bb8a90153888a5ca55576044dcdbcb20cd795afc/lib/sqlalchemy/engine/create.py#L632) closes over arguments; [`default.py:631`](https://github.com/sqlalchemy/sqlalchemy/blob/bb8a90153888a5ca55576044dcdbcb20cd795afc/lib/sqlalchemy/engine/default.py#L631) calls the DBAPI's current `connect` | A cold pre-created engine using the default path is a plausible routing candidate. A supplied `creator`/pool or event-returned connection bypasses that assumption. Existing idle connections still need generation checks |
| mysqlclient | [`Connect`](https://github.com/PyMySQL/mysqlclient/blob/2076d161e2f09f3fb99e00134c9f415063924ad9/src/MySQLdb/__init__.py#L121) imports its connection class when called; module aliases reference this factory | Saved factory aliases differ from PyMySQL class aliases. Replacing only `MySQLdb.connect` does not replace saved factory references; native constructor interception is not established by this read |
| Go mysql | [`NewConnector`](https://github.com/go-sql-driver/mysql/blob/62984ada4402df6571557bc3fed2bcbde48ec908/driver.go#L100) and [connector Connect](https://github.com/go-sql-driver/mysql/blob/62984ada4402df6571557bc3fed2bcbde48ec908/connector.go#L65) construct new physical connections with configuration and optional dialing hooks | Test-owned connector/pool is a concrete integration seam. Global network dial interception changes transport only, not necessarily auth/database/session semantics; it does not move idle/active pooled connections |
| Django | [MySQL backend](https://github.com/django/django/blob/3cff3209e35a560f94801d428cf7f2a3ecb2a051/django/db/backends/mysql/base.py#L255) calls `Database.connect`; [base wrapper](https://github.com/django/django/blob/3cff3209e35a560f94801d428cf7f2a3ecb2a051/django/db/backends/base/base.py#L237) retains a live connection | Driver routing is a candidate for new connections, not a full test-runner adapter. [Test DB creation](https://github.com/django/django/blob/3cff3209e35a560f94801d428cf7f2a3ecb2a051/django/db/backends/base/creation.py#L32) creates a DB, changes NAME and calls migrate; teardown/clone/keepdb semantics also need design |

Existing mariamem SQLAlchemy/GORM anchors explicitly construct an engine/pool
from the child endpoint. Their success does not validate interception. Existing
[lifecycle/ownership](../decisions/snapshot-product-contract.md) remains the
contract: baseline capture consumes a disconnected source; children are isolated.

### Same-process concurrency and saved references

A process-global replacement that closes over one target is not enough for two
concurrent tests. Candidate: stable installed wrappers resolve a scoped target
at connection creation, with identity attached to owned connections and checked
at pool checkout. Python [ContextVar](https://docs.python.org/3/library/contextvars.html)
supports context-local values and asyncio; thread propagation and background work
outliving the scope still require explicit policy and tests. Context-local target
selection alone does not make a shared physical connection safe.

Go's reference environment-variable helper is process-wide; per-test owned
connectors/pools or a configuration seam avoid assigning one global destination
to concurrent tests. Neither approach can rewrite arbitrary already-open handles.
Do not claim this implies every Go application requires redesign: inspect the
application's existing configuration seam first.

### What moto adds to the comparison

[moto `patch_client`](https://github.com/getmoto/moto/blob/98bf6b5b9b1f0919560824f512dfdadd6bec5a6b/moto/core/models.py#L275)
explicitly handles clients constructed before normal hook installation by adding
a client event handler. It illustrates a simple normal entry plus an explicit
existing-object adapter. DB sessions have transaction state, so this is UX
inspiration, not proof that a DB connection can be retargeted the same way.
The inspected mock lifecycle also uses shared nesting/patch state; its lock is
not evidence of isolated concurrent databases.

## 3. Concrete preparation inventory

### Dump: MariaDB 12.3.3 upstream decimal regression

Inspect the `Bug#2005` section of
[mysqldump.test](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysql-test/main/mysqldump.test#L35)
and [expected output](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysql-test/main/mysqldump.result#L29).
The input is `t1(a DECIMAL(64,20))` with two large exact integer values;
the command is the test harness's `$MYSQL_DUMP --compact test t1`.
This is pinned upstream expected dump output, not a newly generated dump.

Inventory of that dump segment: sandbox client directive; executable version
comments saving/changing/restoring character set; CREATE TABLE with MyISAM and
utf8mb4 collation; save/disable autocommit; multi-row INSERT of exact decimal
literals; COMMIT; autocommit restore. The result file also contains surrounding
test input and DROP cleanup, so it must not be fed whole to an importer.

Proposed success oracle: exact schema/type and both decimal strings preserved,
not float-converted; capture then two children initially match; changing one
child leaves the other unchanged. Failure oracle: an unsupported directive or
injected invalid statement reports phase/location and original cause; partial
preparation is not promoted to a baseline. Preserve engine/collation or reject
explicitly; do not rewrite to InnoDB merely to pass. This small non-InnoDB example
does not represent all application dumps; follow-up input must include typical
InnoDB data, escaped delimiters and routines before broader import claims.

An older system-schema dump was also encountered (`std_data/mysql_database_10.4.dump`,
header identifies 10.4.13); it is not selected as an application fixture or
evidence of 12.3.3-produced output. No dump was executed or freshly generated.

### Migration: actual Django two-step input and Alembic entry path

Django 5.2.7's pinned [0001_initial](https://github.com/django/django/blob/3cff3209e35a560f94801d428cf7f2a3ecb2a051/tests/migrations/test_migrations/0001_initial.py)
creates Author and Tribble, fields and a uniqueness constraint.
[0002_second](https://github.com/django/django/blob/3cff3209e35a560f94801d428cf7f2a3ecb2a051/tests/migrations/test_migrations/0002_second.py)
depends on it, deletes Tribble/removes a field, adds rating and creates Book with
a nullable foreign key. This is a concrete schema-evolution chain, not a fixture
that only calls create_all. Proposed oracle: migrations recorded in order, final
tables/columns/constraint agree, seeded rows survive capture and child isolation.
Test-runner rollback/flush must not accidentally be substituted for DB-per-test
isolation. Running the upstream fixture requires its app configuration; no claim
that the two files alone form an executable project.

Alembic 1.18.4's [generic env.py](https://github.com/sqlalchemy/alembic/blob/766b5ee98e0aeea85a18f272a1ac813712ee0697/alembic/templates/generic/env.py)
builds an engine from configuration with NullPool. It does not consult an injected
`Config.attributes['connection']`. Thus the official connection-sharing recipe
requires an adapted env.py; setting that attribute alone is insufficient for the
generic template. Compare configuration/routing of this existing path with an
explicit adapter. A real application Alembic chain remains to be selected; the
Django pair closes concrete migration inventory, not Alembic execution coverage.

## 4. Actionable diagnosis and official information

Candidate messages/behaviors, not newly implemented errors:

| Known evidence | Useful user action | What must not be inferred |
| --- | --- | --- |
| Tracked connection belongs to an earlier child | Close/recreate the named pool through the supported integration; show lifecycle phase | All outside connections can be enumerated or safely closed |
| Preparation failed at dump statement/directive | Report position, preserved cause and supported import route; do not capture partial state | Arbitrary syntax errors are definitely MySQL/MariaDB differences |
| Host rejected a known command/capability | Name mariamem's missing feature, applicable setting and impact on tested semantics | SQLState 42000 alone identifies that origin |
| Guest returned a SQL error | Preserve errno/state; add known preparation/target context | The application is necessarily wrong |
| A route has no target in its current scope | Identify the missing fixture/context and supported entry | Silently use the original destination under an assumed active redirect |

Existing [HostError](../../errors.go), [wire errors](../../internal/mysqlwire/wire.go)
and Python diagnostics provide foundations. Some wire errors already identify
mariamem timeout/session capacity, while unsupported commands remain generic.
Structured origin should be captured where known rather than reverse-inferred
from shared SQL error codes. Detailed reports should omit credentials and data
values by default; next-action messages need not dump the complete SQL text.

Official reference entry: [MariaDB versus MySQL compatibility](https://mariadb.com/docs/release-notes/community-server/about/compatibility-and-differences/mariadb-vs-mysql-compatibility).
The linked [Rolling vs MySQL 8.0 page](https://mariadb.com/docs/release-notes/community-server/about/compatibility-and-differences/incompatibilities-and-feature-differences-between-mariadb-rolling-and-mysql)
explicitly states MariaDB 12.1.1 / MySQL 8.0.36 as its comparison basis when read
on 2026-10-18. Link it as official background with its stated versions, not as
an exact 12.3.3 compatibility certificate. Keep engine differences separate from
mariamem's narrower wire surface. This fulfills locating a useful entry point;
it does not claim every difference has been mapped to diagnostic messages.

## 5. Python prepared statements — design prerequisite

Follow-up requested by the Human on 2026-10-18: explicitly include Connector/Python
`connection.cursor(prepared=True)` in the design cases. Recommendation: yes;
this is a concrete Python binary-protocol consumer, not only a Go driver issue.
The [official prepared-cursor documentation](https://dev.mysql.com/doc/connector-python/en/connector-python-api-mysqlcursorprepared.html)
distinguishes this interface from SQL PREPARE/EXECUTE and documents parameter
binding and repeated execution. Existing PyMySQL/SQLAlchemy anchors do not cover it.

Source sample: mysql/mysql-connector-python 9.4.0, commit
`ca251cf833e5697b59b2d10fb77b6b445be176ec`, tree
`1f56a5d7835e75f88dabb2f097a11bbd65ee50c5`, resolved by the commit API.
This is a fixed inspection sample, not a new supported/latest-version claim.
[Pure-Python cursor](https://github.com/mysql/mysql-connector-python/blob/ca251cf833e5697b59b2d10fb77b6b445be176ec/mysql-connector-python/lib/mysql/connector/cursor.py#L1224)
prepares a changed statement, resets it before execution, executes bound values,
and closes the old statement on replacement/closure. The
[connection implementation](https://github.com/mysql/mysql-connector-python/blob/ca251cf833e5697b59b2d10fb77b6b445be176ec/mysql-connector-python/lib/mysql/connector/connection.py#L1569)
reads parameter/column metadata from PREPARE, uses STMT_EXECUTE and binary results,
and sends IOBase parameters through STMT_SEND_LONG_DATA. STMT_FETCH is conditional
on server cursor state, not established as necessary for an ordinary execute.
The [C-extension cursor](https://github.com/mysql/mysql-connector-python/blob/ca251cf833e5697b59b2d10fb77b6b445be176ec/mysql-connector-python/lib/mysql/connector/cursor_cext.py#L1143)
has analogous prepare/reset/execute calls; its native path must be validated
separately rather than inferred from pure-Python tests.

Current mariamem wire dispatch rejects these commands with 1235/42000 once
reached. This is source-derived, not a reproduced Connector/Python session;
handshake/initialization may expose another gap earlier. Guest query bridging
currently uses mysql_real_query/mysql_store_result, not a mysql_stmt interface.

Design consequences:

- Treat connection routing and statement support as separate prerequisites.
  Preserve prepared=True; never silently switch the cursor/driver to text mode
  to make a test appear compatible.
- Track statement IDs, parameter types, metadata and results per physical SQL
  session. A statement from an old pool connection/child must not survive an
  unrelated new session. Bind generation checks to this lifecycle.
- Compare host-side emulation with a guest prepared-statement bridge. Host-only
  SQL interpolation is a hypothesis, not equivalent support: prepare-time errors,
  metadata, signedness, null/binary/decimal/time values and schema changes matter.
- Basic oracle needs prepare/reset/execute/close, repeated binding, SELECT and
  writes, rollback/commit, multiple cursors and connection disposal. Include
  pure-Python and C-extension modes where available; separately decide long-data,
  server-cursor and pool-reset coverage. Do not confuse STMT_RESET with
  COM_RESET_CONNECTION.

This adds prepared requirements to the next routing/preparation design review;
it does not authorize implementation or require all wire features before a
routing-only prototype. Such a prototype must label its prepared boundary unmet.

### Go explicit and implicit prepared paths

The Human also supplied [Go's prepared-statement guide](https://go.dev/doc/database/prepared-statements).
Include DB.Prepare/PrepareContext, Tx.Prepare/Tx.Stmt (and context variants),
and Conn.PrepareContext as distinct lifecycle cases. These are ordinary Go usage,
not an exotic optional consumer.

At the pinned go-sql-driver/mysql 1.9.3 commit,
[`Prepare`](https://github.com/go-sql-driver/mysql/blob/62984ada4402df6571557bc3fed2bcbde48ec908/connection.go#L206)
sends COM_STMT_PREPARE directly. `interpolateParams=true` does not convert an
explicit Prepare into text execution. Exec/Query with arguments and interpolation
disabled return driver.ErrSkip for database/sql fallback; parameterless text
queries are a different case. The current mariamem DSN's interpolation setting
therefore does not provide general Go prepared-statement support.

The next design must cover both Python prepared cursors and Go Stmt lifetime:
DB-level statements used with pooled connections, transaction-bound statements,
reserved-connection statements, repeat execution, close, and replacement of a
physical connection. Logical Stmt identity must not be confused with a single
server statement ID. Test explicit Prepare even with interpolation enabled,
and parameterized Exec/Query without interpolation. No such new acceptance run
was performed in this source review.

The Human subsequently approved prepared support in both languages as mandatory
for the one-line-switching goal. The [implementation comparison and current
Human Review](v06x-prepared-design.md) distinguish that approved requirement from
the proposed guest-API spike, whose implementation authorization is still pending.

## 6. Proposed bounded validation and completion accounting

Before a prototype, select the behavior at each of these boundaries:

1. Fresh connection, cold pre-created engine, sequential idle-pool reuse,
   saved import alias, explicit custom creator, held active connection.
2. Two simultaneous targets; background task after scope close; restoration
   after setup/test/teardown error. Assert actual target and zero unintended
   fallback with a controlled local sentinel, not a real production endpoint.
3. Dump segment and migration chain above: success, intentional preparation
   failure, then independent children. Measure first/second-test authoring steps
   separately from runtime; no new performance promise is set here.

These cases expose rather than hide the limits of each mechanism. Use identical
cases for competing mechanisms. CI cannot infer routing correctness from current
explicit-DSN dogfood; the prototype needs these targeted oracles.

Completed in this continuation: pinned PyMySQL/mysqlclient/Go creation seams,
SQLAlchemy custom/default path distinction, Django lifecycle entry, moto pattern,
concrete upstream dump segment and migration pair inventory, actionable failure
categories and official compatibility entry/version caveat. Checks were read-only
source/document review and local document link/diff checks.

Not completed: runtime proof of any routing/import path; asyncmy/aiomysql/MySQL
Connector, other framework/version combinations and context propagation; real
application Alembic chain; broader dump syntax coverage; final mechanism/API
selection. These remain in the capability map and must receive explicit scope
decisions, not be silently counted as supported or excluded. No guest/runtime
change, compatibility campaign, benchmark or release activity occurred.
