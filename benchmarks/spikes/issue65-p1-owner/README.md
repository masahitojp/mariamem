# Issue65 P1-a: host session ownership

The Human approved implementing the P1-a boundary after the SHA-pinned
[plan/review](../../../docs/reviews/issue65-p1-host-ownership-plan.md).
Base source3f934997cd8ead4daf6a639c7fc75cbb1d863e06. This is experimental
implementation,not public routing,canonical adoption or release.

Host owns one shared16-slot lease table,epoch/per-slot generation and saturated
request IDs. The existing instance lifecycle mutex serializes this owner with
admission/Close/capture. Native profile2 requires OPEN to carry the chosen tuple;
guest only validates an empty slot and newer watermark. SQL/NET/THD/prepared,
first-byte gate,timers,byte queues and native cancellation/reaper stay guest.

A lease requires native retirement and both session relays to end before reuse.
An uncertain OPEN remains owned until root disposal. Native root worker join,
shared reader/host joins and backing disposal stay separate from slot reuse.
Owner unit/race tests cover the two completion orders,uncertain OPEN,capture
preconditions,stale identities and repeated/concurrent counter exhaustion.
Runtime/native tests and both-platform evidence are pending.

A private INSPECT response exposes a live native worker's pthread identity for
retirement-barrier tests. The staged handwritten ThreadLifetime owner receives
explicit checksum-guarded test instrumentation;no wasm2go function body or
canonical installer input is edited. The barrier runs before completion/free
publication and defaults to a no-op. It is not a new per-session join API.

Budget:active3h/tooling45min,owned builder/runtime12GiB each,free floor12GiB.
First deterministic host unit/fault tests,then one new native guest/binding
review and macOS run,then at most one Linux CI for this cohort. Preserve original
G1/G2 and lifecycle assertions;only approved1043 fixture adaptation and explicit
source/ABI fixture initialization changes are allowed. Public30s timeout and
public backend/owner API integration remain P1-b/P1-c;P2 remains separate.
