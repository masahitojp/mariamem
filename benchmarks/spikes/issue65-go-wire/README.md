# Issue #65 step 3C: generated-Go native-protocol endpoint

**Conclusion:** step 3C passes its four scoped execution cases on macOS arm64.
Continue to the 3D ownership/quiesce design; do not adopt this fixture yet. The
decisive evidence is a real SQL driver using upstream protocol/parameter decoding
inside generated Go, including failure joins and sibling-instance survival. The
strongest remaining objection is that fresh-instance success says nothing about
capturing/restoring threads, transport queues or NET state. 3D must resolve that
before Snapshot/Fork integration.

This is an isolated architecture experiment, not candidate adoption or release
qualification. The approved scope is real TCP driver login/text SQL/prepared
input, host byte relay, deadlines/join and independent-instance isolation.
Snapshot/Fork/Live (3D), production APIs and controller placement are outside it.

The prototype uses upstream MariaDB NET/Protocol and parameter decoding.
The Go endpoint relays opaque MySQL bytes and the private control envelope;
it has no second server-side MySQL packet/SQL parser. The C++ controller is
still co-located for this spike. Moving timers/queues to Go remains design work.

## Confirmed execution

The same final binary passes all four cases in evidence/protocol-final.txt:

| Case | Observed result |
| --- | --- |
| ProtocolPrepared | TCP login, 42/43, SQL error and following command, server prepared int42 / a-NUL-b / NULL, statement close, PING, normal close/reconnect47; native started2/joined2 |
| QueryDeadlineAndIsolation | two roots in one Go process have distinct host epochs; foreign epoch rejected; SLEEP10 stopped by 800ms deadline; sibling SELECT44/45 before and after failing root joined; both started1/joined1 |
| PartialInputDeadline | one header byte starts receive deadline; 800ms deadline retained as original cause; started1/joined1 |
| SlowOutputControl | unread 4MiB result blocks at exactly65536 bytes outstanding; separate session SELECT46/control continue; 3000ms deadline retained; started2/joined2 |

All cases also wait for the Go runtime completion channel and host relay workers.
The default binding tests pass21/21; wrong-guest and wrong-full-body-hash controls
reject with nonzero exits. Patch/source consistency checks cover both added C++
source blocks. These are focused experiment checks, not broad product acceptance.

## Identities and reproduction

The final guest is built from source_commit
`03a97af62b6211cb30a69f58063f6356e3c06a29` (full identity in evidence/guest-final.json), SHA256
`07852302f8e0f7269e700df813383c2147428e1eff9f7ac39b52bd4e983255d4`.
The checked installer host source and exact compiled product inventory, templates,
Go1.26.10 build information and binary SHA are in evidence/host-build.json.
This is an UNQUALIFIED development artifact, not the published runtime.

For reproduction, extract these spike tools to external owned temp first, build
the guest at its recorded source commit, then use host source_commit
`a9d9502c17168dcecc98b700ef59a1eca7f65eb4` (full identity in host-build.json). Later report/helper-only commits
are not relabelled as the executed source.

Use a disposable experiment workspace with 12GiB owned budget/free-space floor,
canonical LLVM23 development guest build and locked downloads. The committed
experimental.patch is authoritative. Then run assemble.py --translate-only,
review complete worker bodies with refresh_binding.py, commit the explicit
experimental binding, and assemble.py --resume. These scripts intentionally
require a clean source identity and owned workspace; they are spike tooling.
Run the built wire.test with bounded test/external timeouts. Keep raw observations
before normalizing personal paths for public evidence; preservation.json records
both hashes. SDK/generated code/WASM/Go caches are disposable after verification.

## Problems exposed by execution

1. First actual login aborted in native dispatch because embedded THD's C API
   client_params fields were not initialized by this native entry. Explicitly
   initialize those fields to NULL/zero, retain the invariant and keep upstream
   parameter decoding. The diagnostic stack and original failed attempts remain.
2. SQL and prepared input then worked, but normal driver QUIT followed immediately
   by FIN poisoned the instance. Preserve queued bytes on input FIN and let native
   NET/dispatch distinguish QUIT from incomplete/abandoned work. Write failure is
   a separate transport event. This is protocol ownership, not a host-side parser.
3. The canonical worker-lifetime installer correctly rejected a different guest.
   An explicit development-only exact-body binding was added; the production pin
   remains unchanged. Complete bodies match the reviewed prior ABI after recorded
   function renames/static relocation/TLS-size changes. Mismatched guest/body hashes
   are negative controls, not accepted fallbacks.

## Limits and next decision

This spike does not establish full protocol/client compatibility, performance,
race freedom, snapshot safety or production readiness. Native session ownership
and failure gates remain guest-authoritative. The host adapter is fresh-instance
only; snapshot/capture/restore paths are explicitly rejected. No main integration,
issue closure, release CI or publication is authorized by these results.
