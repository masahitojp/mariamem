# Issue65 — three compatibility fixes, isolated candidate

Human selection,2026-11-07: fix the three demonstrated boundaries and incorporate
published0.6.2 main. Main `0c4e75dc2c21421a59d04661efd72a1f58efecaa` is merged;
shared release runtime was already0.6.2. Keep the release documentation cleanup
rather than restoring old release-pending records. [Issue65](https://github.com/masahitojp/mariamem/issues/65)
owns current work. No native-path adoption, release or performance claim.

## Local native result, Linux pending

macOS arm64 native execution at tooling source_commit
`fd6d12f723cf03abcb7314b8c0290170d4c36765` passes all22 lifecycle cases and
all7 compatibility groups/88 observations, with the original6 mismatches resolved.
The per-connection FOUND_ROWS control, focused Live endpoint tests, actual
worker-peer boundary, selected-binding negative controls and21 canonical
installer tests also pass. Focused `internal/live` race passes separately with
Go1.27.3; the native generated-Go binary uses Go1.26.10, CGO_ENABLED=0.
New guest SHA256:
`6956ea97ff4ad5fa7cc1b9617ec39ac0197c402c0bfa869469ec62a9ad6c3719`
(18,437,749 bytes, UNQUALIFIED). All three complete worker bodies retain their
previous native-profile hashes, now bound explicitly to this new guest.
[The immutable compact macOS reference](evidence/macos-reference.json) records
278 compiled Go/assembly/data files, the binary and exact template/binding pins,
and actual values for all6 previously failing observations. Linux must reproduce
that source set; differences are not accepted as metadata automatically.
The original NOT_READY receipt remains under the old observation report.

This is local scoped execution, not yet Linux acceptance. A later tooling-only
root Git trust preflight and source-reference guard do not change the compiled
runtime/template inputs; CI executes the final tooling SHA independently.

## Bounded changes

1. In the experimental MariaDB ACL patch, accept optional CLIENT_FOUND_ROWS before
   intersecting the client's capabilities. Do not add it to the greeting. Guest
   source_commit `8dc2b113394630c5be7127100903a359f994db45` includes main and this
   patch; a fresh build and exact worker-body binding review are required.
2. Native relay host reserves shared16-session capacity before guest OPEN. Keep
   reservations until native RETIRED (or confirmed disposal), not transport EOF.
   TCP rejects inline in its one accept owner through the fixed1s pre-login
   helper; Pipe permits one bounded rejection responder without starting SQL.
   Live has an optional bounded reject callback, called outside its mutex in the
   accept owner. The native fixture supplies the same fixed helper; nil retains
   the old route's behavior. Established streams still get no host serializer.
3. At an exactly full credit window the relay can read one observation byte or
   EOF. The existing guest input gate decides whether that byte is overflow or
   raced valid consumption/capture; it never appends above its queue limit.
   At most one such byte is outstanding before credit/failure. Do not poison a
   successful capture based on a stale host notice or inspect MySQL headers.

The ordinary command/result path remains opaque. Session generation and the
atomic SQL gate stay in guest; this is not whole-controller relocation.
Canonical `guest/source.patch` and generated production source stay unchanged.
`internal/live`'s optional rejection boundary and its test are isolated experiment
changes, staged explicitly; public native-route wiring is not added.

## Source and correctness boundary

Guest and checked host base both use8dc2b113. Tooling supplies inventoried host
main/Live/endpoint overlays and tests on top, so guest provenance is checked
against its exact clean source, not an arbitrary cross-commit receipt. The
assembler's explicit development binding comes from reviewed complete worker
functions; it must match the new guest and rejects wrong guest/full-body hashes.
Never refresh the pin automatically in CI. Historical tools/templates/receipts
and the six original mismatches remain intact.

The same14 capture/protocol plus8 Live cases and the same7 compatibility groups
must execute without changing expectations. An added per-connection control
checks FOUND_ROWS false -> true -> false; greeting and alias/RESET/LONG_DATA
oracles remain the original ones. The changed Live endpoint has an actual
localhost capacity callback test proving Status/existing relay remain usable,
no extra backend, and no generation change. Its full focused package is run.
The actual generated-worker boundary control and selected-binding negative
controls remain required. Existing21 canonical installer tests retain their
original fixture attribution; they are not proof of the new native binding by
themselves.

A new guest changes generated code. Original274-file equality to the old guest
is not an acceptance oracle for this candidate. Record a new source inventory,
new binary, exact staged inputs and actual per-platform execution. Prior
macOS/Linux/Live receipts remain scoped to their original guest.

Initial envelope for this selected fix:2h active/tooling30min, local guest12GiB/
free12GiB, separate host12GiB/free12GiB, at most one remaining heavy CI submission
in the current two-run compatibility campaign. Local builder uses the fixed
Linux-arm64 image/LLVM23 development recipe with2CPUs/6GiB and3300s guard.
Inspect the new worker bodies before selecting the CI guest/binding pins.

No full profile/output/large-aggregate/client/race/performance/release acceptance
is claimed from these three fixes. Preserve original failures and partial output.
All SDK/build/converter/Go caches/binaries/container/worktrees are disposable;
retain compact receipts, identities, exact reviewed binding and logs. After CI
submission hand off exact SHA, URL and operation, then stop supervision.
