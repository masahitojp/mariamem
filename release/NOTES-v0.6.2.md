# mariamem v0.6.2 — Driver compatibility and opt-in Go Pipe connections

## Prepared-driver compatibility

- Accept MariaDB's optional boolean new-parameter-bound flag for zero-parameter
  `COM_STMT_EXECUTE`. This fixes the observed prepared `count()` / `findMany()`
  failures from the MariaDB Node driver without accepting malformed extra bytes.
- Resolve MariaDB statement ID `0xFFFFFFFF` to the latest successfully prepared
  statement on that physical connection. `COM_STMT_EXECUTE`, `COM_STMT_RESET`,
  `COM_STMT_CLOSE` and `COM_STMT_SEND_LONG_DATA` use the same owned mapping. A failed/new prepare or closing the
  latest statement cannot silently reuse an older alias.

These fixes address the concrete Prisma/MariaDB-driver failures recorded in
[#93](https://github.com/masahitojp/mariamem/issues/93) and
[#95](https://github.com/masahitojp/mariamem/issues/95). They add no new SQL feature
or general Node/ORM compatibility guarantee.

## Bounded input pipelining

The local MySQL endpoint accepts commands arriving before the previous response
is received. SQL execution and responses remain serial per physical connection;
this enables bounded driver pipelining, not concurrent SQL execution.

Pending raw input is limited to **1,048,581 bytes per physical connection**.
Overflow terminates that database instance, including its other connections;
prepare a fresh independent database after this fatal failure. Query deadlines,
disconnect and owner-stop behavior remain in force after input is queued.
Existing SQL/command limits and unsupported protocol capabilities still apply.
There is no new SDK setting or arbitrary-depth pipeline promise. See the
[protocol guide](../docs/mysql-protocol.md).

## Opt-in same-process Go connections

- `Database.DialContext` can be assigned to the normal MySQL connector's
  `Config.DialFunc`, using `net.Pipe` to reach the existing wire/guest path.
- `mariamemtest.Options{InProcess: true}` selects Pipe for the helper's owned
  preparation and per-test pools. **TCP remains the default**, and the supplied
  DSN remains TCP for external migration commands.
- Local admission at capacity returns a `HostError` matching `ErrCapacity`
  before creating a worker. TCP retains its MySQL1040 response. Closed or
  captured owners match `ErrClosed`; invalidated instances match `ErrUnusable`.
- The callback is bound to its receiving Database and exact endpoint. Close
  client pools before capture/owner teardown; each Fork needs its own connector.
  Existing Snapshot/Fork isolation and cooperative cleanup semantics remain.

Use keyed `mariamemtest.Options` literals: adding the InProcess field breaks old
positional literals. No listener-free startup, Live Pipe API, Python routing
change or automatic Pipe selection is added. See the
[Go guide](../docs/go.md#same-process-connections).

## Configuration guidance and validation scope

A [Node ORM guide](../docs/node-orm.md) records TypeORM's MariaDB dialect and
explicit date convention, plus MikroORM's MariaDB package. It preserves the
bounded evidence and limitations; it is not a new Node SDK or MySQL8 SQL-parity
support claim.

The fixed manual Prisma recheck on main source_commit
`c27061f1a33eed2908fd90b0e2d816692e001339` passed71/71 CLI/Client/Live cases,
including automatic/explicit shadow databases and reset, using Node24.22.1,
Prisma/official adapter7.10.1 and mariadb3.5.4 on macOS arm64.
[Recorded results](https://github.com/masahitojp/mariamem/tree/086036f1e66054ae962146fa0279006d447dad89/docs/reviews/prisma-main-recheck)
are bounded dogfood evidence, not qualification of these final-version artifacts.
Go Pipe adoption has Darwin source/focused-race evidence and Ubuntu source smoke;
its [implementation record](../docs/reviews/issue66-pipe-implementation/README.md)
states the generated-engine race exclusions and remaining limits.

MariaDB remains12.3.3. Python minimum remains3.11 and Go minimum1.26.0; the
canonical build toolchain is Go1.26.10. Supported hosts remain macOS15+ arm64 and
Ubuntu24.04 x86_64. GitHub Release wheels remain the Python distribution channel;
PyPI publication is not added. Existing Django, finite-Fork, prepared-consumer
exceptions and protocol/SQL limitations from
[v0.6.1](NOTES-v0.6.1.md) remain. No general throughput, RSS or resource-reduction
guarantee is made from the lightweight transport measurements.

Release CI owns exact final-version qualification, publication and public smoke.
Preparation or historical/source CI success does not establish release READY.
