# Issue65 — three compatibility fixes, isolated candidate

Human selection,2026-11-07: fix the three demonstrated boundaries and incorporate
published0.6.2 main. Main `0c4e75dc2c21421a59d04661efd72a1f58efecaa` is merged;
shared release runtime was already0.6.2. Main later advanced to
`61973daa19b6f665d7342338c3252dd7af61fc90` with prepared UCA guest/data changes;
that commit is also merged and frozen for this task. The native guest/binding
and runtime proof are rebuilt on that main. Keep the release documentation cleanup
rather than restoring old release-pending records. [Issue65](https://github.com/masahitojp/mariamem/issues/65)
owns current work. No native-path adoption, release or performance claim.

## Frozen-main local native result

The merged prepared-UCA source now passes fresh macOS arm64 native execution at
tooling source_commit `d86f40aeee18121e7c33315e10607d747c2e07e1`:
22 lifecycle cases,7 compatibility groups/88 observations with zero mismatches,
both added FOUND_ROWS/UCA Snapshot/Fork controls, focused Live endpoint tests,
actual worker-peer boundary, both selected-binding negative controls and22
canonical installer tests. UCA input tests separately pass8/8 on this main.
Guest SHA256 `0531ff4f348670dd5e2065a4a25fe9012ed278bd346a12093b97ff1cdfdd67e9`
(21,192,194 bytes, UNQUALIFIED) has a newly reviewed complete-worker binding.
[The current immutable macOS reference](evidence/macos-reference.json) binds
279 Go/assembly/data files, templates, binding, binary and the six fixed actual
observations. Linux must reproduce this source set and execute the same cases.
The final reference/hash and documentation commits do not change the tested
runtime/templates. Linux acceptance is pending; there is no adoption or release.

The first local supporting-check attempts exposed reused scratch and an obsolete
21-test count after main added a22nd guard. Fresh per-control temporary output
and the frozen-main22-test expectation fix those tooling failures; the original
runtime expectations remain unchanged. Failed-attempt receipts are retained.

## Pre-UCA local native result (historical)

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
[The historical macOS reference](evidence/pre-uca-macos-reference.json) records
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
   source_commit `a1e3b8a0d7f3750e684610e273a28b802a7135d0` includes the frozen
   prepared-UCA main and this patch; the rebuilt guest has an exact complete-worker binding review.
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
Canonical `guest/source.patch` and generated production source track the frozen
main exactly; this experiment makes no independent edits to them.
`internal/live`'s optional rejection boundary and its test are isolated experiment
changes, staged explicitly; public native-route wiring is not added.

## Source and correctness boundary

Guest and checked host base both usea1e3b8a0. Tooling supplies inventoried host
main/Live/endpoint overlays and tests on top, so guest provenance is checked
against its exact clean source, not an arbitrary cross-commit receipt. The
assembler's explicit development binding comes from reviewed complete worker
functions; it must match the new guest and rejects wrong guest/full-body hashes.
Never refresh the pin automatically in CI. Historical tools/templates/receipts
and the six original mismatches remain intact.

The same14 capture/protocol plus8 Live cases and the same7 compatibility groups
must execute without changing expectations. An added per-connection control
checks FOUND_ROWS false -> true -> false. A new-main-dependent control checks
utf8mb3/utf8mb4 UCA comparisons and a UCA index after native Snapshot/Fork.
Greeting and alias/RESET/LONG_DATA
oracles remain the original ones. The changed Live endpoint has an actual
localhost capacity callback test proving Status/existing relay remain usable,
no extra backend, and no generation change. Its full focused package is run.
The actual generated-worker boundary control and selected-binding negative
controls remain required. The merged main’s22 canonical installer tests retain their
canonical fixture attribution; they are not proof of the new native binding by
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

Local reference collection is an explicit `record-local` stage, restricted to
macOS arm64 outside GitHub Actions. CI's runtime stage always uses the strict
immutable reference comparison; no environment variable disables it. The
UCA guest/binding/reference pins are selected from the fresh local execution.
The pre-UCA proof remains a separate historical source, not an equivalent-tree
claim for this new guest. Canonical UCA input tests pass8/8 on the merged source.

Prepared UCA changes initialization/Fork independently of wire. Future performance
attribution must compare legacy/native wire with the same frozen-main engine/UCA
inputs; a separate end-to-end comparison to published0.6.2 must name that engine
change. Do not attribute main's UCA benefit to native wire or infer a speedup from
these one-shot functional test timings.
