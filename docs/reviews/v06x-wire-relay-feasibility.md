# v0.6 wire-relay feasibility memo (unverified)

2026-10-18. Source basis: `2dc5247`. **Not tested. Not approved.** This records a
question raised in discussion so it is not lost, and states the bounded
investigation that would settle it.

## Question

pgmem relays the real PostgreSQL wire protocol between the client and a real
backend (`cluster.go`), so prepared statements, session state and protocol
coverage come from the engine instead of being reimplemented. mariamem instead
terminates the client protocol in `internal/mysqlwire`, sends SQL through a JSON
bridge to an embedded libmysqld guest, and therefore must implement prepared
statements and every other protocol feature itself.

Can the guest expose a real MySQL endpoint (socket) that the host relays, so
mariamem gets a pgmem-style architecture?

## What is established from source (this is source reading, not a test)

- The guest contains **no socket handling of its own**. The only mention is a
  lite4mariadb recipe context line, `--socket=/tmp/mysql.sock`
  (`guest/source.patch`, argv around line 18). There is no `bind`/`listen`/
  `accept` usage in `guest/*.inc`.
- The guest/host transport is **framed stdout**: `multi_reply`
  (`guest/resident.inc`) writes a 4-byte length plus a JSON envelope, and the
  host reads it in `internal/guest/linked.go` (`Connect` owns in/out streams).
- The host **never dials the guest**. There is no `net.Dial` or unix-socket use
  in `internal/guest` or `internal/host`; the host listens only for clients.
- mariamem connects to the embedded server through the in-process API
  (`mysql_real_connect(NULL, ...)`), not through a socket.
- `l4m_query_v2` (`guest/wire_core.inc`) uses `mysql_real_query` +
  `mysql_store_result`, i.e. text execution inside the same process.
- This question is **not part of the approved prepared spike**. The prepared
  design (`v06x-prepared-design.md`) and the stable-endpoint spike
  (`v06x-kickoff-notes.md` §2) assume the current transport.

## What is unknown (the actual feasibility question)

1. **Does embedded libmysqld listen at all?** `--socket=` may be a vestigial
   argument in embedded mode, or the server may open a socket during
   `mysql_server_init`. Source reading alone does not settle this.
2. **Does WASIX support a socket the host can reach?** The guest is built with
   `wasixcc`; whether `/tmp/mysql.sock` is a real addressable endpoint, and
   whether the host process can dial it (or bridge it to TCP), is untested.
3. **If it works, what happens to host-side control?** Session capacity (16),
   query deadline, disconnect monitoring, no-response command serialization and
   fail-closed behaviour currently live in `internal/mysqlwire`. A relay moves
   them into the server or loses them.

## Proposed bounded investigation

Isolated experiment branch, `guest/experimental.patch` only, fixed inputs, no
main integration:

1. Determine whether the running guest holds a listening endpoint: inspect the
   guest filesystem/socket state after `mysql_server_init`, or attempt an
   in-guest connect and a `SELECT 1` through the socket instead of the embedded
   API. Try server arguments that force networking only if the default is
   clearly off.
2. If the guest listens, prove host-to-guest byte reachability for one
   connection (dial from the host, handshake, `SELECT 1`).
3. If reachable, record what a relay would need for: ≥2 concurrent sessions,
   client authentication, query timeout, client disconnect detection, and
   no-response commands (the four things `internal/mysqlwire` owns today).
4. Record PASS/FAIL/SKIP with the exact guest identity and the reason for any
   SKIP. Native MariaDB 12.3.3 comparison where available.

Exit: a short evidence record that answers questions 1 and 2, plus a list of
what would move if the relay were adopted. No production change, no
qualification, no release claim.

## What changes with the answer

- **Works**: the JSON bridge, the host wire implementation and the prepared
  bridge become optional. Prepared statements, pool reset and multi-statements
  come from the server. Expect a large simplification of `internal/mysqlwire`,
  at the cost of moving session/timeout/limit control to the guest and needing
  a relay layer. This would reopen the prepared design's chosen direction.
- **Does not work**: keep the current architecture; the JSON/binary payload
  question and the prepared bridge remain the path. The alternative (embedded
  internal protocol/packet bridge) stays as noted in the prepared design.

## Cost and status

Estimated at hours to one day plus one guest rebuild; it depends on the guest
build toolchain already working. Not started: this memo is the only artifact.
No runtime, guest, wire, generated source or public contract change is made or
approved by it.
