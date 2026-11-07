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
macOS and native Linux scoped checks pass;see the fixed CI receipt below.

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


## macOS result — recorded before the Linux repeat

Fixed guest SHA256:`a75416e3b677b83fb9fca4d213dd67ec32c1e1732939d275866183828aa868ee`
(UNQUALIFIED). Worker Fn151/free,Fn129/yield and Fn211/entry match the complete
reviewed bodies after recorded relocation;ABI offsets remain16/40/44.

- Host owner:six race-checked unit tests,seven detected source mutations.
- Exact guest OPEN method:positive plus three detected source mutations with
  engine stubs. Actual native route:nine PASS,three detected fault controls.
- Lifetime:ten leaf tests PASS on the new staged runtime. The first collector
  rejected the Go package footer after all assertions passed. Its original
  log/failure is retained. The collector fix and owned temporary-directory
  change produce an identical binary and full source inventory on rebuild.
- Original baseline:22 lifecycle/Live cases,88 compat observations,38 limits,
  G1 all234,existing fix/policy/repair controls and worker/binding support PASS.
- G2:all241 PASS,zero mismatch/missing,freshly executing the approved1043 fixture
  on Mac. Baseline287 selected Go/assembly/data files;G2 adds exactly one
  approved fixture for288. No original assertion is weakened.

The [baseline source record](evidence/macos-reference.json),
[G2 result](evidence/macos-g2-result.json),[G2 source record](evidence/macos-g2-build.json),
[ownership cases](evidence/macos-owner-native.json) and
[native fault controls](evidence/macos-native-controls.json) preserve the
source/binary binding. `test_reference.py` checks these pins and CI fixed source
refs before expensive work. Linux must rebuild guest a75416e3,match the287-file
source reference and compare all241 expected/actual/pass observations. Original
comparison rules ignore only the already-approved nonnegative mid-output byte
count. Linux acceptance,public integration,performance and adoption are not
claimed by the Mac result.


## Linux repeat — bounded P1-a complete

[CI42346396518](https://github.com/masahitojp/mariamem/actions/runs/42346396518)
succeeds on exact candidate source_commit
`738bbbe58674f097161a1db2c1eda91536e416fe`;guest,linux and discard-transit
jobs all succeed. The [receipt](evidence/ci42346396518.json) binds the candidate,
source/guest hashes,artifact checksums,actual counts and cleanup outcomes.

Linux reproduces guest a75416e3 from checked b2d9a2a6,passes nine native
ownership cases,three native-route fault controls,ten lifetime leaves and
six owner unit tests with race detection/seven source mutation controls.
The exact OPEN seam also passes its three engine-stub source mutations.
Original22 lifecycle/Live,88 compat,38 limits,G1 234,G2 241 and supporting
checks pass. All287 baseline Go/assembly/data files match Mac;all241 G2
expected/actual/pass records match under the existing single ignored byte-count
rule. Neither assertions nor accepted contracts are weakened by this repeat.
Builder/runtime cleanup debt is0;the disposable transfer artifact is deleted.

P1-a is complete for this experimental boundary on both native platforms.
Next is P1-b public timeout handling,then P1-c public native backend/owner
integration. Remaining coordination,consumer/performance,canonical adoption and
release are separate unfinished work. This result is bound to the tested
candidate above;documentation/result commits do not relabel its CI evidence.
