# Experiment storage lifecycle — 2026-10-04

This follow-up reclaimed **2.163 GiB net** from the full local workspace. The
canonical repository decreased from **11.466 to 9.300 GiB**; its `build/` decreased
from **10.555 to 8.390 GiB**. The outer work directory increased slightly from
**11.220 to 11.223 GiB** because the new checksum/evidence archive was retained.
The protected outer cache stayed **1.951 GiB**.

The preceding cleanup had already removed 13 completed registered worktrees
using Git and reclaimed 7.755 GiB. Across both stages, the full workspace went
from 34.587 to approximately 24.669 GiB: **9.918 GiB net reclaimed**. These are
allocated-block measurements (`du -sk`), not a promise about filesystem free
space or APFS snapshots.

## Removed safely

- Five expanded source copies in `build/direct-consumer-{decision,final}/source`
  and `build/distribution-decision/{direct,embedded,external}/source`. Every file
  matched its retained module ZIP; ZIP and per-file SHA-256 records were saved.
- Twenty-six named executables from completed consumer, distribution, benchmark
  and converter checks. Measurements, logs and executable hashes were retained.
- Two obsolete environments: `build/sqlalchemy-dogfood/venv` (Python 3.9) and
  `build/v03-acceptance/venv`. Python configuration and distribution metadata were
  archived; the primary `.venv` and current SQLAlchemy `py314` environment remain.

The current stage removed 33 exact targets. It found only the canonical Git
worktree; `git worktree prune --dry-run` found no stale registration. Local and
pushed experiment refs were inspected and retained, including five unpublished
v0.4.1 branches. No experiment was resumed.

## Preserved and manual review

All committed source, reports, compact measurements, checksums, selected unique
profiles and previous evidence archives remain. Expensive Go/module/tool caches,
pinned compiler source, dependency/license closure, guest/fixed-reference inputs,
and release/distribution artifacts remain available.

Uncertain source remains under outer work: `*-owned-source`,
`v04-canonical-clean-checkout`, `delivery-traced-source`, `cleanup-check-source`,
the temporary final-preparation source, preallocation sources in `fanout-v04`,
and the prepared build source in `v04-integrated`. The earlier audit estimated
these source REVIEW items at 4.109 GiB. Public `build/source`,
`build/gorm-preparation`, the remaining `build/wasm2go-spike` translation input,
and mixed `build/distribution-decision` caches/artifacts also require individual
review before removal. They are not automatically eligible for the new tool.

[Compact inventory and measurements](experiment-cleanup-20261004.json) records
all removed paths, preserved groups, and every remaining top-level directory
over 64 MiB. The full local archive is
`../../build/mariamem-work/storage-lifecycle-20261004/`; it contains the exact
before/after measurements, per-file source/ZIP hashes, environment metadata,
selected measurement copies, classification and deletion journal. Earlier
worktree/source preservation remains in sibling `storage-cleanup-20261004/`.

Future work uses the mechanical
[workspace lifecycle and disk guard](experiment-workspace.md), also documented
in `.agents/skills/experiment-workspace/SKILL.md`. Unknown old data remains manual
REVIEW; the tool's ownership receipt is created only for fresh workspaces.
