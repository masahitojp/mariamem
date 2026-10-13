# mariamem v0.5.0 — MariaDB 12.3.3 candidate

This candidate adopts one reproducibly built MariaDB 12.3.3 guest. The MySQL
handshake reports the running guest's `VERSION()` string. The public Go and
Python APIs, supported platforms and minimum Go version are unchanged.

The runtime keeps the v0.4.7 pinned goccy/wasm2go converter and adds bounded
correctness repairs for `fd_allocate`, zero-length bulk-memory bounds, exact-width
8/16-bit atomic accesses, timeout arithmetic, thread-ID exhaustion and worker
allocation lifetime. Generated Go, source, patch order, licenses and provenance
are tracked and independently reproduced.

Saved Snapshots from the previous guest are rejected by identity and must be
recreated from SQL or fixtures. Normal Snapshot/Fork semantics are unchanged.

The candidate's source and local checks are documented in the
[A–D integration](../docs/reviews/v050-ad-integration.md),
[correctness fixes](../docs/reviews/v050-correctness-fixes.md),
[access review](../docs/reviews/v050-semantic-audit.md),
[boundary repairs](../docs/reviews/v050-boundary-join-fixes.md) and
[J1 lifetime repair](../docs/reviews/v050-join-lifetime-fix.md).
Final native qualification and Product Validation are pending. These notes do
not claim release approval or publication.

The existing limits on forced cleanup of non-cooperative workers, full-guest
race-detector coverage and physical resource accounting remain. The bounded
current-guest investigation found no further identified access or ownership
correction after the listed repairs; it is not a claim of universal Wasm
conformance. Product Validation will assess the cost of the J1 lifetime owner.
