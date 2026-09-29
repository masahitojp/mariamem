# GORM disposable-database dogfood

## Result and scope

Ordinary GORM CRUD works with a disposable mariamem DB per test, without
cleanup SQL or pool restrictions. **Existing-schema discovery is a compatibility
blocker:** a second `AutoMigrate` fails with MariaDB 1050, `Table 'users' already
exists`. The maintained probe deliberately fails there; no migrator override,
SQL rewrite, disabled check, or production change hides it.

The conventional User / Address model uses GORM's documented
[MySQL connection](https://gorm.io/docs/connecting_to_the_database.html),
[has-many associations](https://gorm.io/docs/has_many.html),
[migration](https://gorm.io/docs/migration.html), and
[transaction](https://gorm.io/docs/transactions.html) patterns. Models include
primary/foreign keys, a unique non-null name, nullable fullname, and timestamps.
`gorm.Open(mysql.Open(dsn), &gorm.Config{})` keeps normal defaults, including
write transactions and pooling. The public mariamem DSN enables interpolation;
standard `parseTime=true` is added for Go `time.Time`. No single-connection limit,
special GORM dialect, `SkipInitializeWithVersion`, or prepared-statement mode
is added.

## Environment and reproduction

- macOS 27.0 arm64, Go 1.26.8; Ubuntu was not exercised in this task.
- GORM 1.31.1, GORM MySQL driver 1.6.0, go-sql-driver/mysql 1.9.3.
- Remote mariamem source `d036296708aef04ff1677869db50fc2576c80b47`, retrieved as
  `v0.2.1-0.20260929104630-d036296708ae`. This is a Go pseudo-version for the
  SQLAlchemy fix, not a new public mariamem release.
- Server `13.1.0-MariaDB-embedded`; Wasmer 7.4.2. The explicit local bundle from
  SQLAlchemy branch acceptance has package metadata `0.2.0` and AOT SHA256
  `d914dd9100870b05b03852be473e173a8415ccd5f520b2ed1aca522b66a64fc8`.
  It includes the modified guest and is not a published/approved release bundle.

```sh
python3 tests/consumer/run_gorm.py \
  --native-dir build/sqlalchemy-dogfood/native \
  --output tests/evidence/gorm-dogfood-final
```

Supply an existing matching native bundle: this runner never builds/downloads
one. It copies the pinned consumer module into a temporary directory outside
the checkout and uses the remote module without `replace`, with `GOWORK=off`
and Go 1.26.8. Start / Fork / Fork / Start suites each run eight sequential cases.
The A→B pair must remain in order. JSON captures module/native identities,
timings, pool statistics, connection IDs, SQL diagnostics, and cleanup; raw logs
and evidence remain ignored under `tests/evidence/`. Exit status is nonzero
while the observed migration blocker remains.

## GORM compatibility

Each of four suites passed seven cases and failed the existing-schema migration
case: **28 pass / 4 fail**.

| Path | Observation |
|---|---|
| Open/version detection; initial AutoMigrate | Passed unchanged; schema, indexes and FK created |
| Create/read/update/delete | Passed; generated IDs, timestamps and nullable field worked |
| Associations | Automatic child insertion, Preload and belongs-to JOIN passed |
| Transactions | Intentional commit persisted inside its DB; explicit rollback removed its own uncommitted write |
| Constraint errors | 1062 unique, 1048 non-null and 1452 FK retained driver error codes; normal queries still worked |
| Repeat AutoMigrate / HasTable | Failed consistently; schema discovery returns empty current database |
| Runtime close with pooled connections | Passed; subsequent SQL failed, pool close and runtime cleanup succeeded |

GORM detects MariaDB and uses `INSERT ... RETURNING id` normally. Those statements
work without a SQL rewrite. Application DELETE and rollback are workload
operations, never restoration of the fixture for the next test.

### Migration blocker diagnosis

These raw `database/sql` queries reproduce the disagreement without GORM:

| Query | Result |
|---|---|
| `SELECT DATABASE()` | `test` |
| `SHOW DATABASES` | Only `information_schema` |
| `SELECT SCHEMA_NAME FROM information_schema.schemata` | Only `information_schema` |
| SCHEMATA with `SCHEMA_NAME='test'` | `test` |
| SCHEMATA with `SCHEMA_NAME LIKE 'test%'` | No rows |
| TABLES with exact schema `test`, table `users`, type `BASE TABLE` | Count 1 |
| `SHOW TABLES` | `addresses`, `users` |

The driver's `Migrator.CurrentDatabase()` first obtains `DATABASE()`, then runs
`SELECT SCHEMA_NAME from Information_schema.SCHEMATA where SCHEMA_NAME LIKE ?
ORDER BY SCHEMA_NAME=? DESC,SCHEMA_NAME limit 1` with `test%` / `test`.
It returns an empty string. `HasTable` consequently searches TABLES with an
empty schema, returns false, and `AutoMigrate` attempts CREATE TABLE again.
Lowercasing Information_schema/SCHEMATA produces the same failure: this is not
a capitalization workaround opportunity or missing table.

**Source fact:** pinned MariaDB `sql/sql_show.cc` routes SCHEMATA through
`fill_schema_schemata` / `make_db_list`. Exact database lookup can use the supplied
name; enumerated/wildcard lookup uses `find_files`, `my_dir` and directory-stat
filtering. This matches the observed split. **Unknown:** which guest filesystem,
directory-stat or enumeration behavior causes the omission. No source patch was
made. Classify this as a mariamem embedded guest metadata compatibility issue,
triggered by an ordinary GORM discovery query, rather than application misuse.
The initial teardown failure was separately a harness error: WaitDisconnected
was called after runtime Close. Waiting is now done only while the runtime lives.

## Disposable isolation

Test A explicitly commits `committed-A` and observes two users. It ends by closing
the pool/runtime, without DELETE, TRUNCATE, schema reset, or cleanup transaction.
Test B receives a new DB, sees the seed user only and cannot find `committed-A`.
This passes twice with Start and twice with Fork. Every case has its own DB;
errors and session state from one case do not affect the next. The compatibility
blocker does not invalidate the successful cleanup-free CRUD observation.

## Pool and lifecycle behavior

Normal `database/sql` defaults remain: unlimited maximum open connections,
default maximum idle pool of two, no wait count in observed runs. Typical cases
use one connection. Holding two `sql.Conn`s opens independent connection IDs
2/3; releasing and reacquiring both returns IDs 3/2 without reopening.

Session variables and temporary tables are independent across physical sessions.
Another connection cannot see an uncommitted insert; rollback leaves no row.
The same reused physical session retains its variable and temporary table after
checkin. This is ordinary MySQL session lifetime, not contamination across DBs;
database/sql return-to-pool is not a complete SQL session reset.

Normal teardown closes the SQL pool, waits for disconnect, then closes mariamem.
The dedicated reverse-order case closes mariamem with one checked-out and one
idle pooled connection. SQL then fails as expected, and closing both handles
succeeds. Every case reports clean runtime shutdown; `ps` finds no remaining
Wasmer child of the test process. Temporary snapshot files disappear on Close.
This is bounded process observation, not an exhaustive resource-leak audit.

## Snapshot/Fork observation

Both lifecycle forms use the same models and committed seed. Fork prepares once,
closes its pool, waits for disconnect, snapshots the consumed template, and forks
one fresh DB per case. This adds snapshot ownership/teardown code but removes
schema/seed setup from individual cases.

| Observation | Start | Fork |
|---|---:|---:|
| Startup + GORM Open median (16 cases each) | 306.8 ms | 306.5 ms |
| Per-case schema/seed setup median | 11.0 ms | Not repeated |
| Eight-case suite wall (two observations) | 3.17 / 3.09 s | 4.06 / 4.06 s |
| One-time template/snapshot work | None | 755 / 823 ms |

Suite wall includes the failing diagnostic case and teardown, but excludes Go
compilation/module download. This order-balanced four-suite compatibility probe
is not a controlled performance study. For this tiny fixture and eight cases,
fresh Start is simpler and faster overall; Fork saves very little repeated setup
and pays substantial one-time work. Nothing here settles its value for larger
schemas, expensive migrations or longer suites.

## Go setup ergonomics

Module installation and `gorm.Open` are ordinary Go usage, but NativeDir setup
is separate. The caller must select/download the platform bundle, extract the
complete manifest/runtime/AOT/sidecar set, and pass its directory in
`mariamem.Options`. A module alone cannot Start the database. This task reused
the prior local test bundle: it did not measure a new user's download effort or
validate a released bundle with the branch fix. Explicit bundle resolution is
a concrete P1 usability candidate; no auto-download feature is implemented here.

## v0.3 findings: next three tasks

1. **BLOCKER:** repair existing-schema discovery in the guest and rerun the
   unchanged migration case. Require SHOW DATABASES, wildcard/equality SCHEMATA,
   HasTable and repeat AutoMigrate to agree; do not replace GORM's migrator.
2. **P1:** improve/document Go native-bundle setup and disposable fixture ownership,
   including pooled session lifetime. Decide its priority from additional dogfood
   evidence; keep zero-setup implementation separate.
3. **P1:** run this consumer on Ubuntu 24.04 and packaged candidates before claiming
   two-platform GORM compatibility. This report establishes only the tested macOS
   configuration, and overall compatibility remains blocked by discovery.

Verification: canonical check (Go tests/vet, Python 326 pass / 3 skipped,
public-source/version checks), real-guest Go race/lifecycle tests and Python
timeout/multi-client tests (3 pass), plus `git diff --check`. The consumer's
expected four failures are retained rather than reported as green. No product
behavior, public API, runtime configuration or session capacity changed.
