# P3 full matrix and external OUT negotiation

The approved P3 continuation after [minimal real-guest PASS](v06x-prepared-call-pass.md)
uses14 pinned native cases. [Initial evidence](v06x-prepared-p3-matrix-evidence/receipt.json)
preserves the original13-case native oracle and actual guest failures before
repair; adding a paired capability-positive control leaves all13 original
packet/metadata/error expectations unchanged.

Cases cover0/1/several/129 ordinary results, IN, OUT, INOUT, repeated execution
with descriptor reuse, combined IN/OUT/INOUT, initial/later SQL errors, changed
column count/type under the same prepared handle, following QUERY/CLOSE/PING,
and external PS_MULTI_RESULTS on/off. Native14 capture and replay PASS. Each
scenario owns a fresh root DB in the guest runner, so a broken case cannot make
later cases appear to fail or pass through a contaminated DB.

The formally regenerated/compiled baseline guest at9d25fde (same engine/runtime
code as tested42be2b5) matches11 original scenarios. It fails only the two cases
without PS_MULTI_RESULTS: an extra dedicated OUT result appears. The raw reader
consumed all received packets before its result-count assertion failed. No SQL
wrong value, crash or hang was reproduced. An ordinary client that stops reading
where the negotiated protocol says it should may leave extra response packets;
that application consequence is a risk inferred from the observed protocol
mismatch, not a reproduced driver failure. See saved full packets and stages.

The bounded fix belongs to the handwritten Go protocol bridge, not MariaDB
internals or wasm2go. Validate the Ready/open owner before advertising supported
prepared execution. Retain the external client's PS_MULTI_RESULTS bit. The
embedded connection always enables the internal flag, but native
[Protocol_binary::send_out_parameters](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/protocol.cc#L1936)
sends OUT to external clients only when that bit is negotiated. Apply that same
rule at the bridge: completely consume and validate the guest chain, then expose
its dedicated SERVER_PS_OUT_PARAMS result only to a client that requested it.
Ordinary result sets, terminal OK/errors and procedure execution are retained;
SQL is not retried. This is explicit, native-matched capability negotiation,
not an arbitrary result-count exception. A malformed unexposed OUT remains a
transport failure; unit oracles must prove it cannot be hidden by the selection.

PS capability advertisement is conditional on the validated guest actually
supporting EXECUTE. A legacy guest or PREPARE-only staged owner keeps the prior
advertisement. Fresh FOUND_ROWS reopening must still replace registry generation
and apply the final client's negotiated bit. Public library APIs, guest inputs,
all converter patches, existing native oracles and canonical Generated Go remain
unchanged.

The fixed handwritten host at source_commit
`49cb504006809a06d3625c3bbe62810e4fd38bf1` now passes all14 actual guest/native
cases locally on macOS arm64, including required advertisement and both negotiated
states. There are no failures/different cases. It also passes the previous P1,
all72 P2 cases, minimal CALL and the SQL/transaction/Snapshot/Fork/Close smoke.
Local112 Python/C checks PASS; the3 Go packages pass non-race units. Subsequent
[exact-candidate both-OS CI now PASSes](v06x-prepared-p3-pass.md), including race
suites and all14 cases; P3 development acceptance is complete.

This local host reuses the formally installed baseline's unchanged99-file
Generated Go inventory with the identified committed handwritten host source.
Every copied tracked source file is checked, with the standard dev runtimekind
SHA binding recorded separately. The original formal development receipt is
kept unchanged: the diagnostic has its own source/binary/input inventory and is
not relabelled as a fresh formal-origin checkout or used to widen source-origin
guards. Final CI must freshly build/compile/verify the actual candidate normally.
The [diagnostic recipe](v06x-prepared-p3-matrix-evidence/diagnostic_host.py) and
[identity receipt](v06x-prepared-p3-matrix-evidence/receipt.json) preserve this
boundary. Put actual Go1.26.8 on PATH when reproducing the recipe; use the same
24GiB budget and8GiB floor for disposable caches/output.

For clean exact-candidate acceptance, run the eleven scoped pytest suites and
three Go race packages in prepared-product.yml, then its complete runtime gate.
The new final command is tests/v06_prepared_p3_matrix.py --host HOST
--require-advertisement --reference tests/fixtures/prepared-p3-native.json
--output OUTPUT. The workflow preserves all older probes before this gate.

This bridge policy matches the externally observed native protocol. The embedded
connection still materializes its internal OUT result before selection; it does
not eliminate that allocation cost. Large-result/resource limits and failure
hardening remain part of P4, not a claim of this14-case correctness comparison.

P3 closes only after the full matrix, truthful advertisement and on/off behavior,
plus previous P1/P2 regression gates, pass on both supported OSes. P4–P6, required
consumer acceptance, canonical/J1 independent generation and Human adoption/
release decisions remain separate. No shared-memory or storage redesign is
introduced by this repair.

## Coverage against the approved P3 row

| Required item | Named controls/evidence |
| --- | --- |
|0/1/several/129 ordinary results|zero-results, one-result, several-results,129-results (130 responses including terminal OK)|
|IN/OUT/INOUT|IN, OUT-only, INOUT-reuse, combined IN-OUT-INOUT-reuse|
|Repeated metadata/binding use|INOUT and combined descriptor reuse; different column shapes between ordinary and OUT results|
|Later error and healthy following QUERY|later-error, initial-error; exact1644/45000/error packet plus following SELECT1 and CLOSE/PING|
|Metadata changes|same prepared handle after column type/count ALTER; complete metadata/row native comparison|
|PS_MULTI_RESULTS truthful|validated EXECUTE-only advertisement; required live handshake check; paired PS-positive/negative procedures|
|No pending result leaks in these scenarios|all responses drained; following QUERY after every execution; CLOSE immediately followed by PING; root cleanup errors fail each case|

These controls do not substitute for P4's broader lifetime/resource testing or
P5's real Go/Python consumer acceptance. Both-OS CI39686154515 now passes this
same fixed matrix and previous gates; see the linked acceptance record.
