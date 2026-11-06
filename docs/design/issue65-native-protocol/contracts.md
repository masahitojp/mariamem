# Issue65 — compatibility contract and host/guest ownership

2026-11-06. **D1–D3 approved for the native endpoint; implementation and
compatibility acceptance remain pending.** The Human accepted all three
recommendations after discussing SQL-client connection loss and owner-side
error reporting. The [decision](../../decisions/issue65-native-wire-contract.md)
records the approval and its scope. The original proposal is preserved at
source_commit `a1dfa69a4727fcedcd4b5a7ba46b8acb0fa1a610`.

The Human selected compatibility/contracts after Linux and Live, and prefers
host-owned stateful coordination. Host owns lifecycle/resource policy; guest
retains authoritative native SQL admission and session state. Native normal wire
semantics and transport close after fatal instance failure avoid synthesizing ERR
inside an arbitrary native response. Wire-only clients lose the original-cause
message; the owning mariamem object/diagnostics must retain that cause and cleanup
state. This approved tradeoff is not yet a verified public API implementation.

| Approved change | Contract and consequence |
| --- | --- |
| D1: fatal failure after a native session starts | Close every transport of that instance; preserve the first cause and cleanup disposition through the owner API/diagnostics. Do not guarantee a server ERR2013/HY000 or its message on an established stream. Keep bounded host pre-login rejection separately. Wire-only consumers lose the original-cause message. |
| D2: malformed EXECUTE string whose length exceeds remaining bytes | Retain the pinned native decoder's observed empty-string acceptance, explicitly named as an exception. Do not duplicate the parameter decoder in Go. A stricter rule would require a minimal guest/upstream change and separate evidence. |
| D3: old internal JSON/typed bridge envelope | Remove that representation's 32MiB limit from the new streaming route; retain the separate client command/SQL/output-packet bounds. Do not invent an equivalent aggregate byte limit or claim bounded total SQL/RSS. Large aggregate results may complete where the old representation failed; limits must be documented and measured. |

D1–D3 are **APPROVED** for the future native route. The running stable product
and its legacy regressions remain unchanged until implementation and verification.
This approval adds no commands, client profiles, main integration or release.

“Owner” means the host-side mariamem DB/Live resource owner that starts/stops the
instance and retains disposal responsibility, not the SQL username or ORM pool.
The SQL driver observes connection loss (wording depends on the driver/transport);
the mariamem management side must expose the original failure and cleanup state.
Ordinary SQL errors still use native ERR and permit subsequent commands where
specified; they are not reclassified as fatal instance failure.

## Source and evidence boundary

Inspected experiment source_commit `43d96a62740c8e7309e3e6709d2d83fc929c653d`.
Guest source_commit `5d9915d9940ff691249361aafb6ea39551f29a87`, guest SHA256
`c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf`;
host execution base `ecd5d2b7ceff2085cac59f629c36d688007fc6bc` plus inventoried
templates. MariaDB source remains `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.

[Linux42146945114](https://github.com/masahitojp/mariamem/actions/runs/42146945114)
passed the same14 cases, controlled worker join and binding guards; all274
Go/assembly/data inputs matched macOS. [Live42150799762](https://github.com/masahitojp/mariamem/actions/runs/42150799762)
passed all22 cases (14 original plus8 Live), including physical drain, reserved
replacement, generation commit, cancellation, ordinary cleanup recovery and
permanent capture debt. Actual receipts retain distinct binary/template hashes;
the Live build adds exactly two files without changing the baseline source bundle.
Both CI campaigns disposed owned workspaces and their WASM transfers.

These prove isolated native execution and lifecycle behavior. They do not prove
that public APIs use this route, the complete advertised capability/profile,
all prepared edges, 17th-connection behavior, overflow parity, or race freedom.
Some failure controls are explicit models, as the original reports state.
The [original design](README.md) and [capture design](snapshot-fork.md) retain
their original decision/evidence context. No historical pending claim is silently
relabelled as acceptance of this approved contract.

Compatibility basis: the inspected source's
[wire contract](../../decisions/v060-wire-contract.md),
[active fixture inventory](../../reviews/issue94-wire-inventory.md),
[protocol guide](../../mysql-protocol.md) and
[fixture acceptance fields](../../reviews/v06x-fixture-acceptance.json).
This is an exact-source basis, not a claim that the experiment tracks future main.
Before adoption, reconcile the actual integration base and its later decisions.

## Current evidence after the native policy repair

The original gap observations below remain scoped to43d96a62. The fixed
candidate `ba3e092eced56ca67a5cf5a16e7e3a84a96df752` passes its22-case/126-observation
native campaign on macOS arm64 and Linux x86_64 at
[CI42289241674](https://github.com/masahitojp/mariamem/actions/runs/42289241674).
This closes the tested boundaries, not the entire table or public integration.
The [scope review](../../reviews/issue65-native-compatibility-scope.md) maps each
remaining item to actual coverage, legacy-only checks and its proposed stage.
It recommends a finite prepared-input check next; it does not authorize new
experiments, relax this contract or select production adoption.

## State belongs with the authority that can make it true

| State / responsibility | Target authority | Guest/host counterpart and invariant |
| --- | --- | --- |
| Listener/Pipe attach admission, 16 shared session reservations, public connection count | Host | Guest accepts only a matching admitted OPEN. A retiring native worker still occupies capacity; transport EOF alone cannot release its slot. |
| Instance epoch and monotonic session identities | Host lifecycle owner | Guest validates epoch/generation and owns the corresponding live THD handle. Current fixture instead allocates slot/generation in C++; relocation is future work. No duplicate allocator or reuse before joined RETIRED. Exhaustion fails closed. |
| Live generation, candidate, stable relay, draining, commit and recovery | Existing host `internal/live.Endpoint` | Guest has no Live generation algorithm. Old child retirement precedes commit; reserve replacement before drain. Do not migrate sessions. |
| Fork reservations, backing pins, cleanup debt and permanent capture debt | Host | Native cleanup/join reports supply evidence. Timed-out/failed execution is not proof of disposal; Reset cannot forgive capture debt. |
| Transport queues, input/output byte accounting, fairness, scheduling and transport deadlines | Host policy and transport owner | Keep bounded Vio buffers/wakeup mechanics in guest. Credit/ACK/offset validation at the boundary remains necessary. Define total outstanding ownership across queues; do not multiply the input budget per copy. |
| SQL command ID, first-byte/NET-buffer admission, RECEIVING/EXECUTING/FLUSHING, transaction status and capture fence | Guest atomic gate and owning native worker | Host sees observations for diagnostics, not permission to capture. A delayed BUSY notice cannot authorize Snapshot. Preserve final dispatch fence and upstream buffered-input hooks. |
| Prepared statement IDs/types/long-data, session variables and native protocol sequence | Native MariaDB session | Host stores no second prepared registry or parameter decoder and generates no normal greeting/rows/OK/ERR/EOF. These states do not survive Fork or Live Reset. |
| Command deadline at atomic admission; THD cancellation and native worker join | Guest initially | Host owns transport deadlines and an independent instance watchdog. Moving timer scheduling later must preserve the first-byte bound despite delayed/lost notifications and reject stale command tokens. Do not delete the local watchdog based only on host preference. |
| THD/current_thd, Vio/NET lifetime, rollback report, native reaper/killer | Guest/native worker boundary | Host requests stop and retains resources until actual generated-worker and reader/relay joins. A callback returning or native DONE alone is insufficient. |

The result is **host-owned policy and durable resource ownership, with a small
guest mechanism and authoritative SQL gate**. It is not a stateless guest.
A THD transaction, NET read-ahead or native statement map cannot be reconstructed
from asynchronous host notifications without reintroducing protocol/SQL logic.
The current C++ Manager is a proof controller, not the target product placement.

No cgo boundary is selected here. This route still compiles guest C/C++ through
WASIX/wasm2go; the existing private byte/control channel is the established seam.
A future direct callback/shim must be a separate small proof of ownership,
blocking/wakeup, cancellation and join behavior. It must not simultaneously change
protocol semantics, controller placement and the measured baseline.

The custom C++ Manager can therefore shrink substantially: host-side admission,
identity allocation, queue policy and lifecycle orchestration need not remain in
that proof controller. This does not remove MariaDB's own C/C++ or establish that
all custom C++ can disappear. Memory-Vio callbacks, native initialization/cleanup,
THD/NET and buffered-input hooks, the atomic SQL gate, rollback observation and
native cancellation/join mechanics still need a guest-side boundary. Scheduling
or tracking their work can move independently from the native operations they
control. The amount removable is not measured; retain correctness/ownership
proofs while moving one boundary at a time.

## Observable compatibility profile

The entries below are contract requirements or explicitly approved exceptions,
not claims that the present fixture implements every row. Native decode/policy
hooks enforce guest-side requirements; the host never parses normal MySQL packets.

| Boundary | Target disposition | Required native-route evidence before adoption |
| --- | --- | --- |
| Credentials and identity | Preserve placeholder username/password acceptance, canonical root SQL identity and existing full local test privileges. Preserve default returned root/empty credentials. No account authentication promise. | Rebind the credential matrix, empty username, secure/legacy response, initial DB/charset, USER()/CURRENT_USER(), malformed login and follow-up SQL. |
| Capabilities | Preserve bits1,4,8,512,8192,32768,65536,131072,524288; conditional PS_MULTI_RESULTS262144 only for validated prepared execution. Preserve accepted FOUND_ROWS2 behavior; no upstream default leakage. | Capture greeting and negotiated subsets; text/prepared multi-results, FOUND_ROWS status/affected rows, malformed required flags. Advertising bits alone does not prove negotiated behavior. |
| Commands | Keep QUIT1, INIT_DB2, QUERY3, PING14, PREPARE22, EXECUTE23, LONG_DATA24, CLOSE25, STMT_RESET26, SET_OPTION27. | Guest native decoded-command allowlist and raw negative paths. RESET_CONNECTION31, STMT_FETCH28/cursors, LOCAL INFILE, admin/replication remain OUT. STMT_RESET and Live Reset do not enable RESET_CONNECTION. |
| Login/output scope | Retain no TLS, compression, DEPRECATE_EOF or alternate auth; no packet continuation. Preserve existing negotiated multi-statement COM_QUERY / SET_OPTION behavior without expanding it. Normal packets come from native NET/Protocol. | Reject unsupported login/commands without desynchronizing supported subsequent work where the existing profile permits recovery. |
| Prepared session state | Keep alias0xffffffff, zero-parameter flags, signed/unsigned/NULL/NUL/temporal values, type reuse, session isolation, RESET and long-data error lifetime. Native owns the state. | Raw vectors for explicit/alias IDs, failed/new prepare invalidation, CLOSE/RESET short and surplus bodies, unknown handles, invalid index/deferred error, RESET clearing and following-query oracles. D2 is the named approved exception. |
| No-response commands | QUIT/CLOSE/LONG_DATA do not gain a synthetic response. Completion is native dispatch/lifecycle completion. | Chain the next PING/EXECUTE/QUERY immediately; compare response sequence, results, handle lifetime and retirement, not merely absence of an error. |
| Client input limits | Preserve1MiB SQL, nonzero command payload <=1,048,577 bytes and command-specific EXECUTE/LONG_DATA bounds. Reject continuation at every NET header, including warm buffers, before allocation/read. | Boundary and max+1 cases for each command; native decoded lengths and existing typed-codec limits as source anchors. A blanket NET cap is insufficient. |
| Pipeline / disconnect | Preserve serial execution and ordered responses, cumulative pending raw input1,048,581 bytes per physical connection, overflow aborting that instance, monitoring EOF even at a full window. | Deterministically hold SQL/output, fill exact budget, inject one extra byte or peer EOF, require bounded failure and an independent DB still usable. Include TCP and Pipe. No host command parser is needed to count raw outstanding bytes. |
| Output limits | Preserve maximum payload0xfffffe per MySQL response packet and no continuation. D3 removes only the obsolete internal envelope boundary. Output credits remain transport bounds, not a total engine allocation limit. | Native oversized row/metadata/multi-result cases and >32MiB aggregate streaming with exact data/row oracle, slow output/control progress and measured queue peaks. Do not inject ERR after a partial native packet. |
| 17th physical connection | Host reserves across TCP/Pipe before guest OPEN. Retain the existing bounded pre-login ERR1040/08004 rejection helper, independent of a spare SQL worker, then close. Pipe public admission retains ErrCapacity. | Fill16, attempt17 on both transports/mixed, assert errno/SQLSTATE or public ErrCapacity, bounded responder concurrency/time/memory, no native worker growth, continued existing SQL, reuse only after RETIRED. Live's stable relay admission also needs an explicit client-visible parity check. |
| Ordinary SQL error | Native errno/SQLSTATE and following-command usability remain required. | Unknown table/statement, bad arguments, multi-result terminal error and a following query on the same connection. No generic EOF substitution for ordinary SQL errors. |
| Fatal established session | D1: connection loss plus owner-side original cause; no in-stream host failure serializer. Pending I/O is woken promptly, same-instance peers fail, independent lineages survive. | Idle PING, partial header/body, active SQL, partially written output and buffered future commands; no injected corrupt packet, no early resource release, original/cleanup causes and admission/debt observable through owner. |
| Snapshot/Fork/Live | Preserve the proven consuming/reversible boundaries, fresh session identity, rollback, physical drain, reserved replacement and permanent debt. | Carry the14+8 native cases to the actual public route; additionally port production Fn-index owner tests and run both supported OSes. Existing model faults keep their model attribution. |

A pre-login fixed rejection is the intentionally retained host wire surface: its
boundary and sequence are known before session handoff, its response is bounded,
and it parses no command or parameter. Keep it isolated from established streams.
Reuse/extract the fixed helper rather than retain the general serializer as a
fallback. Host must decide “reject” versus “hand off” once, before any native
byte is forwarded; a race cannot send two greetings or mix a reject with native
output. Unavailable-before-login may keep the existing bounded fixed helper;
established-session failure still follows D1.

## Concrete gaps in the current experiment and detection limits

These are source observations at43d96a62, not newly executed negative tests.

* `guest/experimental.patch` sets greeting capability bits, canonicalizes root
  after native authentication and adds a1,048,577-byte NET header cap. It does not
  establish the full credential/negotiation matrix or command-specific policy.
  The dispatch hook records command start; it is not a product allowlist.
* `benchmarks/spikes/issue65-native-capture/main.go.txt: attach` closes an OPEN
  rejection without sending the stable pre-login capacity ERR. Slot/generation
  allocation remains in guest Manager. Neither becomes host-owned because Live
  forwards to the instance.
* That relay stops socket reads while sent-minus-consumed reaches the input
  window. The guest queue also has a bound, but this does not prove detection of
  additional socket bytes/EOF at a full window. Backpressure alone is not the
  existing overflow/continuous-disconnect contract. Preserve bounded accounting
  and add a bounded overflow/EOF observation path without accumulating excess
  data; if this cannot retain parity, bring back the exact product choice.
* Native Protocol output is reused. The input cap is not evidence that native
  output cannot split oversized packets or exceed the existing result limits.
* `internal/mysqlwire/worker_failure_test.go: TestIdlePingRejectsFailedInstanceWithOriginalCause`
  requires the legacy in-stream original-cause ERR. It would conflict with D1.
  Keep it protecting the legacy route until an approved new contract is actually
  implemented and replacement native oracles exist; do not remove it to adopt
  the current fixture.
* Prepared RESET/LONG_DATA/alias/malformed paths have legacy source/tests and
  earlier native anchors. The22-case Live success does not execute their full
  raw-wire vector set. The step2 malformed-string observation is native evidence
  at a different profile, not final WASIX endpoint compatibility acceptance.
* Existing public/source-contract CI pins the legacy wire implementation. A green
  legacy job cannot detect an absent native-path policy hook, capacity responder
  or profile regression. Version the native profile and bind actual new tests to
  it at productization; do not simply replace the four legacy file hashes.

## Proceeding conditions and cost

The D1–D3 Human decision is complete. Next run one bounded compatibility experiment, initially2h active/tooling30min,
at most2 heavy CI submissions, owned12GiB/free floor12GiB per builder/runtime.
Reuse the fixed guest only for observations it can make; any policy patch gets a
new guest identity and separate old/new evidence. Start with raw handshake/caps,
prepared state/no-response vectors, capacity and full-window overflow/EOF. Record
exact native reference, experiment and declared client versions/options, expected
outcome, original failures, following-query/retirement oracle and what remains
UNVERIFIED. Use deterministic barriers where ordering matters.

This contract document costs no runtime build or CI. It neither declares the
compatibility stage complete nor begins controller relocation/productization.
If evidence forces a semantic change or the budget expires, report the named
missing behavior and concrete next cost before enlarging the campaign. Later
production extraction must move one owner at a time and retain the lifecycle
proofs; matched performance comparison follows correct public-route integration.
