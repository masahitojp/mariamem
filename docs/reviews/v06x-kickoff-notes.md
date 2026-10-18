# v0.6.x kickoff notes — wire, fixture UX, dump/binlog

2026-10-18. Consolidated discovery notes from the v0.6 planning discussion.
Draft seed; **no runtime, wire, guest or protocol change is approved**. Main is
untouched (a v0.5.3 release is in progress). Companion: `wire-gap-inventory.md`
(same branch) plus the accepted 0.5.x records
(`child-lifecycle-attribution.md`, `ubuntu-parallel-startup-results.md`).

## 1. Wire protocol

See `wire-gap-inventory.md` for the source-anchored table. Summary:

- The host wrapper `internal/mysqlwire` supports only `COM_QUERY`, `COM_INIT_DB`,
  `COM_PING`, `COM_QUIT`; every other command returns
  `ErrorPacket(1235, "command is not supported")`.
- Server-side prepared statements (`COM_STMT_*`) are not supported (text
  protocol only).
- `CLIENT_MULTI_STATEMENTS` is set by the lite4mariadb recipe, but mariamem's
  resident patch overrides it to `0`. A dump sent as a single multi-statement
  query therefore fails. The guest JSON API (`l4m_query_v2`) is single-statement,
  single-result.
- Other gaps: `COM_RESET_CONNECTION`/`COM_SET_OPTION`, handshake flags
  (SSL/compression/`CLIENT_DEPRECATE_EOF`), monitoring commands, `COM_CHANGE_USER`.
- binlog emission (guest config; code present but off) and replication streaming
  (`COM_BINLOG_DUMP`; guest API + host).

Layer split that the v0.6 work should preserve:

- **host-only** (re-encode over the existing single-statement API): prepared
  statement emulation, pool reset, extra `SHOW`, handshake flags.
- **guest API change** (with host): multi-statements, replication stream.
- **guest config** (argv in `guest/source.patch`): binlog emission.

## 2. Fixture / test UX

Current mariamem:

- Python: `pytest_plugin.py` provides `mariamem_server`, `mariamem_snapshot`,
  `mariamem_fork`, `mariamem_connection_info` (inspired by `shibukawa/pgmem`).
- Go: manual `Start → Snapshot → Fork` with `ConnectionInfo()`/`DSN()`.

Friction points observed from the API:

- pool lifecycle order (`close pool → wait_disconnected → fork.close`) is
  user-managed and easy to get wrong;
- no first-class prepare hook (the user runs migrations/seed between
  `mariamem_server` and `mariamem_snapshot`);
- dump loading is manual;
- no Go test helper;
- the text-protocol constraint (no server-side prepared statements) is easy to
  violate from an ORM/driver.

pgmem (read-only peek at `a61005d`, not a pinned review) has a much richer test
integration:

- `@shadow_pg(fork=True, prepare=False, live=False)` decorator/marker.
- Driver monkeypatching (`packages/python/src/pgmem/_shadow.py`) routes new
  psycopg/psycopg2/asyncpg/SQLAlchemy connections to a prepared fork **without
  changing the application's config or DSN**; the SQLAlchemy pool guard rejects
  pooled connections from another test fork.
- `live=True`: a stable endpoint reset in place before each test (for
  long-lived HTTP apps), with `LiveBaseline.capture()` to keep migrations the
  app ran at startup.
- `reset` restores a fork to a snapshot while **keeping the port and client
  connections** (`docs/subprocess.md`).
- `pgmemtest.ShadowPG(t)` (Prisma's shadow database) is a separate feature.

Candidate mariamem v0.6 UX items:

- **cheap, plugin-only**: a `shadow_mariamem`-style driver routing to a fork
  (PyMySQL/SQLAlchemy/Go mysql), a Go `mariamemtest` helper with `t.Cleanup`, a
  `prepare` hook, an env/DSN helper.
- **architectural / verification theme**: stable endpoint + in-place reset (see
  below). This needs a relay/session layer and changes the current "Fork = new
  endpoint / Snapshot consumes source" contract → separate design decision.

### Verification theme (spike): stable endpoint + in-place reset

Hypothesis to test, **not an approved implementation**. Today every database owns
an ephemeral listener (`internal/host/server.go`, `net.Listen("tcp4",
"127.0.0.1:0")`), `Fork` creates a new endpoint, and `Snapshot` consumes its
source. A "live" endpoint would keep the listener/port and client sockets while
the guest backend is re-materialized from a baseline.

Bounded questions to resolve before any implementation:

1. Can a running `Server` restart its guest in place from the same baseline
   (`stored.Owned` / `restore.Acquire`) without changing the listener or port?
2. Can `clients`/`slots` and `internal/mysqlwire` session state survive the
   backend swap, and what is the correct behavior for an open transaction
   (`busy`/wait) and for sessions from the previous backend?
3. Does the Python shared host (one host, multiple databases) fit a per-DB relay,
   or does the current one-guest-per-database assumption block it?
4. Is a wire session reset (`COM_RESET_CONNECTION`) needed, or can the relay
   present a fresh session without it?
5. Does this need any guest change? Expectation: none (the guest restarts like a
   Fork), but confirm.

Exit conditions: a bounded spike on a pinned commit that demonstrates or refutes
in-place restart on a stable endpoint, with the invariants above stated. Any
implementation, and whether HTTP-app `live=True` is worth it, is a separate
Human decision. The cheaper driver-routing path above is independent and does not
need this.

## 3. Dump / restore as fixture preparation

- "Load a dump into a fresh DB → Snapshot → Fork" fits the existing
  prepare-once model and is largely possible today with a stock client
  (`mariadb < dump.sql`, one statement per query).
- The multi-statement failure is the resident override above; do not send a whole
  dump as one query. `--single-transaction --master-data` needs binlog.
- Candidate: a documented/helper path plus a dogfood scenario ("prepare from an
  existing dump"). It is a fixture-ergonomics item, not a wire priority.

## 4. binlog / CDC and the layer split

- binlog is **file-based**, not a table; the guest binary contains the code but
  it is off (no `--log-bin` in the hardcoded server argv).
- Enabling it is a guest argv patch → guest patch maintenance; keep it opt-in.
- `SHOW BINLOG EVENTS`/`SHOW MASTER STATUS` are `COM_QUERY` (host-only exposure).
- CDC streaming needs `COM_BINLOG_DUMP` (guest API + host).

## 5. Guest patch provenance (maintenance)

- `guest/source.patch` patches both the lite4mariadb recipe
  (`wasm/lite4mariadb.c`, `wasm/CMakeLists.txt`) and MariaDB source
  (`mysys/my_lib.c`, `storage/innobase/buf/buf0flu.cc`).
- The hardcoded server argv and `CLIENT_MULTI_STATEMENTS` are lite4mariadb
  context; mariamem's overrides are the added hunks (`L4M_RESIDENT`).
- Keep the "minimize guest patches" preference: prefer host-only wire work and
  config/host levers before guest changes.

## 6. Additional scope candidates (perspective scan)

Gaps seen from a product/test-UX perspective, beyond wire / fixture UX / dump,
binlog / stable endpoint above. Candidates for Human decision, **not approved**.

1. **Parallel resource safety (highest safety priority).** There is no fork/DB
   count cap; at ~240–320 MiB per DB, 16 parallel databases is ~4–5 GiB, an OOM
   risk on CI. pgmem derives `MaxForks` from memory. Add a fork/concurrency budget
   (cap plus guidance) and document worker/memory totals. Evidence: the per-DB
   incremental memory in `benchmarks/memory-session-envelope.md`; current
   `max_sessions=16` per DB and no cap in `internal/host` or the public API.
2. **Framework integration layer, not just measurement.** Dogfood should decide
   whether per-framework adapters/fixtures are deliverables with correct
   semantics: Django test runner (test DB, transaction wrapping, flush, migrate),
   Alembic apply/shadow, SQLAlchemy pool reset, dbt.
3. **Driver/auth/TLS compatibility matrix.** Text protocol only means
   prepared-statement-default drivers (Go `interpolateParams=false`, MySQL
   Connector, JDBC, Node mysql2) hang or fail. Also root/no-password, no TLS,
   `caching_sha2_password` key paths, `SET NAMES utf8mb4`, default collation.
   Produce a compatibility table with required settings before adding wire
   commands.
4. **Cross-run baseline cache decision.** Large fixtures are re-prepared per
   session/worker (100 MiB seed ~35 s); mariamem removed save/load, so there is
   no cross-run cache. Decide opt-in cache vs no-cache and record the trust
   rationale.
5. **Failure / observability UX.** Make SQL error / `busy` / timeout /
   non-cooperative termination visible, and add a fixture that fails teardown on
   an unclosed DB/handle. `Database.Logs()` exists but has no test-level
   assertion.
6. **Bulk data load.** `LOAD DATA LOCAL INFILE` uses a special protocol (a wire
   gap); CSV bulk load would speed up 100 MiB preparation.
7. **Language coverage (likely beyond v0.6).** Only Go and Python today; pgmem
   ships Java (JUnit5/Spring/Micronaut) and Node. Note as a strategic direction
   if JVM/TS test suites are in the target market.

Suggested v0.6 subset: 1 (safety), 3 (driver matrix), 2 (framework adapters),
5 (failure/observability), 4 (cache decision). 6 and 7 can follow.

## 7. Strategy note: pgmem as a matched floor reference

Now that the non-guest layers are largely eliminated (OS check cached, native
bundle resolve removed, Snapshot content scan removed in v0.5.2, transport and
session handling small), the remaining target is guest MariaDB re-initialization
plus parallel startup contention. That is where pgmem becomes a meaningful
reference — as a **floor**, not a target.

Preconditions before any speed tuning against pgmem:

1. **Matched measurement.** The current numbers do not reconcile: mariamem's own
   attribution puts Fork at ~54–65 ms and DB Close at ~2.5–4.9 ms (macOS M1,
   post-ownership), while the external pgmem comparison put mariamem child Fork at
   ~502 ms and Close at ~63 ms (Intel). The difference is boundary/cohort, not a
   regression. Define one matched benchmark (same harness, boundary, machine,
   workload) before trying to "close the gap".
2. **Engine difference.** pgmem is Postgres/PGlite; mariamem is MariaDB 12.3.3
   (guest init alone is 34–61 ms). pgmem's cheaper fork is plausibly engine
   weight, not a copyable trick; the pgmem review also found that pgmem does not
   clone runtime state.

Levers, in order:

- reduce guest init work (collation / InnoDB page / memory EA); config/host first,
  minimal guest patch only where a concrete saving is demonstrated;
- hide it (pre-warm pool); the 4-parallel suite already wins ~51% wall;
- avoid it (clone an initialized state); highest payoff, hardest, and not done by
  pgmem either — a research theme, not a task.

Positioning: use pgmem as a floor reference for what is achievable, with the
engine difference stated, and decide the guest-init investment from a matched
benchmark. Suggested arc: **v0.6 = UX/wire** so the disposable DB is a tool users
can trust; **v0.7 = guest init plus 100 MiB large-scale tuning**, with the matched
pgmem baseline as the investment input.

## 8. Inspiration: moto's shadow pattern ("moto for MariaDB")

The pgmem author states (Future Tech Blog, 2026-10-15,
<https://future-architect.github.io/articles/20261015a/>) that `@shadow_pg` /
`fx.ShadowPG` / `@ShadowPg` were inspired by **moto's `@mock_aws`**: a decorator
that redirects an SDK to a local emulator **without changing application code or
endpoints**. pgmem applies that pattern to PostgreSQL drivers; it also ships the
same decorator per language (Go/Python/Java).

Product framing for mariamem: a real MariaDB as a **test double (fake)** with the
same "redirect the driver, change nothing" ergonomics — **"moto for MariaDB"**.
The value is the decorator (transparent routing), not only a faster database, so
the v0.6 fixture UX should be framed around that. The per-language decorator is
also a useful model for the language-coverage discussion (item 7 above).

Lineage: pgmem (PGLite) and mariamem (`lite4mariadb` recipe) both use the
`wasm2go` converter. pgmem forks the whole initialized storage (a VFS copy, not a
runtime-state clone), consistent with the pgmem VFS review.

## 9. Next steps (v0.6.x, for Human decision)

1. Dogfood (Django, Alembic/migrations, metadata-heavy, dbt-like; retain the
   SQLAlchemy/GORM anchors) and record which wire commands/flags each client
   requests, including dump tools. Include a "prepare from dump" scenario.
2. Bounded pgmem re-review at a pinned SHA (`a61005d`) covering `shadow_pg`,
   `reset` (stable endpoint), `pgmemtest` and driver routing.
3. Human decision on: which wire commands to implement, which fixture-UX helpers
   to add, and whether the stable-endpoint reset is in scope.
4. Resolve the stable-endpoint verification theme (spike) before deciding whether
   HTTP-app `live=True` is in scope.

Draft only. No runtime, wire, guest, generated source or public contract changes.
