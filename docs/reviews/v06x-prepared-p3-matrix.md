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

Fixed-host local runtime and both-OS exact-candidate CI remain pending at this
source commit. Native comparisons and component tests alone are not acceptance.
The local diagnostic may reuse the formally installed baseline generated tree
with unchanged inventory and a separately identified handwritten host patch;
that is not relabelled as a fresh formal checkout or used to bypass source-origin
guards. Final CI must build/compile/verify the actual candidate normally.

P3 closes only after the full matrix, truthful advertisement and on/off behavior,
plus previous P1/P2 regression gates, pass on both supported OSes. P4–P6, required
consumer acceptance, canonical/J1 independent generation and Human adoption/
release decisions remain separate. No shared-memory or storage redesign is
introduced by this repair.
