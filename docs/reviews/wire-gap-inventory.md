# MySQL wire-protocol practical gap inventory (v0.6.x draft)

2026-10-18. Draft seed for the v0.6.x wire workstream. **No protocol change is
approved or implemented here.** Base: main `4f7b18b` (v0.5.3 release candidate).
Sources are anchored at that commit; dogfood evidence is not yet collected.

## Scope and method

The host wrapper `internal/mysqlwire` ("initial MySQL text protocol") implements
the client-facing MySQL protocol and forwards SQL to the embedded guest through
the guest JSON API. This inventory lists practical gaps and assigns each to an
implementation layer. The open question is how to split the work so that as much
as possible stays host-side without sacrificing required semantics. The Human
subsequently approved Python/Go prepared support as mandatory; the
[implementation comparison](v06x-prepared-design.md) proposes a guest-API spike
because host emulation is not established as equivalent. The Human approved the bounded embedded-API spike on 2026-10-19;
production method adoption remains pending.

## Released baseline state (source-anchored)

- Command dispatch (`internal/mysqlwire/wire.go`): `COM_QUIT(1)`, `COM_INIT_DB(2)`,
  `COM_QUERY(3)`, `COM_PING(14)`; any other command returns
  `ErrorPacket(1235, "42000", "command is not supported")`.
- Advertised capabilities (`internal/mysqlwire/wire.go:21`):
  `1 | 4 | 8 | 512 | 8192 | 32768 | 524288` — text-oriented. The
  multi-statement (`0x10000`), SSL (`0x800`) and compression (`0x20`) flags are
  not among them.
- Public contract (`mariamem.go:21`): text protocol, **not server-side prepared
  statements**.
- Guest JSON API (`guest/wire_core.inc`, `l4m_query_v2`): one
  `mysql_real_query` + one `mysql_store_result` => **single statement, single
  result set**.
- Guest session connect (`guest/resident.inc:77`):
  `found_rows ? CLIENT_FOUND_ROWS : 0`. The resident build drops
  `CLIENT_MULTI_STATEMENTS`, which the lite4mariadb recipe sets by default and
  `guest/source.patch` overrides to `0` under `L4M_RESIDENT`.
- Guest server argv (`guest/source.patch`, on `wasm/lite4mariadb.c`): a hardcoded
  list (`--table-open-cache=32`, `--thread-cache-size=0`, `--socket=...`, plus the
  resident auth-key paths). No `--log-bin`/`--server-id`, so binlog is off even
  though the guest binary contains the binlog code.

## Inventory

| Gap | Current | Who needs it (to confirm by dogfood) | Impact | Layer |
| --- | --- | --- | --- | --- |
| Server-side prepared statements (`COM_STMT_PREPARE/EXECUTE/CLOSE/RESET/SEND_LONG_DATA`) | rejected as "command is not supported" | Go parameterized/Prepare paths without interpolation; Connector/Python `cursor(prepared=True)`; ORM/JDBC use depends on driver and settings | high | host emulation is a candidate requiring semantic proof; guest API if `mysql_stmt_*` is used |
| Multi-statements (`CLIENT_MULTI_STATEMENTS`) | not advertised; resident build overrides the recipe default to `0`; guest API single-result | dump/restore that batches statements per request; some migration tools | medium (restore) | guest API + host (`mysql_next_result`) — or fragile host-side SQL splitting |
| `COM_RESET_CONNECTION` / `COM_SET_OPTION` | rejected | pool reset-on-return | medium | host-only (re-encode over the existing API) |
| `COM_STATISTICS` / `COM_PROCESS_INFO` | rejected | monitoring tools | low | host-only (may need guest status) |
| `COM_CHANGE_USER` | rejected | auth switching | low | host + guest |
| Handshake flags (SSL, compression, `CLIENT_DEPRECATE_EOF`, ...) | not advertised | client connection options | low/medium | host-only |
| Binlog emission | guest code present but off (no `--log-bin` in the argv) | CDC validation, rebuild verification | opt-in cost | guest config (argv patch) |
| `SHOW BINLOG EVENTS` / `SHOW MASTER STATUS` | only if binlog is on; exposed via `COM_QUERY` | SQL-level binlog inspection | opt-in | guest config only |
| Replication stream (`COM_BINLOG_DUMP`, `COM_REGISTER_SLAVE`, GTID) | not implemented | Debezium/Maxwell/canal-style CDC | high effort | guest API + host |

## Layer summary

Follow-up source inspection confirms a concrete Python consumer:
[Connector/Python prepared design requirements](v06x-mysql-workflow-source-review.md#5-python-prepared-statements--design-prerequisite).
Its ordinary prepared execute includes STMT_RESET, and PREPARE expects metadata;
support is not merely replacing SQL placeholders. Pure-Python and C-extension
paths need separate coverage. The host-only labels below describe possible
approaches, not proof of semantic equivalence or approved implementations.

- **host-only** (re-encode over the current single-statement guest API):
  prepared-statement emulation, pool reset, extra SHOW, handshake flags.
- **guest API change** (with host): multi-statements, replication stream. The
  guest JSON API is the real boundary; it currently exposes single-statement,
  single-result.
- **guest config** (argv in `guest/source.patch`): binlog emission, and the
  `SHOW`-based inspection once enabled.

Guest patch provenance: `guest/source.patch` patches both the lite4mariadb recipe
(`wasm/lite4mariadb.c`, `wasm/CMakeLists.txt`) and MariaDB source
(`mysys/my_lib.c`, `storage/innobase/buf/buf0flu.cc`). `guest/input.json` pins
`source_commit` (MariaDB 12.3.3), `recipe_source_commit` (lite4mariadb) and
`portability_source_base`. The hardcoded argv and `CLIENT_MULTI_STATEMENTS` are
lite4mariadb context; mariamem's overrides are the added hunks.

## Next steps (v0.6.x)

1. Dogfood: Django, Alembic/migrations, metadata-heavy and dbt-like workloads,
   retaining the SQLAlchemy/GORM anchors, and record which wire commands/flags
   each client requests (including dump tools such as `mariadb-dump`).
2. Replace the "who needs it" column with observed evidence.
3. Human decision on which commands/flags to implement, keeping the layer split
   above and preferring host-only where the result is equivalent.

The initial inventory was not implementation approval; runtime, guest, generated
sources and public contracts were unchanged at that stage. Follow-up prototype
results below are separate from that released-baseline snapshot.

### Multi-statement precedent (2026-10-19)

The pinned lite4mariadb recipe already provides `l4m_exec_multi` and
CLIENT_MULTI_STATEMENTS; `guest/source.patch` disables that flag in the resident
build; `guest/resident.inc` also opens each worker session without that flag.
Both the worker connection and result API need adaptation. A dump-import bridge
may therefore cost less than prepared support, though
result draining and host/guest semantics remain unverified. This is an independent
import option; prepared remains priority #1 for ordinary Python/Go consumers.


### Bounded prototype results (2026-10-19; not published support)

The Human added multi-statements to the prepared scope; the
[continuation review](v06x-prepared-multi-spike.md) records default Python 3.14 /
Connector 26.7.0 prepared and text multi-result tests, SET_OPTION ON/OFF and
native error-packet comparison. It supersedes the earlier unverified/deferred
status for this bounded investigation, not the released-baseline table above.
Procedure setup is blocked by missing mysql.proc; C-extension syntax reporting
and OpenSSL 4 import remain FAILs. Pool reset is COM_RESET_CONNECTION, distinct
from COM_SET_OPTION. Production coverage, native Ubuntu and adoption remain pending.
