# Issue65 — native profile policy repair

Human authorization,2026-11-07: fix the three demonstrated native profile gaps.
[CI42274490597](https://github.com/masahitojp/mariamem/actions/runs/42274490597)
at ecfa4b15 completes38 observations:28 pass,10 mismatches, none missing.
[Earlier observations](../issue65-native-limits/README.md) retain their original
source/configuration failures; their missing output cases were resolved by this
second CI, not by changing guest identity or expectations.

The defects are OUT-command rejection/errno parity, TLS and missing PROTOCOL_41
rejection, and response max+1 continuation. PROCESS_INFO's following-PING failure
is secondary to its unexpected result set.40MiB text/prepared streaming, exact
0xfffffe packet payloads, input headers, Pipe full-window overflow/EOF and the
22-case/88-observation baseline pass on the old guest.

## Selected implementation

Keep the host relay opaque. In the experimental guest only:

- Check the already decoded command against the approved10-command allowlist
  before dispatch's command switch. Use native diagnostics/end_statement for
  ERR1235/42000 and normal subsequent commands; do not reset prepared state.
- Check raw lower handshake flags before capability intersection. Require
  PROTOCOL_41 and reject SSL; keep other unadvertised bits masked as before.
  Flush and wait for native output ACK on failed auth before native RETIRED can
  close the host transport. No host serializer or authentication feature is added.
- Check the logical NET output length before packet header/sequence/body writes.
  Reject payload>0xfffffe with native1153 diagnostics. Leave NET usable for the
  native error path. Existing output credits remain transport bounds; the guard
  imposes no aggregate/RSS/engine allocation bound.

A small header contains pure policy predicates, no protocol decoder/session state.
Canonical guest/source.patch and production generated source stay frozen on
main61973daa. Existing guest lifecycle, controller, capture gate, host relay and
capacity code remain unchanged. Prepared/ordinary SQL errors still come from
MariaDB. This is an experimental repair, not adoption or release.

## Verification and budget

Initial envelope:2h active work,30min measurement tooling, at most2 heavy CI
submissions; aim to submit once after local native evidence. Separate owned
builder/runtime workspaces12GiB each, free floor12GiB. Local tooling/output is
owned too. Use the fixed native-arm64 image,2CPUs/6GiB and a3300s build guard.
Source identity precedes builds. New guest, complete worker-body binding review,
source/binary/template inventories and fresh macOS execution are required before
Linux submission. Preserve old receipts; no automatic hash/binding refresh.

The policy unit check compares all256 commands to the declared fixture, all65536
lower handshake flag sets and seven output boundaries, plus guard placement and
auth-error ordering. It is not a WASIX/runtime proof.
Run unchanged22 lifecycle cases,88 old compatibility observations,38 remaining
limit observations, existing FOUND_ROWS/UCA controls, worker-peer/binding/installer
checks and new rejection-lifetime/session-preservation controls on the new guest.
No full client/profile, every command-specific bound, metadata/multi-result,
public integration, controller relocation, whole-program race or performance
claim follows. Save original failures and distinguish missing execution from a
contract mismatch. Cleanup SDK/cache/build/generated code/binaries/worktrees,
retain compact evidence, then hand off CI URL/SHA/operation and stop supervision.
