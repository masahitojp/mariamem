# GORM disposable-database dogfood

## Result and scope

Ordinary GORM CRUD works with a disposable mariamem DB per test, without
cleanup SQL or pool restrictions. **32/32 cases now pass**, including repeat
`AutoMigrate`, after fixing generic MariaDB directory enumeration for WASIX.
There is no GORM migrator override, SQL rewrite or disabled integrity check.
The original discovery failure and real-MariaDB comparison are retained below.

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
  `90da311cbcaeec30705a73fe45629c7ede470d1094b3db7ca6e113de294b1d84`.
  The Go host source remains d036296; the guest includes this branch's discovery
  fix. It is not a published/approved release bundle. All recorded prepared-source
  hashes matched a fresh canonical preparation before the incremental local build.

```sh
python3 tests/consumer/run_gorm.py \
  --native-dir build/gorm-dogfood/native \
  --output tests/evidence/gorm-discovery-fixed
```

Supply an existing matching native bundle: this runner never builds/downloads
one. It copies the pinned consumer module into a temporary directory outside
the checkout and uses the remote module without `replace`, with `GOWORK=off`
and Go 1.26.8. Start / Fork / Fork / Start suites each run eight sequential cases.
The A→B pair must remain in order. JSON captures module/native identities,
timings, pool statistics, connection IDs, SQL diagnostics, actual bound GORM
discovery SQL, and cleanup; raw logs and evidence remain ignored under
`tests/evidence/`. Historical failing evidence is in `gorm-dogfood-final/`;
successful evidence is in `gorm-discovery-fixed/`.

## GORM compatibility

Originally each suite passed seven cases and failed existing-schema migration:
28 pass / 4 fail. With the generic discovery fix, all four eight-case suites pass:
**32 pass / 0 fail**.

| Path | Observation |
|---|---|
| Open/version detection; initial AutoMigrate | Passed unchanged; schema, indexes and FK created |
| Create/read/update/delete | Passed; generated IDs, timestamps and nullable field worked |
| Associations | Automatic child insertion, Preload and belongs-to JOIN passed |
| Transactions | Intentional commit persisted inside its DB; explicit rollback removed its own uncommitted write |
| Constraint errors | 1062 unique, 1048 non-null and 1452 FK retained driver error codes; normal queries still worked |
| Repeat AutoMigrate / HasTable | Passed after generic discovery repair; current database is `test` |
| Runtime close with pooled connections | Passed; subsequent SQL failed, pool close and runtime cleanup succeeded |

GORM detects MariaDB and uses `INSERT ... RETURNING id` normally. Those statements
work without a SQL rewrite. Application DELETE and rollback are workload
operations, never restoration of the fixture for the next test.

### Migration blocker diagnosis

These raw `database/sql` queries reproduced the disagreement without GORM:

| Query | Result |
|---|---|
| `SELECT DATABASE()` | `test` |
| `SHOW DATABASES` | Only `information_schema` |
| `SELECT SCHEMA_NAME FROM information_schema.schemata` | Only `information_schema` |
| SCHEMATA with `SCHEMA_NAME='test'` | `test` |
| SCHEMATA with `SCHEMA_NAME LIKE 'test%'` | No rows |
| TABLES with exact schema `test`, table `users`, type `BASE TABLE` | Count 1 |
| `SHOW TABLES` | `addresses`, `users` |

The driver's `Migrator.CurrentDatabase()` first obtains `DATABASE()`. A logger
observer captures the following actual bound discovery SQL without changing it:

```sql
SELECT SCHEMA_NAME from Information_schema.SCHEMATA
where SCHEMA_NAME LIKE 'test%'
ORDER BY SCHEMA_NAME='test' DESC,SCHEMA_NAME limit 1
```

Before the fix this returned an empty string. `HasTable` consequently searched
TABLES with an empty schema, returned false, and AutoMigrate attempted CREATE
TABLE again.
Lowercasing Information_schema/SCHEMATA produces the same failure: this is not
a capitalization workaround opportunity or missing table.

**Source fact:** pinned MariaDB `sql/sql_show.cc` routes SCHEMATA through
`fill_schema_schemata` / `make_db_list`. Exact database lookup can use the supplied
name; enumerated/wildcard lookup uses `find_files`, `my_dir` and directory-stat
filtering. The failing condition is in `mysys/my_lib.c`: with `MY_WANT_STAT`,
`my_dir` discards every entry without `MY_S_IREAD` in `st_mode`.

**Measured runtime fact:** a minimal diagnostic compiled with the same WASIXCC
0.4.7 and executed by Wasmer 7.4.2 creates `/mariadb/test`, then returns:
`stat=0 mode=40000 type_dir=1 user_read=0 access_read=0`. Readdir finds `test`.
WASIX reports the directory type without POSIX permission bits; the native
permission-bit test therefore silently discarded a readable database directory.

**Real MariaDB comparison:** official local image `mariadb:12.3`, digest
`sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`,
reports `12.3.3-MariaDB-ubu2404`. In a disposable container with a real `test`
database/table, the exact GORM query returns `test`; SHOW DATABASES and unfiltered
SCHEMATA also include it, and the exact TABLES query returns count 1. This is not
the same server version as embedded 13.1.0; the comparison establishes the
expected discovery semantics, not complete cross-version equivalence. The native
server also contains system databases absent from this embedded configuration.

**Generic repair:** only the `__wasi__` branch of `my_dir` checks successful stat
and `access(path, R_OK)` instead of testing unavailable POSIX read bits. Stat or
access failure still excludes the entry; file type remains checked by MariaDB's
normal caller. Native builds keep their previous branch. There is no fabricated
schema list, GORM query interception, authentication/grant change or runtime
redesign. The canonical patch and pristine hash of `mysys/my_lib.c` are recorded
in source preparation/provenance. Generic wire tests cover SHOW DATABASES,
SCHEMATA enumeration/wildcard lookup and database CREATE/DROP visibility.

One previously unreachable assertion was a harness error: it queried
`HasConstraint(&Address{}, "User")`. The FK created by User.Addresses is named
`fk_users_addresses`; the inverse relation name is not that constraint name.
Normal MariaDB also returns 0 for constraint name `User` and 1 for the actual FK.
The test now checks that existing FK by its correct name, without changing GORM's
model/migration or database semantics.

The initial teardown failure was separately a harness error: WaitDisconnected
was called after runtime Close. Waiting is now done only while the runtime lives.

## Disposable isolation

Test A explicitly commits `committed-A` and observes two users. It ends by closing
the pool/runtime, without DELETE, TRUNCATE, schema reset, or cleanup transaction.
Test B receives a new DB, sees the seed user only and cannot find `committed-A`.
This passes twice with Start and twice with Fork. Every case has its own DB;
errors and session state from one case do not affect the next. The original
blocker did not invalidate the successful cleanup-free CRUD observation.

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

Historical pre-discovery-fix observations (the original 28/32 run):

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

The schema-discovery **BLOCKER is resolved on this branch**. The remaining tasks:

1. **P1:** run the unchanged consumer on Ubuntu 24.04 and packaged candidates
   before claiming two-platform GORM compatibility. This is macOS local acceptance.
2. **P1:** improve/document Go native-bundle setup and disposable fixture ownership,
   including pooled session lifetime. Decide its priority from additional dogfood
   evidence; keep zero-setup implementation separate.
3. **NICE TO HAVE:** repeat with a larger realistic migration/fixture workload
   before drawing broader conclusions about Snapshot/Fork ergonomics or payoff.

Verification: canonical check (Go tests/vet, Python 326 pass / 3 skipped,
public-source/version checks), real-guest Go race/lifecycle tests and Python
timeout/multi-client tests (3 pass), raw wire acceptance including generic
discovery and FOUND_ROWS, SQLAlchemy standard consumer (44 pass), canonical
source preparation/hash checks and `git diff --check`. Current GORM acceptance
is 32/32; historical failures remain separate. The repair restores database
discovery semantics; public API, runtime configuration and session capacity stay
unchanged.

## Follow-up cross-platform acceptance

The earlier local-only observations above are historical. GORM passed
32/32 on clean macOS 15 arm64 and Ubuntu 24.04 x86_64 in
[run 36582171063](https://github.com/masahitojp/mariamem/actions/runs/36582171063),
source `872fdea882ad82540ffe32e14e506ff67b2d10c3`, without framework-specific
workarounds. Committed CRUD isolation, normal pools and lifecycle cleanup passed
on both platforms. See [v0.3 acceptance](v03-acceptance.md) for artifact identity,
related regression checks and the dedicated audit-readiness conclusion.
This closes the two-platform dogfood acceptance gap; it does not broaden the
supported framework/version matrix or establish a Snapshot/Fork speed advantage.
