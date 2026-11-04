# MySQL connection protocol limits

## Unreleased: bounded input pipelining

The local endpoint accepts commands sent before the previous response has been
received. Execution and responses remain serial on each physical connection;
this does not enable concurrent SQL execution or multiple SQL statements in one
command. Existing command, SQL, packet and capability limits still apply.

Pending raw input is limited to **1,048,581 bytes per physical connection**:
the size of one maximum accepted command frame (1MiB SQL budget plus command
byte and four-byte frame header). This is a cumulative byte limit and can hold
several small commands. It is not a command-count limit or an overall RSS limit.
The limit is fixed; there is no new SDK setting.

If additional input exceeds that limit while a query runs, the database instance
is terminated and clients receive a connection-loss error identifying the bounded
receive buffer. Prepare a new independent database after this fatal failure.
Reduce outstanding requests or disable the driver's pipelining for large bursts.
Other physical connections to that same instance are also lost; independent
root databases remain separate.

Disconnect monitoring continues after future input arrives, including when the
buffer is full. Query deadlines and owner shutdown retain their existing abort
behavior. Ordinary SQL errors still return their SQL error and permit subsequent
commands. Each new command is checked against stopping/quiescence admission,
including commands already buffered in memory.

These are endpoint semantics, not a declaration of support for every driver,
ORM, version or arbitrary pipeline depth. The bounded Prisma comparison uses
Node 24.22.1, Prisma/client/official MariaDB adapter 7.10.1 and mariadb 3.5.4.
Its zero-parameter prepared path additionally needs the separate Issue #93 fix;
the last-statement alias is tracked in Issue #95. There is no Node SDK addition.

The [policy decision](decisions/issue94-bounded-pipeline.md) records authorization.
Historical protocol scope and remaining command/capability gaps remain in the
[wire contract](decisions/v060-wire-contract.md).
