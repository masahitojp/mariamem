# P4 LONG_DATA: source candidate, actual guest acceptance pending

Continue the approved [P4 row](v06x-prepared-product-design.md#7-finite-implementation-and-acceptance-plan)
after [both-OS lifetime acceptance](v06x-prepared-p4-lifetime.md). The candidate
adds engine-owned streaming through the public embedded API, current type
omission/precedence, no-response dispatch and reset/close cleanup. Native25-case
capture/replay and focused local units PASS. Actual new guest execution is not
yet verified. This does not close LONG_DATA or P4, authorize main integration,
or start Qualification/release.

## Implementation and primary-source reasoning

Pinned MariaDB83e909fc has the necessary public mysql_stmt_send_long_data API.
It requires a bound string/blob parameter; mysql_stmt_bind_param resets client
long_data_used flags. However, embedded emb_stmt_execute passes client_params
directly, and emb_insert_params/emb_insert_params_with_log check the server's
has_long_data_value before reading an inline value. Thus network-client flag
serialization is not the source of truth for embedded execution. See
[public binding/send API](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c#L2844),
[embedded execute](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc#L337),
and [embedded parameter insertion](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L1187).
Source reasoning establishes this candidate path; actual guest results remain
mandatory and are not substituted by mock tests.

The authored guest creates owned BLOB placeholder bindings before the first
chunk of a batch and calls mysql_stmt_send_long_data for each chunk. Only the
engine accumulates payload bytes. Guest state is one byte per parameter plus
existing owned bindings; Go retains only parameter-presence flags per statement
and a deferred error, not chunk payloads. Transient transport copies still exist;
this is not a zero-copy claim. An empty first chunk is still a real stream.

Go decodes current descriptors normally and omits inline data only for marked
parameters, regardless of the NULL bitmap. It sends typed NULL placeholders in
the existing internal value format, because the embedded engine's stream wins
over the inline binding. Guest validation, count/width/type checks and per-session
handle ownership remain independent. No native pointer or raw MySQL parser is
moved into Go/C twice, and the binary envelope version does not change. Ready/open
explicitly add operation24; the old guest cannot silently claim its support.

Two network/embedded differences are handled in the authored owner, without a
new MariaDB-internal edit:

- Invalid parameter: the public API would reject it immediately; the wire server
  defers1210/HY000 until EXECUTE, repeats that error, and recovers only at RESET.
  Guest and host retain that error, emit no LONG_DATA reply, and never execute SQL
  to discover it. CLOSE releases it as well. Unknown handles and bodies shorter
  than6 wire-body bytes are ignored without a response, as in native controls.
- Invalid stream type: embedded insertion lacks network's is_param_long_data_type
  rejection. Before SQL, the owner rejects numeric/temporal/NULL/DECIMAL/BIT/
  NEWDECIMAL with native1210 and clears the stream via public mysql_stmt_reset.
  BLOB/string aliases accepted by native, including ENUM/SET/GEOMETRY, retain
  their actual descriptors. This is a parameter binding guard, not a SQL retry.
  Source [network type rejection](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L943)
  and [handler classification](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_type.h#L4113)
  are cross-checked with named native cases.

Rebinding before EXECUTE replaces/frees placeholder bindings only after a
successful public bind. RESET, CLOSE and session clear release presence/error
state; partial bind/API/allocation/serialization failure fails closed. The
no-response failure path terminates its session without sending an invented ERR
for the next command to consume. Expected deferred SQL errors remain recoverable;
they do not cause blanket disconnect. Bounded calls keep existing deadlines and
never enable the read-ahead disconnect monitor for LONG_DATA/CLOSE.

The type guard may issue an internal RESET and the public API may elide redundant
zero-length chunks. Internal command counters can therefore differ from direct
network commands; exact diagnostic Com_stmt_* counter parity is not claimed.
Value/metadata/error/status semantics and native live-statement cleanup remain
acceptance targets. Authored protocol-validation errors return their wire
code/state; they do not recreate native engine diagnostic-area entries for
SHOW WARNINGS. The packet matrix does not claim that additional diagnostic
parity. The scope and future guest-update review must retain this
explicit distinction, not silently treat the guard as native engine behavior.

## Finite native matrix and local evidence

The [25-case fixed native oracle](../../tests/fixtures/prepared-long-data-native.json)
and [capture/replay receipt](v06x-prepared-long-data-evidence/receipt.json) preserve
full PREPARE metadata, binary result metadata/rows/status and error packets.
Each case checks the actual12.3.3 version and healthy following SQL; immediate
LONG_DATA→LONG_DATA→EXECUTE, CLOSE→PING and failing-chunk→PING sequences contain
no sleeps. Reference engine is pinned Linux arm64 MariaDB12.3.3 in Docker on
macOS arm64, not a macOS-native server. Final captures fix utf8mb4_general_ci;
the early type lookup used the native default collation and remains a separate
observation, not a differently configured golden packet oracle.

| Group | Controls / native observations |
| --- | --- |
| Exact bytes and precedence |Split embedded-NUL/Unicode across multiple parameters with an inline integer; repeated empty chunks override NULL; ordinary NULL remains NULL afterward|
| Descriptors and ownership |Cached type reuse, subsequent inline execution and type change; two independent statements with interleaved chunks|
| Types |BLOB/VAR_STRING plus VARCHAR/ENUM/SET/all BLOB widths/STRING/GEOMETRY accepted; LONG/NULL/TIME/DECIMAL/BIT/NEWDECIMAL reject1210, following execution recovers|
| Beyond prototype limits |65 parameters with streamed index64;1,400,003 bytes per parameter across three chunks, length and SHA256 checked without a giant result envelope|
| Deferred errors |Out-of-range index gives no immediate response, repeated EXECUTE and a header-only EXECUTE return1210; RESET recovers|
| Engine capacity |Temporarily set native session's inherited max_allowed_packet to4096; two3000-byte chunks give no immediate response; EXECUTE returns1105/HY000, repeats with a valid next binding, RESET recovers; original global limit restored|
| Cleanup/framing |RESET discards chunks while preserving type reuse; CLOSE discards stream; unknown and short chunks leave following PING/SQL healthy|

4096 is a test-controlled engine setting, not a product cap. The bridge adds no
1MiB aggregate limit or second payload accumulator. Existing incoming packet,
response packet and32MiB internal envelope boundaries remain unchanged. The
capacity error stays native1105, not an invented1153. Opaque unknown-handle IDs
are retained with their original packet separately; comparison uses errno/state
there and compares other selected packet fields without rewriting.

Local118 Python/C checks PASS, including normal and ASan/UBSan ownership modes.
The mock API checks owned chunk lifetime, empty streams, invalid-index deferral,
wrong-type non-execution, RESET/CLOSE, failed bind/allocation/send/reset and failed
serialization unwind to zero native handles. These are component proofs, not
actual embedded API or general allocator/race guarantees. Go1.26.8 darwin/arm64
passes -race for preparedproto/mysqlwire/guest; units cover omission versus inline
values, bitmap/type reuse, malformed acknowledgements, no-response monitor
exclusion and absence of an invented error packet after a fatal no-response call.
Canonical inventory PASS applies to the unchanged prior canonical runtime only.

## Generation boundary and next gate

Fixed MariaDB/lite4mariadb/converter13 patches and toolchain are unchanged.
Canonical guest/source.patch and the existing experimental source patch are
unchanged. Changes belong to authored guest includes and the handwritten
protocol/codec owners; generated Go is not edited. New tests are outside the
generated runtime, so no generated HANDWRITTEN_FILES classification changes are
needed. New guest and generated identities are PENDING source CI, not populated
with an old hash. The old e6d6021a whole-body/data/TLS guard deliberately remains
and rejects an unknown new guest.

experiment/prepared-long-data first runs fixed-source guest compilation plus
both-OS units. Its development-runtime job is intentionally SKIP under existing
branch policy. After exact Wasm/function/data/TLS/init binding review and normal
formal generation, prepared-product must pass prior P1/all72 P2/all14 P3/P4
lifetime7 plus these25 LONG_DATA cases on both supported OSes. The appended gate
is already mandatory there; no old gate, native expectation or binding guard is
weakened. A source-only green run cannot close actual LONG_DATA acceptance.

Reproduce native capture/replay:

```sh
mkdir -p build
python tests/v06_prepared_long_data_probe.py --native-port PORT \
  --output build/long-native.json
python tests/v06_prepared_long_data_probe.py --native-port PORT \
  --reference tests/fixtures/prepared-long-data-native.json \
  --output build/long-native-replay.json
```

Use the pinned image, root access in an isolated instance and no competing global
configuration changes. Replace --native-port with --host HOST and set PYTHONPATH
to its formally generated product/python for actual guest acceptance. Required
following steps remain finite: exact new binding and actual both-OS matrix, then
prepared executing-query timeout/cancellation/disconnect and the remaining P4
resource/failure exits. Arbitrary malformed-packet combinations or universal
shared-memory correctness are not proved by this matrix. P5 consumers and P6
canonical/J1/independent generation remain separate, without deferring required
P4 acceptance to Qualification. No main merge, version choice or release occurs.

## Exact binding continuation

Source CI39714836816 passes guest-source and both supported-OS unit jobs at425c821;
development-runtime is skipped by source-branch policy. The [new binding record](v06x-prepared-long-data-binding/reproduce.md)
pins guest f5ce001d and validates complete unchanged lifetime functions/init/TLS,
changed data identities and explicit prior-P3 rejection. Actual LONG_DATA25 and
full regression runtime acceptance remain pending.

## Both-OS runtime gate: metadata mismatch blocks acceptance

CI39718930329 at e5f77f0 compiles/installs and passes previous regressions on
both OSes. LONG_DATA25 individual assertions pass but strict comparison fails
24 cases:91 parameter names per OS differ. [Root cause and repair candidate](v06x-prepared-param-metadata.md)
preserve the oracle and implement engine-owned PREPARE metadata in a separate
source branch. New guest/binding/runtime acceptance is pending; no feature PASS.

## Both-OS LONG_DATA/native metadata development gate closed

[CI39729456821 at fba09f6](v06x-prepared-long-data-pass.md) passes all25
LONG_DATA/native comparisons including the previously wrong parameter names,
plus the previous runtime gates and cleanup controls on both OSes. No oracle
or native fixture was weakened. Full P4 (active-query cancellation/disconnect
and remaining failure/resource paths), P5/P6 and adoption remain unfinished.
