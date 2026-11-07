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

## Reproduction and detection boundaries

The guest/checked host origin is source_commit
`b2d9a2a6e37ed7dd3149b6c85f8908d8d11df17a`. Tooling is a separate,clean
commit;its main/runtime/owner-test overlays are inventoried explicitly. New
worker binding and Mac source/observation pins are recorded after the first
fixed-source build. Linux must reproduce those pins;it cannot refresh them.

Use owned workspaces with12GiB budgets/free floor and Python3.14 for host
translation. `probe_baseline.py build` uses native Linux arm64/root;
`probe.py runtime` requires native Linux x86_64. The local sequence is
`translate`,exact worker binding review,`record-local`,then `probe.py observe`.
These commands use the original lifecycle/compat/limits/G1 fixtures and the
previously approved1043 G2 fixture transformation.

`owner_controls.py` runs the six owner tests with race detection and seven
source mutations. `controller_controls.py` compiles the exact guest OPEN
method with engine stubs and detects three identity/watermark mutations;it is
not a full-engine mutant run. Native tests additionally reserve a host-only
slot before opening a real SQL connection. `native_controls.py` mutates an
outgoing OPEN tuple to obtain a genuine native response with the wrong
identity,injects RETIRED before the Go completion barrier,and ignores one
relay join. Each mutated binary must fail its unchanged native oracle. The
OPEN envelope control models an allocator mismatch;it does not rebuild the
engine with a different allocator.

Late OUTPUT/CREDIT/RETIRED/OPENED controls enter the same receiver used by the
transport;stale DATA/ACK/EOF go to the actual guest. Native completion
instrumentation is limited to handwritten staging glue. No canonical generated
function body,public owner API or public default route is changed.
