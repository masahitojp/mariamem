# Issue65: direct guest MySQL wire entry feasibility

Source inspection, 2026-11-01. Decision: reject a socket-only addition to the current guest; retain a separate packet-entry experiment as a possible follow-up. This is not proof that every alternative is impossible.

## Conclusion and recommendation

The current embedded guest cannot provide a native MySQL handshake/SELECT1 endpoint merely by adding a relay or changing `--socket`. Its build excludes network startup/accept and the normal server response writers. The generated-Go host also leaves the imported WASIX socket creation/bind operations fail-closed.

A memory packet entry is not present either. Recommend keeping the current product architecture for now. If the value of removing host-side wire implementation justifies a further experiment, first prove one native packet entry independently of the WASIX build, then evaluate the guest/runtime changes. No architectural implementation or integration is approved by this report.

Strongest objection: embedded MariaDB already calls the real command dispatcher, and parts of its binary result representation survive. That may make a targeted bridge smaller than a standalone-server port. However, dispatching a decoded command is not accepting a handshake/packet stream, and the embedded output path does not supply the normal server wire responses. The reuse boundary needs a prototype; existing API execution cannot establish it.

## Fixed inputs and method

- Product `source_commit`: `b3b3b46a8807482ad3f96725af86e031fe369b01` (v0.6.0).
- MariaDB `source_commit`: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` (12.3.3), pinned by `guest/input.json` and `release/inputs.lock.json`.
- Recipe `source_commit`: `24be9371a2f6c71250a2356631ad6feab2280b02` (shyim/lite4mariadb).
- Generated guest identity: `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`, from `release/generated-go-inputs.json`.
- Local inspection: macOS arm64. `scripts/git_identity.py inspect` resolved the product object as a commit before any prospective build.
- Downloaded only 14 pinned upstream files, with URLs, sizes and SHA256 in [the manifest](issue65-guest-wire-evidence/upstream-files.json). All three inspected recipe files match the repository's locked hashes.
- Read the canonical portability/prepared/resident patches and current host overrides as well as upstream sources. They retain the embedded build and do not introduce a packet entry.
- No build, native comparison execution, guest execution, benchmark or heavy CI was performed. No guest patch was changed. `static-findings.json` records source anchors and conditional contexts; it is an inspection aid, not a C preprocessor/build result.

## Decisive evidence

1. The recipe builds `lite4mariadb-wasix` with `EMBEDDED_LIBRARY` and links `mysqlserver`: [recipe CMake](https://github.com/shyim/lite4mariadb/blob/24be9371a2f6c71250a2356631ad6feab2280b02/wasm/CMakeLists.txt#L7). The canonical product patch adds `L4M_RESIDENT` without removing embedded mode: [source.patch](https://github.com/masahitojp/mariamem/blob/b3b3b46a8807482ad3f96725af86e031fe369b01/guest/source.patch#L77). The WASIX configuration explicitly enables the embedded server.
2. Embedded library compilation defines `MYSQL_SERVER` and `EMBEDDED_LIBRARY`: [libmysqld/CMakeLists.txt:17](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/CMakeLists.txt#L17). `lib_sql.cc` includes `sql/mysqld.cc` under that configuration. The embedded branch at mysqld.cc2308 excludes `network_init` at2857; the normal startup call at6367 and accept loop at6783 are also in non-embedded branches. [network setup](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L2308)
3. `mysql_server_init` selects `init_embedded_server`: [libmysql.c:182](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L182). Its init path does not call network startup: [lib_sql.cc:532](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L532). A socket filename argument cannot restore compiled-out code.
4. Embedded `emb_advanced_command` calls `dispatch_command` on an existing THD at lib_sql.cc173. Its `Protocol::write` at1253 and OK response at1305 update embedded result structures; they do not send the normal response packets. Binary results preserve some packet-shaped data, but that does not create a full packet endpoint. [embedded output](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L1253)
5. The standard `Protocol::net_send_ok` and `Protocol::write` are excluded by `#ifndef EMBEDDED_LIBRARY`: [protocol.cc:205](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc#L205), [protocol.cc:823](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc#L823). Merely exposing `dispatch_command` would still leave input framing/authentication and response transport work.
6. The live generated-Go host overrides `Sock_open`, `Sock_bind`, `Sock_connect` and several socket options with explicit panics. The embedded `WasiStubs` type has other socket helpers, but those do not override these concrete host methods: [current overrides](https://github.com/masahitojp/mariamem/blob/b3b3b46a8807482ad3f96725af86e031fe369b01/internal/generatedgo/main.go#L383). Filling these imports alone would not restore MariaDB's excluded listener/writers.
7. The existing TCP listener is the host's own MySQL implementation, not a guest socket: [server.go:94](https://github.com/masahitojp/mariamem/blob/b3b3b46a8807482ad3f96725af86e031fe369b01/internal/host/server.go#L94). Connecting to it would test the current architecture and cannot validate the proposed relay.

PGlite exposes `execProtocolRaw`/stream APIs ([official API](https://pglite.dev/docs/api#execprotocolraw)); this proposal requires an analogous engine-side entry, not just the same TCP wrapper. Its existence is not evidence that embedded MariaDB has that interface.

## Results against Issue65

| Question | Result |
| --- | --- |
| Current guest exposes a usable native MySQL endpoint after init | No endpoint initialization path in the inspected embedded build; not a runtime connectivity test |
| Can host-to-guest relay alone enable handshake/SELECT1? | Rejected for the current build: required server paths are excluded and socket host imports are incomplete |
| Existing raw memory packet API | None identified in the current guest exports/bridge; command dispatch is at a different boundary |
| Handshake / SELECT1 / disconnect via a new entry | NOT_RUN: no candidate endpoint exists to connect to; building one is new prototype work |
| Alternative guest build or patched embedded protocol | UNVERIFIED, not rejected as impossible |

This meets the initial source-inspection exit of identifying the absent entry/build constraints. It does not complete runtime acceptance or establish performance/compatibility of a replacement. No PASS is inferred for either proposal.

## Options and remaining cost

- Keep current host wire path: no migration work; optional command additions continue under their own demand/design decisions (#62).
- Prototype a memory packet entry: native-first, one connection, handshake/COM_QUERY SELECT1/quit. Determine whether normal server response writers and THD/session/auth initialization can coexist with embedded ownership before rebuilding the WASIX guest. A hand-written SQL-to-packet adapter would not prove reuse of MariaDB's native protocol.
- Port a non-embedded server endpoint: includes server build/configuration, guest networking and generated-Go host imports, plus startup/session/cleanup integration. It is not a flag-only change and has a broader affected boundary.

If continued, propose a separate initial two-hour native source/build spike to find the smallest packet-entry boundary and report compile/runtime obstacles. This is a budget proposal, not a promised completion time. A full guest rebuild/regeneration and both-platform product validation would be later costs, not prerequisites retroactively added to this investigation.

Any follow-up must account for session capacity, deadlines/cancellation, client disconnect, no-response command ordering, fatal worker failure and joined cleanup. Snapshot/Fork ownership and Live quiescence/session retirement require explicit mapping; byte forwarding does not preserve those contracts automatically. Existing CI covers the current host protocol, not this absent entry; only a future native/guest packet-level handshake/query/close test could validate it.
