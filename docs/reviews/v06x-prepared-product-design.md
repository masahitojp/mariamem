# Prepared statements product design — Human Review

2026-10-20. **Decision now: approve implementation of this production candidate,
not main adoption or release. Recommendation: proceed with the public embedded
mysql_stmt API bridge, replacing the prototype's fixed arrays/limits and binary
codec.** Existing Python/Go code can retain real prepared execution; the engine
continues to parse, bind and execute it. Text multiple results, routines and
COM_SET_OPTION already adopted on main are prerequisites to preserve, not work
to repeat.

The strongest objection is that the old spike established feasibility, not a
production codec: temporal values, untruncated results, prepared CALL result
chains and several error/lifetime cases are unfinished. The public embedded API
exists for these operations, but actual guest behavior still needs the finite
acceptance below. Approve staged implementation with explicit stop conditions;
do not adopt the prototype's limits or substitute text interpolation. The
Connector C-extension error exception proposed below remains a separate adoption
disposition; implementation approval does not silently accept that exception.

## 1. Basis and current state

Design source_commit: `22a8c64305e706408ebcd54cfd7ecc45426802ad` (current main at
start). The routine candidate's both-OS evidence is for03184a6, not new prepared
code. This task changes design/status documents only: no runtime, build, protocol
experiment or consumer test was added or executed.

Cross-check basis:

- [North star](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven),
  [capability map](v06x-capability-map.md), [workflow options](v06x-workflow-design-options.md)
  and [MySQL consumer findings](v06x-mysql-workflow-source-review.md).
- [Original prepared design/acceptance](v06x-prepared-design.md),
  [Snapshot lifecycle/ownership](../decisions/snapshot-product-contract.md),
  [adopted routine scope](../decisions/routine-support-scope.md) and
  [canonical candidate review](routine-canonical-ci-review.md).
- Historical [prepared + multi spike at9250ff5](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-prepared-multi-spike.md),
  especially its **Conditions for production and review limits**. Guest source
  926365bdc853bd2a45cc00139db1b64c5d78e3e9 / tested host
  7037f05bb279de4ce7aab622e33b13e20d7c52f0 are feasibility inputs, not current
  canonical runtime. The later routine experiment includes that prototype but
  its whole branch is not an adoption unit.

| Boundary | Established | Remaining |
| --- | --- | --- |
| Go DB/Tx/Conn explicit Prepare and non-interpolated implicit execution | Spike PASS | Product ownership, extended matrix and both-OS native controls |
| Python26.7.0 pure / C extension prepared | Successful cases on Python3.14; default multi refusal resolved | Extended types/lifecycle; named error/import differences below |
| mysql_stmt_param_metadata | Always NULL in pinned embedded implementation | Preserve native PREPARE descriptors from proven profile, broaden equivalence cases |
| Text CALL / multiple results / option toggling / routine schema | Adopted on main | Binary prepared CALL and its result draining remain unverified |
| Large results and typed output | Prototype only | Replace4KiB cells /1,024 rows /64 counts and incomplete result codec |
| Canonical prepared generation / provenance | Not adopted | New owner changes, same-input builds, independent generation, source/license/J1 gates |

The old report's "mysql.proc absent" gap is closed for **current main**, without
rewriting the old FAIL. It does not establish prepared CALL support.

## 2. Proposed product scope

**IN:** COM_STMT_PREPARE(22), EXECUTE(23), SEND_LONG_DATA(24), CLOSE(25), RESET(26);
actual server-owned statements for Go DB/Tx/Conn and Python
`cursor(prepared=True)`, including default Connector connection behavior; prepared
SELECT/DML, transactions, repeated executions, metadata/schema reprepare, large
values within the existing transport/resource contract, and procedures/functions
including prepared CALL multiple results and OUT/INOUT behavior. Keep text
COM_QUERY/INIT_DB/PING/QUIT and existing COM_SET_OPTION unchanged.

The word "cursor" in Python `prepared=True` does **not** itself mean a MySQL
server-side cursor. Proposed OUT for this first production candidate:
server-side cursor flags / COM_STMT_FETCH(28), optional query-attribute protocol,
new authentication/TLS modes, COM_RESET_CONNECTION(31), general dump import,
new public APIs/options, new platform/Go minima, guest/converter upgrades, packages
and events. Do not advertise unsupported capabilities. If ordinary pinned Go or
Python prepared use actually requires an excluded path, that is a scope blocker;
ask for a changed scope instead of requiring application workarounds.

Prepared CALL is deliberately IN rather than silently excluded after routine
adoption. A stored routine's normal SQL rules remain engine-owned; this does not
turn multi-statement text into several prepared statements. PREPARE of a batch
must follow the native engine's acceptance/error behavior.

## 3. Owners and internal boundary

### Wire/host

`internal/mysqlwire` owns packet framing, validation, statement IDs visible to
that TCP session, type-descriptor reuse, binary row encoding and capabilities.
Prefer focused prepared decoder/encoder/state files over copying
prepared_spike.go. Validate lengths/counts using overflow-safe arithmetic before
allocation or guest dispatch. Keep complete packets and unknown/malformed input
behavior under tests; do not route all errors through a fabricated generic OK.

A wire statement maps to a guest handle and physical-session generation. Two
sessions may legally have the same numeric wire statement ID; isolation means
an ID resolves only in its owning session, not global numeric uniqueness. A Go
logical DB Stmt may prepare separately on several physical pool connections.
Close/reconnect/slot reuse invalidate old mappings and caches. There are no
cross-session or cross-Fork statement handles.

### Guest/engine

Use public mysql_stmt_* APIs. Engine owns prepare/execute/SQL errors, transaction
state, reprepare and actual data conversion. New authored
`guest/prepared_api.inc` is the proposed owner, copied and hashed by
`scripts/prepare_guest.py` and included in wire_api.inc **after wire_core and
before resident**. This can use the recipe's existing MYSQL/buffer definitions
and worker MYSQL without the prototype's insertion into lite4mariadb.c. That is
a proposed smaller ownership route, not an already compiled result. If compilation
requires an upstream edit, expose the exact preimage/patch/maintenance cost before
adoption; do not hide it in preparation or change MariaDB internals silently.

The current resident reserves guest opcode4 for text SET_OPTION; the prototype
uses4 for all prepared commands. **Do not copy that dispatch.** Propose dedicated
opcode5 for a versioned prepared request and matching response, keeping opcodes1–4
and text api_version2 unchanged. Ready/response metadata must explicitly bind
prepared schema version1 and supported features; mismatch fails closed before
use. Public MySQL wire version/capability negotiation is a separate boundary.

Use a small versioned binary request envelope (operation, session-owned handle, lengths, NULL,
type/unsigned descriptors and exact value bytes), rather than letting native C
pointers or JSON numbers cross the boundary. Wire decoding stays in the host;
the guest independently validates its own envelope, counts, ownership and byte
ranges. Keep responses in the existing framed JSON family, with an explicit
prepared schema and exact typed value bytes/hex instead of decimal JSON numbers. Descriptor reuse is decoded into explicit current bindings before the
engine call. Do not duplicate incompatible wire parsers in host and guest.

Dynamic statement/parameter/result buffers replace PST_LIMIT arrays. Buffers and
metadata have one owner, with unwind paths for allocation/bind/fetch/serialization
failures. Dispose all native statements before mysql_close/worker reuse. Host
maps, guest bindings and pending long data must be released on all exits.

## 4. Types, results and capacity

### Exact values

- Integers retain requested width, sign and unsigned64 range; no float64 JSON
  number round trip. Floating results use typed native bindings and explicit
  binary bytes, not the prototype's BLOB→decimal text→Go ParseFloat path.
- DECIMAL retains exact decimal bytes/scale; binary/text/BLOB retain byte lengths,
  embedded NUL, empty versus NULL and charset/flags. BIT/ENUM/SET/JSON/spatial
  forms must follow the native field type actually exposed, not a guessed
  application type. Named cases, not a claim of every MySQL extension.
- DATE/DATETIME/TIMESTAMP/TIME parameters/results include fractional seconds,
  zero dates, negative and >24h TIME and native error cases under the same SQL
  mode/timezone. Use public MYSQL_TIME components where required; do not turn
  SQL values into host-local time or normalize invalid native cases into success.
- Null bitmaps, type reuse without new descriptors, no/zero parameters, metadata,
  original/table names, charset, signedness, warnings, affected rows, insert IDs,
  server status and terminal errors are part of the result contract.

Native result binding chooses exact numeric/temporal representations and exact
variable-length bytes. On MYSQL_DATA_TRUNCATED, obtain the actual length and
fetch the complete variable-length value with mysql_stmt_fetch_column using
checked allocation; never return a shortened cell as success. Engine/API failure
remains an error, not an excuse to convert every result to strings.

Prepared chains advance with mysql_stmt_next_result and rebuild each result's
metadata/bindings. Encode binary rows and MORE_RESULTS in order, retain terminal
OK/OUT-parameter status and later errors, and drain/free each result. A following
query must remain usable after a recoverable SQL error. Advertise PS_MULTI_RESULTS
only with that implementation and passing actual guest/native cases. Public API
source establishes a candidate path, **not** guest execution of it.

### No silent prototype limits

Do not promote64 statements/parameters/columns,4,096-byte cells,1,024 rows,1MiB
aggregate long data or128-result chains into product limits. No particular row
count is a correctness limit. Capacity tests cross each old threshold, subject
to applicable native/protocol limits; failures must be explicit, not truncation.

This is not an unlimited-capacity promise. Current wire.read caps an incoming
packet at1,048,577 bytes; response send uses maxPacket=0xffffff−1; internal guest
responses are capped at32MiB. Preserve these boundaries in this task; MySQL packet
continuation/streaming and raising these limits are not bundled improvements.
Account for encoded-envelope overhead (including hex expansion) before an
internal frame becomes oversized. Large result tests must fit the actual envelope;
do not present raw-byte sizes as the serialized size.

Use the engine's max_prepared_stmt_count/native allocation limits rather than an
extra unexplained count64. LONG_DATA chunks use the engine API and its packet/
resource handling rather than retaining a second unbounded host/guest accumulator.
Compare aggregate overflow/error timing with native, including a later EXECUTE.
For errors with possible completed DML, preserve the existing invalidation rule
and never imply retry is safe. If the existing framing cannot report a failure
without losing framing/session state, fail closed; do not silently raise limits.
Any additional product cap needs its value, unit, scope, release behavior and
Human approval before adoption, rather than being selected inside the code.

## 5. Lifecycle, errors and no-response commands

| Event | Required behavior / evidence |
| --- | --- |
| Prepare fails / quota / allocation failure | No leaked native handle or half-installed host mapping; preserve native errno/SQLSTATE when available |
| EXECUTE repeated / type changes / schema changes | Current descriptors and newly returned metadata used; engine-owned reprepare compared to native, no stale output shape |
| RESET | Compare parameter/type/long-data/pending-result lifetime to native; do not confuse it with session reset or rollback |
| CLOSE / SEND_LONG_DATA | No client response. Serialize an internal ack, then process the next client command; never let callGuest read-ahead consume it |
| Unknown/stale handle / malformed command | Compare response vs no-response and connection health with native; preserve legitimate following commands. Prototype's blanket disconnect for failed no-response commands is not adopted |
| LONG_DATA failure | Native-equivalent deferred error/cleanup behavior must be established; no invented wire acknowledgement or silently dropped chunk |
| Timeout / cancellation / disconnect while executing | Preserve current DB invalidation/cleanup contract, pool rejection and error context; forced noncooperative-worker reclamation is not promised |
| Idle disconnect / connection Close / slot reuse | Close statements, result bindings and long data; no leak or handle resurrection |
| Snapshot / Fork | Existing disconnected/busy/transaction checks apply. SQL definitions/data survive; statement handles, cursors and connections do not. Independent children cannot share mutable statement state |

No-response dispatch requires a context/deadline and bounded queueing, not an
uninterruptible call or an unbounded packet stash. Test immediate CLOSE→QUERY,
LONG_DATA→LONG_DATA→EXECUTE and failed-command→PING/QUERY sequences without adding
sleeps to make framing accidentally work. Maintain current host failure and
connection-initialization semantics throughout.

## 6. Consumer differences requiring an explicit disposition

### C extension syntax error

The old expected1064 oracle **remains FAIL** for Connector/Python26.7.0 C-extension
prepared syntax errors: both guest and native returned a client-visible2006,
while a subsequent text SELECT succeeded. Pure mode returned1064. See the pinned
[error/health probe](https://github.com/masahitojp/mariamem/blob/9250ff5/tests/v06_prepared_error_health.py)
and original spike's guest/native JSON. This is evidence of that matched
combination, not proof every2006 is harmless or a connector root-cause finding.

**Proposal for the later adoption decision:** accept this exact native-parity client error
mapping as a documented consumer exception, provided fresh production-candidate
raw-wire evidence still shows1064/42000, the same pinned native consumer produces
the same exception, and both connections remain usable. Never fabricate2006 on
the server, replace the original FAIL with PASS, or advertise exact exception-code
parity without the exception. If that exception is not accepted, prepared
adoption stays blocked on fixing/updating the consumer path or a new scope decision;
forcing pure mode or interpolation is not completion of the approved goal.
Implementation may proceed without accepting the exception yet; adoption may not.

### Python3.14 / OpenSSL

Homebrew Python3.14/OpenSSL4 import failure occurs before either database is
contacted; the routine canonical CI passed26.7.0 on Python3.14/OpenSSL3 on both
supported OSes. Prepared acceptance must exercise explicit pure and the unmodified default mode
on each OS. Also run explicit C-extension mode where available (the existing
macOS evidence has it). An unavailable Ubuntu C extension is an explicit SKIP of
that additional mode, not a SKIP of the required default/pure consumer or evidence
of C-extension compatibility. No promise of C-wheel availability on every OS is
made. A missing required mode on its supported environment remains a blocker.
Document the concrete successful environment and upstream import failure. Do not
inject deleted SSL constants, force driver mode, or infer a blanket Python3.14
failure or universal support. A supported default consumer must actually run.

## 7. Finite implementation and acceptance plan

Each row is an independently reviewable implementation/test unit. A unit's PASS
does not waive later rows. Reuse existing fixtures and native controls; retain
old failures under their original identities. Do not repeat the whole feasibility
investigation or reopen guest initialization/storage architecture.

| Unit | Required acceptance before adoption |
| --- | --- |
| P1: owner/schema/state and PREPARE | Opcode4 unchanged; opcode5/version mismatch rejected; live/stale/cross-session handles; native parameter descriptors for SELECT/typed expressions/DML/CALL; prepare does not execute SQL; counts and metadata beyond old64 where native accepts |
| P2: typed execution/results | Null and numeric boundaries, exact decimal/binary/Unicode/empty values, temporal cases, repeated type reuse, >4KiB cells and >1,024 rows without truncation; unit packet vectors and native differential cases |
| P3: prepared multiple results | Real guest CALL with0/1/several/129 results where native accepts, IN/OUT/INOUT, later SQL error, metadata changes and following QUERY; PS_MULTI_RESULTS truthful; no leaked pending results |
| P4: lifetime/failures | Go DB/Tx/Conn + pool reconnection and Tx.Stmt, several sessions/statements, CLOSE/LONG_DATA no-response adjacency, invalid handles, quota/allocation/truncation/serialization failures, timeout/cancel/disconnect and cleanup counters |
| P5: consumers/regressions | Fixed Go driver1.9.3 explicit Prepare with interpolation enabled and implicit prepare with it disabled; Python26.7.0 pure/default on each OS and explicit C extension where available; pinned native12.3.3 controls; text/auth/option/routine/SQL/transaction/Snapshot/Fork/isolation/Start/Close regressions; existing GORM/SQLAlchemy anchors |
| P6: canonical ownership | Formal source rebuild with the fixed MariaDB/lite4/converter13 patches/toolchain; independent same-input Wasm builds and independent Go regeneration; exact guest/function/data/J1 rebinding review, failure oracle/control runs; license, provenance, inventory and release guard checks |

Run the required generated-Go runtime/consumer matrix natively on macOS arm64
and Ubuntu x86_64. Native MariaDB12.3.3 reference-engine receipts must state their
actual OS/architecture; a Linux container reference used from macOS is not
relabeled as a macOS-native MariaDB build. Source
and codec negatives belong in deterministic unit tests/CI; real-guest behaviors
need explicit runtime cases. Keep required prepared consumers from silently
skipping in the candidate gate, and decide permanent normal-CI placement for
codec/state tests and selected consumers before main adoption. Do not make the
whole cold source build an every-main-push requirement.

PASS means the named oracle succeeded. FAIL remains a real failure; a Human
accepted consumer exception is a separately recorded disposition, not a changed
PASS. SKIP carries environment/reason and cannot satisfy a required platform or
consumer row. Completion is judged against these units, not elapsed time.

Stop and return a specific blocker/scope change if: public APIs cannot preserve
the required metadata/result semantics; a new converter correctness issue or
MariaDB-internal edit is needed; required default consumers need application
changes; capacity requires a new public cap; or a required oracle cannot be met.
Do not hide an unfinished unit by deferring it to Qualification.

## 8. Cost, generation ownership and next decision

**Planning estimate:9–14 additional engineer-days plus build/CI wait**, not an
approved time budget or delivery promise:2–3 for owner/state/PREPARE,4–6 for typed
codec and result chains,1–2 for failure/resource hardening,2–3 for consumers,
canonical generation and docs (overlapping work may reduce elapsed time). The
range replaces the old provisional5–10 estimate because that spike's fixed
buffers, missing temporal codec and missing prepared chains are now explicit
production work. Re-estimate after P1–P3 expose actual guest constraints; stop for
approval if those constraints change the architecture or maintenance allowance.

Keep the existing0.5–1 engineer-day allowance per future guest update for strict
reapplication/public-API review and focused prepared regression, plus builds/CI;
it remains an estimate. This design aims to avoid a new upstream recipe patch
through authored overlays, but does not count that aim as a verified saving.
Any required source patch must be minimal, ordered, zero-fuzz/preimage-bound and
classified in the canonical source/license provenance; experimental changes stay
in guest/experimental.patch until adoption.

Generated Go is never edited. Update the authored owners/preparation inventory,
release/generated-go-inputs.json and translation/build records, source license
attribution and both inventory mirrors. Review changed guest function/data
identity before repinning J1; keep whole-body/mutation rejection. If a handwritten
runtime file is added, classify it in HANDWRITTEN_FILES and the source inventory;
otherwise do not change that boundary needlessly. Independent regeneration
compares every canonical file including provenance, not a selected count.

At design approval: implement on an experiment branch from then-current main,
return P1–P6 PASS/FAIL/SKIP, native differences, any consumer exception disposition,
maintenance/capacity changes and evidence-backed recommendation to Human Review.
Main adoption, target release placement, final Qualification, Product Validation
and publication remain separate decisions. No tag, main merge or release action
is authorized by this design task.

## 9. Primary source receipts for this design

Pinned MariaDB source_commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e:

- [libmysqld/libmysql.c](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/libmysql.c):
  SHA256d8f0a9d4f7c638bd91d11453e1207ccfe6d3cda85f9c3082e51c37a69c9fc60c;
  lines1865–1889 parameter metadata stub,4293 fetch_column,4888 next_result.
- [libmysqld/lib_sql.cc](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/libmysqld/lib_sql.cc):
  SHA2565de14e2760c775701fe7dff7a9cbf4d47266990081f0abf94e88942a943d377e;
  line337 emb_stmt_execute and the embedded_methods table connect the public
  statement and next-result implementation paths. Existence is not runtime PASS.
- Current local source: guest/resident.inc:95 (opcode4), internal/mysqlwire/wire.go:50
  (incoming frame bound), internal/guest/guest.go:163 (guest response bound).
  Historical prototype: [experimental.patch](https://github.com/masahitojp/mariamem/blob/9250ff5/guest/experimental.patch)
  lines19–20,93–100,206 (fixed limits) and
  [prepared_spike.go](https://github.com/masahitojp/mariamem/blob/9250ff5/internal/mysqlwire/prepared_spike.go)
  (placeholder descriptor/incomplete binary codec). These ground the proposed
  replacements; no new runtime measurement is claimed.

## 10. Design review cross-check (not runtime acceptance)

| Prior condition / gap | Disposition and detection |
| --- | --- |
| Real prepared use in Go/Python; no interpolation workaround | Included in scope/P5. Existing spike supports feasibility only; new required consumers detect regressions |
| Ordered fixed inputs, rebase budget, canonical ownership | Included in P6/section8. Existing source/preparation/generated guards detect identity drift; no new generated artifact exists yet |
| Parameter metadata / values / native engine differences | P1/P2/P3 remain unverified for production. Deterministic packet/native differential oracles required; current text tests cannot prove them |
| Old capacity and no-response behavior | Explicitly replaced by P2/P4 criteria. Existing prototype assertions do not establish large-value or pipelining behavior; those need new tests |
| Consumer syntax/import differences | Section6 retains FAIL/exception/SKIP distinction. CI green cannot authorize the exception or make an unimportable driver work |
| Default mode and both supported native targets | Required P5 matrix, with extra C-mode availability stated separately; no forcing a different driver mode to claim completion |
| Public guide / current scope | No new prepared support is claimed by README/go/python/releasing; implementation must update those guides only with accepted behavior |
| Source/converter ownership / existing correctness oracles | No generated/source/converter code changed in this task. J1 and source/mutation guards remain mandatory; no missing design boundary found here |
| Completion / performance / later gates | All production P1–P6 results are pending; no new performance or Qualification claim, and no implicit version/main/release approval |

One intentional test migration must be visible during implementation:
`tests/test_text_multi_runtime.py::test_binary_prepare_is_not_silently_adopted`
currently enforces main's unsupported PREPARE contract. After scope approval,
replace that assertion with explicit real PREPARE/EXECUTE acceptance and retain
negative assertions for genuinely unsupported modes/flags. Preserve03184a6's
historical negative evidence. Do not skip/remove the case to make CI green.
This approved feature-contract change is separate from existing correctness
failure oracles (J1, truncation, wrong errors, ownership), which cannot be waived
by adding support.

The remaining decision uncertainty is implementation feasibility/cost within the
specified boundaries, not a request to prove arbitrary Wasm or every MySQL
feature. If a named P-unit fails, report that exact unit and its impact on the
adoption recommendation. Do not expand the investigation indefinitely.
