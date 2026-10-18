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

## 6. Next steps (v0.6.x, for Human decision)

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
