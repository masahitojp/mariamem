# mariamem v0.4.7 — Upstream wasm2go migration (candidate)

- Generation uses pinned goccy/wasm2go upstream plus nine purpose-specific,
  mariamem-managed patches. The shibukawa converter fork is no longer a build
  dependency; attribution for selected fork-derived compatibility fixes remains.
- The MariaDB Wasm guest is unchanged from v0.4.6. Memory32 bounds/traps, shared
  memory, cooperative worker cleanup and mmap ownership retain their existing
  contract. Public Go/Python APIs and persisted Snapshot format are unchanged.
- Qualification compares the unchanged v0.4.6 guest with this translator using
  the same product scenarios, including SQL/transaction oracles and memory/
  cleanup observations. This release does not claim a performance improvement.

Minimum Go remains 1.26.0; mysql client dependency remains v1.9.3. Platform scope
remains macOS 15+ arm64 and Ubuntu 24.04 x86_64. Go1.27 consumer compatibility
is checked separately from canonical Go1.26.8 qualification.

Existing limitations remain: full generated shared-memory race freedom and
forced cleanup of non-cooperative execution are not guaranteed. Zero-length
bulk-memory bounds have a pre-existing documented edge case; this migration
must not be described as full WASM conformance. MariaDB stable-guest migration
belongs to v0.5.0; no guest, VFS or Snapshot performance optimization is included.

Candidate only: no publication approval or completed cross-platform acceptance
is implied by these notes. See the migration review for actual PASS/FAIL/PENDING.
