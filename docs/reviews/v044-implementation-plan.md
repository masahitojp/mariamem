# v0.4.4 implementation plan

Accepted product decisions, not a new design proposal. Main remains unchanged.

- Main input: `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`.
- Released performance input: `dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20` (v0.4.3).
- Proven spike input: `730b64db7059d0374e2e00680416de77cdb346eb`;
  review/evidence: `09443d4de999b833cddc2ca536d43f9120130c79`.
- Work branch: `experiment/v044-product-contract`.

## Implementation boundaries

1. `internal/snapshot`, a small `internal/prepared` descriptor representation,
   `snapshot.go`: validate acquisition, retain unlinked read-only descriptors,
   pin startup against Close. Copy imports and explicitly persisted captures;
   adopt only newly created private temporary captures.
2. `internal/host`, `internal/guest`, `internal/generatedgo/runtime_instance.go`,
   handwritten `code/base`: pass those exact descriptors to private mappings.
   Preserve guest, child MemFS/growth and worker-join-before-unmap semantics.
3. `cmd/mariamem-host`, Python lifecycle/Snapshot modules: internal descriptor
   handoff, guest identity at import, no manager, no path reopening for handles.
4. Python `load_snapshot`, fixture removals, metadata surface cleanup and affected
   consumers/tests. Preserve constructors and path/handle startup. Persistence is
   selected at capture: Python `snapshot()` is temporary and `snapshot_to(path)`
   persists. Replace the old positional `snapshot(path)` without an alias or a
   later save/persist method. Go retains idiomatic `SnapshotOptions.Destination`.
5. After stable behavior, compact README/language guides, current architecture,
   continuing decision document, current project status and migration notes.

## Verification dependencies and order

- Pure ownership/manifest and mapping tests first; focused handwritten races.
- Mapping and descriptor-lifetime changes directly affect SQL isolation and
  filesystem semantics. Run Go/Python integration including DML/DDL/growth,
  transactions, generations/orders/parallel siblings, import corruption and
  source deletion, Close races and startup/partial failure cleanup.
- Language/fixture changes affect installed-wheel consumers; run existing
  serial/xdist acceptance with independent per-test state.
- CI qualifies macOS arm64 and Ubuntu x86_64. After correctness gates, measure FD
  scaling and only then serial performance comparisons with exact v0.4.3,
  minimal/10/100 MiB, Fork-many and bounded realistic/parallel suites. No
  competing benchmark processes; scan SQL is distinct from ready timing.
- Preserve source SHAs, checksums, reduced CSV/JSON, commands and a Human Review
  report. Remove worktrees/build/cache/temp; no release or main merge.

No cache manager, shared mutable fixture, new run-wide fixture, rename,
diagnostics API, guest upgrade or unrelated race redesign is authorized here.
