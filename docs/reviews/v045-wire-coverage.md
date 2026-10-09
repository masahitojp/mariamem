# v0.4.5 wire coverage migration

The old `tests/integration.py` was not invoked by canonical integration. It mixed
supported wire/session oracles with Wasmer-era external-guest termination and
unsupported hard-containment assumptions. It is retained as historical source,
not blindly enabled or treated as a current gate.

## Canonical ownership

| Invariant in the old investigation | Current owner | Action |
| --- | --- | --- |
| driver parameters, UTF-8/emoji/quotes, binary zero/FF, NULL, decimal, datetime, unsigned maximum | `test_python_wire.py::test_text_protocol_values_metadata_flags_and_error_recovery` + `support/wire_acceptance.py` | restored |
| PING/USE, InnoDB, schema enumeration/wildcards/create/drop | same shared oracle | restored |
| insert ID, row counts, transaction/autocommit status flags, commit/rollback | same shared oracle | restored, supplements ORM/Go behavior |
| errno 1062/1064, multi-statement rejection, duplicate column names, quoted semicolon | same shared oracle | restored |
| column origin/alias/scale/length, warnings, SQL_CALC_FOUND_ROWS, negotiated CLIENT.FOUND_ROWS | same shared oracle | restored; ORM subset is not a replacement |
| 70 KB request/response, 300-row packet sequence wrap, empty-result metadata | same shared oracle | restored |
| unsupported COM_STMT_PREPARE then successful query on the same session | same shared oracle | restored; tests raw protocol command, not just SQL strings |
| 100 queries retain session state | same shared oracle | restored |
| reconnect discards temporary table/session variable/uncommitted update; committed table remains | `test_reconnect_discards_uncommitted_and_session_state[quit/tcp_eof]` | restored for both disconnect paths |
| unsupported host command preserves ready state | `test_unsupported_host_request_preserves_ready_database` | restored |
| idle connection survives query deadline | `test_idle_connection_does_not_expire_at_query_deadline` | restored |
| opaque DB ID; owner EOF exits and wrapper closes handles | `test_owner_eof_reaps_host_and_closes_wrapper` | restored |
| multiple clients/session isolation/capacity | existing `test_python_multiclient.py`, `tests/gointegration/multiclient_test.go` | keep distinct Python/Go boundaries |
| password authentication rejection | existing `tests/godefault/failure_paths_test.go` | keep |
| double Close, guest reaping, wrapper pipe/log/reader cleanup | existing normal Close, owned lifecycle and `tests/snapshots.py`; new owner EOF test | keep layered owners |
| SIGSTOP large write, killed external guest, host SIGTERM bounded containment | historical combined script; current `tests/diagnostics/active_query_close.py` / opt-in forced timeout | not a current guarantee; no PASS claim and no new release gate |
| invalid Wasmer/AOT module override | current generated default/artifact rejection unit tests | old executable-runtime entry is obsolete |
| no full guest race report in old logs | focused handwritten race gate remains; documented full-guest limitation | not equivalent to full guest race-free |

## Execution / evidence

`python scripts/verify.py integration` now invokes `tests/test_python_wire.py`.
The ordinary checkout check skips these opt-in real-host cases. Their owner is
asserted by `test_v04_verification_scope.py`; protocol assertions remain in the
shared helper, preserving the original current-api (`api_version=2`) oracle.

macOS arm64: seven cases executed against a Go1.26.8 current-source host, with
Python3.14.8/PyMySQL1.2.3, PASS in 2.42 seconds (pytest test window, not host build).
The first sandbox attempt could not bind localhost and is not test evidence.
No production Go/Python runtime, guest source or generated source was changed.
No Ubuntu execution is claimed; the maintained integration entry runs these
checks wherever runtime qualification executes, including the future Ubuntu job.
