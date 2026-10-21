# P3 preflight: embedded prepared CALL and OUT

The Human supplied an upstream investigation on2026-10-21. Independent inspection
of MariaDB source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` confirms a public
API/capability/test path. **Actual guest execution is NOT RUN.** This does not close
P3 or change the approved [P1–P6 scope](v06x-prepared-product-design.md).
[Source identities](v06x-prepared-p3-source-evidence/sources.json) record11 fetched
primary files. Product checkout inspected:3c0da63. No guest/converter/generated
source is changed by this note.

## Confirmed source path

- [libmysqld/libmysql.c:4888](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L4888):
  mysql_stmt_next_result calls mysql_next_result, which invokes the methods table
  when MORE_RESULTS exists. On a new result it resets bind_result_done and updates
  field_count. This is an API route, not evidence of successful draining.
- [include/sql_common.h:47–75](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/sql_common.h#L47)
  fixes the MYSQL_METHODS field order. Comparing that order to
  [embedded_methods](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L484)
  confirms next_result uses emb_read_query_result; it is not a missing slot.
- CLIENT_PS_MULTI_RESULTS is1<<18 (262144) and belongs to CLIENT_CAPABILITIES
  ([mysql_com.h](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/mysql_com.h#L246)).
  The supplied sql-common/client.c:2077 reference concerns the network client's
  reply packet. More directly, embedded
  [libmysqld/libmysqld.c:158–174](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysqld.c#L158)
  ORs CLIENT_CAPABILITIES, clears only compression/plugin-auth at that step,
  then calls create_embedded_thd and init_embedded_mysql. In
  [lib_sql.cc:705–720](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L705),
  THD.client_capabilities receives those flags plus extended metadata.
  Thus FOUND_ROWS/0 at this connection call does not by itself disable PS results.
  Runtime instrumentation has not yet confirmed the actual compiled THD flags.
- [protocol.cc:1936](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc#L1936)
  gates binary send_out_parameters on this flag; sql_prepare.cc:5479/5483 selects
  text/binary OUT delivery.
- [test_wl4435_2/3 and WL4435_TEST](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tests/mysql_client_test.c#L1015)
  cover prepared multiple results and OUT binding/fetch/status/next_result.
  [examples/CMakeLists.txt:49–57](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/examples/CMakeLists.txt#L49)
  builds mariadb-client-test-embedded from that source and links mysqlserver.
  Neither continuous upstream CI execution nor success of those cases in this
  WASIX configuration has been established. The test is implementation evidence,
  not a claim of a complete official support specification.

## Small first acceptance case within P3

After the P2 runtime result is assessed, start P3 with one procedure containing
one OUT parameter and two SELECT result sets with distinct metadata/values.
Use the public mysql_stmt_* APIs in an isolated guest-side harness/bridge stage;
the current P2 owner deliberately fails on MORE_RESULTS and cannot serve as a
successful CALL probe unchanged. Keep canonical source.patch/converter inputs
and failure oracles unchanged; never hand-edit generated Go.

Compare to pinned native12.3.3, recording each API stage, return code, errno,
SQLSTATE, metadata, binary row values, warnings and status. In particular:

1. Confirm both ordinary result sets are fetched in order, plus the distinct OUT
   result with SERVER_PS_OUT_PARAMS and expected value. Two SELECTs do not mean
   only two total results. Observe the terminal OK and next_result completion
   separately; compare the complete ordered sequence to native.
2. Rebuild metadata/result bindings for each result, free/drain them, then run
   SELECT1 on the same connection. No silent result/status/error dropping.
3. Record failure stage/errno/SQLSTATE and stop this minimal case on failure.
   Any missing flag/result is FAIL, not an accepted limitation or renamed PASS.

Guest-internal capability and the host's external wire advertisement are
separate. Keep external PS_MULTI_RESULTS unadvertised until the product bridge
and actual guest/native gates support it; internal upstream flags alone do not
justify advertising it.

A minimal PASS permits the existing full P3 matrix:0/1/several/129 results where
native accepts, IN/OUT/INOUT, later errors, changing metadata, following QUERY,
truthful capability negotiation and no pending-result leaks. It cannot replace
that matrix, P2 completion or later P4–P6 gates. This note contains no runtime
PASS/FAIL verdict, new production adoption or release decision.
