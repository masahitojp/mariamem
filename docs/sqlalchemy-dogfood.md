# SQLAlchemy disposable-database dogfood

> Historical Wasmer/migration reference. Current runtime, verification and roadmap
> are documented in [project status](project-status.md) and
> [development](development.md); this is not a supported fallback workflow.

## Result and scope

The original SQLAlchemy blocker is fixed on this branch. SQLAlchemy's default
MySQL dialect enables `CLIENT_FOUND_ROWS`; the host now carries that negotiated
bit into the guest MariaDB client connection. Unchanged UPDATEs return 1 for a
FOUND_ROWS client and 0 for existing clients without the flag. The SQLAlchemy
dogfood passes with ordinary engine defaults and no flag workaround.

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
build/sqlalchemy-dogfood/py314/bin/python tests/consumer/run_sqlalchemy.py \
  --native-dir build/sqlalchemy-dogfood/native \
  --output tests/evidence/sqlalchemy-dogfood-found-rows
```

For this branch acceptance, the venv imports the released Python wheel outside
the checkout; `--native-dir` selects the locally built, unaccepted host/runtime/
guest bundle containing the change. The bundle was built from the current guest
source and Wasmer 7.4.2 for this test only. It is not a release candidate or a
published artifact. The runner clears inherited runtime overrides, then applies
only this explicit bundle path. The previous unmodified v0.2.0 bundle's failure
is retained as historical evidence in `sqlalchemy-dogfood-final-default/`.

The runner executes four serial 11-case suites in Start / Fork / Fork / Start
order. A→B isolation cases must remain together and in maintained order; the
suite is not an xdist run. JSON records the wheel origin/hash, native manifest,
dialect, pool events, SQL, database identity and teardown checks; JUnit and logs
retain failures. Raw evidence is ignored under `tests/evidence/`. These are
compatibility observations, not controlled performance measurements.

## SQLAlchemy compatibility

| Condition | Result | Evidence |
|---|---|---|
| Released v0.2.0 host/runtime bundle before this fix | Rejected `CLIENT_FOUND_ROWS` with MySQL 1235 | Historical default run |
| Branch host + rebuilt guest, SQLAlchemy defaults | 4 × 11 cases passed | 2 Start and 2 Fork suites |
| PyMySQL without FOUND_ROWS | Connects; unchanged UPDATE rowcount = 0 | Raw wire acceptance |
| PyMySQL with FOUND_ROWS | Connects; unchanged UPDATE rowcount = 1 | Raw wire acceptance |

The host accepts `CLIENT_FOUND_ROWS`, reopens that session with an internal
FOUND_ROWS option byte, and the guest passes `CLIENT_FOUND_ROWS` to
`mysql_real_connect()` before establishing its MariaDB session. Unflagged
connections keep the previous single-open path. This preserves MariaDB's own
matched-versus-changed row accounting rather than adjusting counts in the host.

With standard SQLAlchemy behavior, MariaDB dialect/version detection, schema
creation, primary/foreign/unique constraint reflection, one-to-many relationship
loading, JOIN, inserts/updates/deletes with commits, rollback, autocommit, and
recoverable unique/non-null/FK errors passed. IntegrityError retained codes
1062, 1048 and 1452. A no-op UPDATE through SQLAlchemy returned `rowcount=1`.

The earlier fixture's committed marker exceeded the User name column's 30
characters; shortening only test data fixed this harness error. It did not
require changing the SQLAlchemy model or product behavior.

## Disposable isolation and pool/lifecycle behavior

Every test owns a new database. Test A commits a new user and ends with two
users; disposal performs no DELETE/TRUNCATE/schema reset. Test B has a different
database identity and sees only its seed user, with A's committed user absent.
This passed twice with fresh Start and twice with Snapshot/Fork, with standard
SQLAlchemy connection options. DELETE is an application operation; rollback cases
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
with SQLAlchemy defaults and the branch candidate native bundle. It does not establish that AI-generated tests
are less error-prone; there was no authoring/control study, and transaction and
pool-session reasoning is still necessary.

## v0.3 usability findings

- **BLOCKER resolved on this branch:** `CLIENT_FOUND_ROWS` now reaches the
  MariaDB connection and preserves the requested affected-row semantics.
- **P1:** run the same installed-wheel consumer acceptance on Ubuntu 24.04 and
  repeat against the current SQLAlchemy 2.1 series before broadening the
  compatibility statement. This result covers macOS arm64 and SQLAlchemy 2.0.54.
- **P1:** document pooled connection state lifetime for application authors.
  SQLAlchemy's normal rollback-on-checkin does not clear MySQL session variables
  or temporary tables on a reused physical connection; disposable DBs avoid
  cross-test database residue but do not reset a session between checkouts.

The CRUD tests need no state-restoration SQL because each owns and closes a
separate database. This supports cleanup-free disposable tests for this example;
it is not evidence that AI-authored tests are less error-prone. No wider ORM
compatibility guarantee is made here.

## Follow-up cross-platform acceptance

The earlier local-only observations above are historical. SQLAlchemy passed
44/44 on clean macOS 15 arm64 and Ubuntu 24.04 x86_64 in
[run 36582171063](https://github.com/masahitojp/mariamem/actions/runs/36582171063),
source `872fdea882ad82540ffe32e14e506ff67b2d10c3`, without framework-specific
workarounds. Committed CRUD isolation, normal pools and lifecycle cleanup passed
on both platforms. See [v0.3 acceptance](v03-acceptance.md) for artifact identity,
related regression checks and the dedicated audit-readiness conclusion.
This closes the two-platform dogfood acceptance gap; it does not broaden the
supported framework/version matrix or establish a Snapshot/Fork speed advantage.
