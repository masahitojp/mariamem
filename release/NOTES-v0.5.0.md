# mariamem v0.5.0 — MariaDB 12.3.3

This release adopts one reproducibly built MariaDB 12.3.3 guest. The MySQL
handshake reports the running guest's `VERSION()` string. The public Go and
Python APIs, supported platforms and minimum Go version are unchanged.

The runtime keeps the v0.4.7 pinned goccy/wasm2go converter and adds bounded
correctness repairs for `fd_allocate`, zero-length bulk-memory bounds, exact-width
8/16-bit atomic accesses, timeout arithmetic, thread-ID exhaustion and worker
allocation lifetime. Generated Go, source, patch order, licenses and provenance
are tracked and independently reproduced.

Saved Snapshots from the previous guest are rejected by identity and must be
recreated from SQL or fixtures. Normal Snapshot/Fork semantics are unchanged.

The source and checks are documented in the
[A–D integration](../docs/reviews/v050-ad-integration.md),
[correctness fixes](../docs/reviews/v050-correctness-fixes.md),
[access review](../docs/reviews/v050-semantic-audit.md),
[boundary repairs](../docs/reviews/v050-boundary-join-fixes.md) and
[J1 lifetime repair](../docs/reviews/v050-join-lifetime-fix.md).
[Both-native Qualification](../docs/reviews/v050-final-qualification.md) passed
for the tested runtime basis. The approved
[Product Verification](../benchmarks/v050-product-verification.md) passed its
SQL and cleanup checks. Timings were mixed, including an existing startup tail;
these results do not establish a general speed or allocation improvement.
Release CI must qualify the final integrated source before publication.

The existing limits on forced cleanup of non-cooperative workers and full-guest
race-detector coverage remain. The bounded current-guest investigation found no
further identified access or ownership correction after the listed repairs; it
is not a claim of universal Wasm conformance.
