# Current wire sufficiency inventory — fixed main source

2026-10-28. Inspected source_commit
`cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`, the adopted main before these
documentation/tooling changes. This is the active source baseline for dogfood
wire checks. The [older inventory](wire-gap-inventory.md) is historical and must
not be read as current Prepared or multiple-result status. No new protocol run,
support expansion or guest generation is claimed by this source reconciliation.

## Actual host/guest surface

[Host dispatch](../../internal/mysqlwire/wire.go) handles QUIT1, INIT_DB2,
QUERY3, PING14, SET_OPTION27 and the Prepared command family22–26. The Prepared
session validates the embedded prepared version/operations before it is usable;
this is engine-backed execution, not placeholder interpolation/emulation.

Base advertised capability bits are
`1|4|8|512|8192|32768|65536|131072|524288`.
This includes MULTI_STATEMENTS and MULTI_RESULTS. PS_MULTI_RESULTS `1<<18` is
added only with validated execution support. TLS, compression, LOCAL_FILES and
DEPRECATE_EOF are not advertised. The greeting uses mysql_native_password;
the current accepted account is local root/empty password. Required SSL requests
are rejected. Do not infer broad authentication/TLS support from a successful
default connection. Capability availability is not proof of every client path.

[Guest text bridge](../../guest/wire_core.inc) drains mysql_next_result and
supports mysql_set_server_option. The resident OPEN path's initial FOUND_ROWS
argument is not evidence that multi-results were removed: host handshake and
COM_SET_OPTION use the option bridge, and engine capabilities retain their own
defaults. [Prepared dispatch](../../internal/mysqlwire/prepared_session.go) and
the resident prepared operations own the actual22–26 lifecycle. The guest still
reports max_sessions16; helper concurrency/pool budgets do not change that ABI.

## Coverage and remaining need-to-confirm paths

| Capability/path | Source-supported status | Existing evidence / detection net | Dogfood obligation |
| --- | --- | --- | --- |
| Text QUERY, schema selection, PING, quit, original errors | Implemented | Existing wire, SQLAlchemy/GORM, Django, migration and Live acceptance | Connect actual P1/G1/D1/EP1/EG1 profiles and retain original errno/SQLSTATE; no new all-client promise |
| Prepared PREPARE/EXECUTE/LONG_DATA/CLOSE/RESET, metadata, binary values and multiple results | Adopted, no longer pending | prepared_session/execute/chain/long_data/failures tests; completed P6 and driver-native records | Reuse fixed accepted controls and verify actual helper driver uses prepared path; retain exact consumer exceptions |
| Text multi-statements/results, CALL chains | Implemented | multi_result_test.go, routine/text runtime owners and adopted acceptance | Verify preparation tool/result draining and subsequent query; do not implement another SQL splitter |
| COM_SET_OPTION27 | Implemented through embedded option API | TestSetOptionValidationMatchesNativeUnknownOption and multiple-result tests | Separate this from session reset; validate selected clients' toggles |
| COM_RESET_CONNECTION31 | No dispatch handler | Default unsupported-command reply; no positive reset acceptance | Inventory whether selected pool reconnect/reset actually requests it; do not equate disconnect, COM_STMT_RESET or Live Reset with this command |
| COM_STMT_FETCH28 / server-side cursors | Not implemented | Public guide explicitly excludes cursors; no positive cursor coverage | Track client demand/default cursor settings; cannot count ordinary prepared SELECT as cursor support |
| TLS, compression, DEPRECATE_EOF and alternate authentication | Not advertised/supported at this boundary | Handshake validation and routing profile refusals, existing auth/readiness controls | Observe actual client flags/config; required-TLS refusal is distinct from transport TLS acceptance |
| LOCAL INFILE exchange | LOCAL_FILES not advertised; no client file-transfer exchange | Source inspection only, no successful LOAD DATA LOCAL evidence | Track loader demand; ordinary SQL-file import is not proof of this exchange or host filesystem access |
| CHANGE_USER17, STATISTICS9, PROCESS_INFO10 | No dispatch handlers | Generic unsupported-command reply, not per-command practical acceptance | Keep named until reach/defer decisions; ORM metadata queries through QUERY are different from PROCESS_INFO |
| Binlog/replication commands18/21/30 and enabling binlog | No streaming dispatch; no adopted binlog feature | Historical source/config investigation, not a CDC campaign | Retain low-priority/watch decision; do not infer support from SHOW syntax or protocol families already implemented |
| Request/result framing and packet/owner limits | Explicit framing and prepared owner checks | Existing malformed packet/metadata/lifetime/quota controls | Keep limits/negative tests visible; a successful small app does not qualify arbitrary payloads |

Concrete named tests include TestPreparedSessionIDsBelongToFinalPhysicalGeneration,
TestPreparedCapabilitiesFollowValidatedExecutionSupport,
TestPreparedClientOUTNegotiationMatchesNativePairedConnections,
TestLongDataNoReplyOwnedMappingDeferredErrorAndReset and
TestMultipleResultStatusAndError. A source/test locator is not a new test PASS.
Root Snapshot consume semantics and Live state changes are separate lifecycle
properties, not evidence that a missing wire command was implemented.

## Reuse of accepted evidence and fresh observation

Prepared completion and adoption are recorded in
[current project status](../project-status.md#prepared-p6-canonical-ownership--complete-adopted-on-main).
[Accepted consumer exceptions](../decisions/prepared-consumer-exceptions.md)
remain: Oracle Connector/Python26.7.0 prepared CALL traversal and the exact Mac
C/default untyped-NUL projection limitation are not rewritten as unconditional
PASS or fixed by silently changing client/SQL. MariaDB Connector/Python replay
and Go prepared paths have their separate bounded evidence. Keep the local
Python3.14/OpenSSL4 import failure distinct from protocol failure.

The [PR3 main receipt](v06x-dogfood-main-completion/README.md) supplies later
native/Django/Live/consumer regression evidence under its actual CI sources;
it is not relabelled as a new wire census at cc00ccd. Tests and capabilities above
were inspected at that fixed main source, which is the baseline of the next
entry acceptance.

For every named entry, retain a driver-operation/capability ledger: intended
operation, connection options, actual command/flag where observed, native result,
guest result, error and cleanup outcome, source/client pin and detecting oracle.
Read-only source observations, captured wire behavior and actual guest/native
execution must have separate statuses. Mark uncaptured paths UNVERIFIED rather
than claiming a full wire trace from application success. Preserve disagreements
and classify wire versus SQL semantics, configuration and client/environment.

No remaining row is automatically approved for implementation or silently removed
because the selected app did not use it. Reach/defer decisions close the coverage
map; the first G1 helper does not close whole-v0.6 wire sufficiency. Prefer the
smallest justified layer change only after a concrete requirement and semantic
comparison; historical host-only guesses are not current architecture decisions.
