# P3 first CALL: source candidate, actual guest gate pending

This continues the approved P3 scope after [P2 development acceptance](v06x-prepared-p2-pass.md),
using the Human's [embedded API source investigation](v06x-prepared-p3-source.md).
The first case is one OUT parameter plus two ordinary result sets. This is not
full P3 acceptance, main adoption, Qualification or release.

## Small implementation boundary

The authored guest/prepared_api.inc captures one typed result at a time and
advances with the public mysql_stmt_next_result API. Each result rebuilds its
metadata and owned result buffers, captures status/warnings before cleanup, and
retains its binary values. A successful chain contains the ordinary results,
OUT result and terminal OK in order. Later SQL errors retain errno/SQLSTATE;
failed cleanup, impossible next-result transitions or allocation/serialization
failure terminate the transport rather than report partial success. EXECUTE is
not retried. The existing single-result path and total envelope bound remain.

Go's private EXECUTE adapter accepts explicit binary chains only for EXECUTE.
PREPARE/lifecycle still reject chains. It validates all elements before returning
any response packets, including handle identity, version, result shape and
MORE_RESULTS consistency. It preserves OUT flags instead of reconstructing them
from assumptions about result positions. A terminal SQL error remains an error.
No public API or exported wire capability changes. In particular,
PS_MULTI_RESULTS remains unadvertised until the complete P3 implementation and
matrix are verified. The experimental raw client explicitly requests that flag;
this one probe is not ordinary-driver capability acceptance.

No canonical guest/source.patch, converter13 patches, toolchain pin or generated
Go file is edited. P2's experimental internal-source repairs remain unchanged.
The old4dad84d0 binding deliberately rejects the unknown new guest. The source
branch only builds the guest and runs unit gates; actual runtime is SKIP until
exact new identity/function/data/TLS/initialization review. The runtime gate on
prepared-product then retains all prior P1/72 P2 scenarios and appends this probe.

## Evidence and current limits

[Receipt and local logs](v06x-prepared-call-minimal-evidence/receipt.json) record
input hashes, actual local/compiler environment and native fixture provenance.
Local106 pytest checks PASS, including ordinary C and ASan/UBSan owner cases.
Go1.26.8 darwin/arm64 passes -race -p1 for internal/preparedproto,
internal/mysqlwire and internal/guest. These Go tests link the unchanged canonical
runtime; they do not install or execute the new guest. There are no local test
SKIPs in this focused set.

The fixed native12.3.3 image runs Linux aarch64 through Docker on macOS arm64;
it is not a macOS-native MariaDB server. Initial capture and independent command
replay both PASS. The reference fixes full PREPARE descriptors, result metadata,
binary rows, each EOF/status and terminal OK. The expected sequence is:

| Element | Columns / values | Status |
| --- | --- | ---: |
| First ordinary result | first_value=11 |10|
| Second ordinary result | second_value=22, extra_value=33 |10|
| OUT result | v=44 |4106 (includes SERVER_PS_OUT_PARAMS)|
| Terminal OK | No columns |2|

A following SELECT1 and CLOSE immediately followed by PING both PASS natively.
Failures record the read/execute stage, wire errno/SQLSTATE where available, raw
error bytes and host diagnostics. The harness does not treat a missing OUT or
unread terminal response as success.

C/sanitizer mocks check per-result buffer/metadata switching, OUT/status retention,
exactly one execution, later error capture, invalid next-result rejection and
existing owner/failure controls. Go unit tests compare every generated packet to
the native capture, reject malformed suffixes without partially emitting a
chain, and retain a terminal SQL error. These are component tests, not real
guest execution. Canonical inventory verification concerns the unchanged routine
guest, not this new prepared candidate. Native success does not prove WASIX API
success.

## Reproduce and next gate

1. Inspect scripts/git_identity.py before building and use the fixed source and
   converter/toolchain pins from the preceding P2 receipts. Run the ten scoped
   pytest suites named in the prepared-product workflow, and its three Go
   packages with -race -p1. Record actual Go1.26.8 darwin/arm64 locally; source
   preflight CI runs its unit jobs on both supported platforms.
2. With the recorded immutable MariaDB image, run tests/v06_prepared_call_probe.py
   --native-port PORT --reference tests/fixtures/prepared-call-native.json
   --output OUTPUT. This one fixture does not replace the later full matrix.
3. Submit experiment/prepared-call for fresh source compilation. Obtain the
   exact guest/source inventory, then translate with unchanged converter13 patches
   and review full lifetime functions, data/TLS and complete memory initialization.
   Do not widen the source-origin exception or guest allowlist.
4. With that reviewed single binding, run prepared-product's installed both-OS
   runtime gates including the new native comparison. Minimum real-guest PASS
   permits the approved full P3 matrix (0/1/several/129 results, IN/OUT/INOUT,
   later errors, metadata changes, capability truthfulness and pending-result
   cleanup). FAIL must preserve stage/errno/SQLSTATE and stop to identify the
   cause; it is not grounds to drop results or reduce the matrix.

P3 actual guest, full P3, P4–P6, canonical independent regeneration and final
production/release decisions remain unfinished. No new architecture exploration
or compatibility profile is introduced by this first source candidate.
