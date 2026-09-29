# SQLAlchemy disposable-database dogfood

## Result and scope

**Ordinary SQLAlchemy defaults cannot connect to released mariamem v0.2.0.**
The first handshake fails with MySQL 1235, `unsupported connection capabilities`.
This is a mariamem compatibility gap, not a schema or test-lifecycle failure.
No product code, native artifacts, or public APIs were changed for this probe.

The application adapts the official [SQLAlchemy ORM Quick Start](https://docs.sqlalchemy.org/en/20/orm/quickstart.html)
and its Unified Tutorial patterns: typed declarative `User` / `Address`, a
one-to-many relationship with delete-orphan cascade, `Session`, commit, SELECT,
relationship loading, JOIN, UPDATE and DELETE. Adaptations for MariaDB are
bounded VARCHAR lengths and InnoDB tables; a unique user name adds a constraint
case. Rollback and FK/non-null failures are additional ordinary application tests.
There is no mariamem-specific dialect or application API.

## Reproduction and evidence

Measured on 2026-09-29: macOS 27.0 arm64, Python **3.14.7**, SQLAlchemy **2.0.54**,
PyMySQL **1.2.3**, pytest **8.4.2**. This covers this SQLAlchemy 2.0 combination,
not all SQLAlchemy versions or Ubuntu ORM behavior. Product checkout baseline:
`dca0413f6f7adfb97961271b164ff476241380bc`.

The consumer imports the installed **released wheel**, not the checkout:
`mariamem-0.2.0-py3-none-macosx_15_0_arm64.whl`, SHA256
`c60b8bd6a56699026f7af84eaed21efec6f0596d2c262d17032ace8ae261c4f3`.
Its bundled runtime is Wasmer 7.4.2; AOT SHA256 is
`a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d`.
The server reports `13.1.0-MariaDB-embedded`.

```sh
/opt/homebrew/bin/python3.14 -m venv build/sqlalchemy-dogfood/py314
build/sqlalchemy-dogfood/py314/bin/python -m pip install \
  -r tests/consumer/sqlalchemy-requirements.txt \
  'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.2.0/mariamem-0.2.0-py3-none-macosx_15_0_arm64.whl'
# Expected to fail until standard handshake compatibility is addressed:
build/sqlalchemy-dogfood/py314/bin/python tests/consumer/run_sqlalchemy.py \
  --output tests/evidence/sqlalchemy-dogfood-default
# Diagnostic condition only; NOT recommended as normal application configuration:
build/sqlalchemy-dogfood/py314/bin/python tests/consumer/run_sqlalchemy.py \
  --without-found-rows --output tests/evidence/sqlalchemy-dogfood-workaround
```

The runner copies only the application test into an external temporary directory,
clears native/path overrides, and verifies the import is inside the venv. It runs
serial Start / Fork / Fork / Start suites, each with 11 cases. The explicit A→B
isolation pair must run together in the maintained order; this is not an xdist
suite. JSON records the wheel origin/hash, native manifest, dialect, issued SQL,
pool events, database identities and teardown checks; JUnit/logs retain failures.
Raw evidence is ignored under `tests/evidence/`. Final observations are in
`sqlalchemy-dogfood-final-default/` and `sqlalchemy-dogfood-final-workaround/`.
These are compatibility observations, not controlled performance measurements;
some default and diagnostic suites overlapped in execution.

## SQLAlchemy compatibility

| Condition | Start suites | Fork suites | Interpretation |
|---|---|---|---|
| Standard dialect / pool | 2 × 11 setup errors | 2 × 11 setup errors | First connection rejected; Fork template cannot be prepared |
| Explicit `client_flag=0` probe | 2 × 11 passed | 2 × 11 passed | CRUD/lifecycle evidence conditional on changed rowcount semantics |

SQLAlchemy's MySQL dialect enables `CLIENT_FOUND_ROWS` for matched-row UPDATE
counts. mariamem's handshake rejects bit 2 in `internal/mysqlwire/wire.go`.
The diagnostic `connect_args={"client_flag": 0}` override leaves PyMySQL's basic
capabilities and all pool defaults intact but removes FOUND_ROWS. This isolated
the connection failure. It is **not a complete compatibility workaround**:
a no-op UPDATE matching one row returns **0**, whereas SQLAlchemy expects a
matched-row count of **1**. ORM stale-row/version checking can depend on that
contract; full optimistic-concurrency behavior was not tested. See
[SQLAlchemy rowcount support](https://docs.sqlalchemy.org/en/20/dialects/mysql.html#rowcount-support).

Under this explicit probe, MariaDB dialect/version detection, DDL, reflection of
PK/FK/unique constraints, relationship SELECT/JOIN, insert/update/delete commits,
explicit rollback, autocommit, and recoverable unique/non-null/FK errors passed.
IntegrityError retained MariaDB codes 1062, 1048 and 1452. Normal Session rollback
recovered the failed transaction and the database remained usable. Initial test
adaptation used a name longer than the upstream 30-character column; that was a
harness error, corrected by shortening the fixture rather than relaxing the model.

## Disposable isolation and pool/lifecycle behavior

Every test owns a new database. Test A commits a new user and ends with two
users; disposal performs no DELETE/TRUNCATE/schema reset. Test B has a different
database identity and sees only its seed user, with A's committed user absent.
This passed twice with fresh Start and twice with Snapshot/Fork, under the
explicit handshake probe. DELETE is an application operation; rollback cases
exercise application/failed-transaction semantics, not a cleanup wrapper.

QueuePool defaults remained size 5 / max overflow 10. Typical cases opened one
physical connection; the pool case opened two simultaneously and reused both.
No one-connection workaround was needed. Session variables and temporary tables
were isolated across the two physical sessions. Checkin rollback removed
uncommitted rows, but **did not clear session variables or temporary tables** on
that same reused connection. That is normal MySQL session lifetime / SQLAlchemy
[pool reset behavior](https://docs.sqlalchemy.org/en/20/core/pooling.html#reset-on-return),
not cross-database contamination. It matters if an application expects a pristine
session on every pool checkout.

Engine disposal followed by database close passed. Closing the database first
with idle pooled sockets, then disposing the engine, also passed. Teardown checked
zero active sessions where observable, removed log/runtime directories and absent
host/runtime PIDs. Failed default Start attempts were also cleaned up. Owned
snapshot directories were removed. This is evidence for these scenarios, not a
claim about every possible shutdown race or pool saturation.

## Snapshot/Fork value and test-author hypothesis

Snapshot/Fork successfully preserves the schema and seed, avoiding repeated DDL
and seed code per test. It did not demonstrate a material speed advantage for
this tiny schema: Start suite pytest durations were about 4.4–4.7 s and Fork
suites about 5.5–5.6 s including template/snapshot creation. These incidental times
are not a performance A/B result. Fresh Start is simpler and sufficient here;
Snapshot/Fork is useful when maintaining a prepared fixture, not mandatory.

The ordinary CRUD tests written for this task contain no state-restoration logic:
the fixture owns disposal. This supports the feasibility of cleanup-free tests
**under the diagnostic condition**. It does not establish that AI-generated tests
are less error-prone; there was no authoring/control study, and transaction and
pool-session reasoning is still necessary.

## v0.3 usability findings: next three tasks

1. **BLOCKER:** support the SQLAlchemy-required FOUND_ROWS handshake **and actual
   matched-row semantics**. Merely accepting the flag or recommending zero flags
   would hide an ORM correctness issue. Re-run the unchanged default application,
   including no-op UPDATE and optimistic-concurrency checks.
2. **P1:** document disposable fixture ownership and pooled-session lifetime with
   an idiomatic public example after default compatibility passes. Distinguish
   normal rollback/recovery from cleanup SQL; do not introduce framework APIs yet.
3. **P1:** repeat this consumer probe on Ubuntu and the current SQLAlchemy series,
   extending pool/shutdown coverage as evidence warrants. Current results cover
   only the released macOS wheel and this pinned 2.0 stack.

No mariamem implementation fix or broader compatibility guarantee is made here.
