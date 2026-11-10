# Candidate-only binding review

Guest origin: c7b60a1d51512af44718025b10800e0b3c9130f2, CI42792328050.
Its successful Wasm and fixed converter were used locally to extract full bodies.
Worker Fn153/Fn214 differ only by recorded static addresses relocating -1024;
Fn131 is identical. CRC validator Fn18145 relocates to Fn18142; the full token
stream differs only in recorded function IDs and data addresses. Branches,
comparisons and computation blocks are unchanged. One diagnostic format-string
address moves +18; its NUL-terminated bytes match the canonical data exactly. The CRC table is byte-identical
and uniquely occurs at data offset7179904. review.json records every difference.
No fuzzy match or relocation adjustment is used at installation: whole-function
hashes, exact guest/data SHA and table checks remain mandatory. The canonical
bindings remain unchanged; selection applies only to the explicit development
candidate with the reviewed identity. New fixtures are retained in full.

The dev workflow reuses the successful immutable guest; no C/engine rebuild is
needed for binding-only fixes. verify_source_origin permits only this exact CI
workflow additionally to the pre-existing host-stage/docs/tests set, checks its
historical bytes against the origin commit, and rejects engine/toolchain/input
changes. New guest SHA acceptance is not inferred from the workflow filename.

CI failed before any SQL. This fixes installation prerequisites, not a claim of
actual-guest SQL PASS. Runtime validation remains the next CI operation. Binding
review is real recurring maintenance and must be counted in#128, not hidden as
an output-adapter saving.

Local checks: 38 candidate/canonical worker+CRC tests and21 development-origin
checks PASS. The old canonical binding modules were not edited. This CI repair
reuses an expiring artifact from the named run; it fails closed if unavailable.
It is not a permanent preparation dependency. A later clean qualification must
rebuild from the recorded original source/toolchain instead of relying on it.
