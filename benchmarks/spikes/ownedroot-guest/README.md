# Owned-root actual-guest spike

The current review is [snapshot-owned-root-guest.md](../../../docs/reviews/snapshot-owned-root-guest.md).
This experiment branch is not merge/release approval. macOS arm64 and bounded
Ubuntu24.04 x86_64 checks passed; measurements remain macOS-only.

Before builds, commit exact inputs and verify `scripts/git_identity.py inspect HEAD`.
Use `.agents/skills/experiment-workspace/SKILL.md` to prepare a disposable workspace
with 8 GiB owned / 20 GiB free bounds. Commands take the workspace directory,
not its worktree. `check.py` requires Go1.26.8 in the existing verified toolchain;
use Python3.14 + pytest for Python/source checks and official regeneration.
On Ubuntu the runner finds Go on PATH (or `OWNED_ROOT_GO`); version remains
strictly Go1.26.8. Seed its ordinary module cache with `go mod download` before
checks copy those verified inputs to the private workspace.

```sh
python3 benchmarks/spikes/ownedroot-guest/check.py focused --workspace /path/to/workspace
python3 benchmarks/spikes/ownedroot-guest/check.py integration --workspace /path/to/workspace
python3 benchmarks/spikes/ownedroot-guest/check.py public --workspace /path/to/workspace
python3.14 benchmarks/spikes/ownedroot-guest/check.py python --workspace /path/to/workspace
python3.14 benchmarks/spikes/ownedroot-guest/check.py mapped --workspace /path/to/workspace
python3.14 benchmarks/spikes/ownedroot-guest/check.py source --workspace /path/to/workspace
python3.14 benchmarks/spikes/ownedroot-guest/check.py regenerate --workspace /path/to/workspace --guest-dir /path/to/fixed/guest
python3 benchmarks/spikes/ownedroot-guest/measure.py --workspace /path/to/workspace
python3 benchmarks/spikes/ownedroot-guest/corruption.py /path/to/workspace
python3 benchmarks/spikes/ownedroot-guest/collect.py /path/to/workspace
python3 benchmarks/spikes/ownedroot-guest/analyze.py
```

Use `scripts/experiment_disk.py` or the workspace runner with a bounded timeout
for builds/measurement. Complete correctness builds before timed comparison;
do not run concurrent build/test work during measurement.
`measure.py` benchmarks HEAD: reproducing published numbers requires exact
candidate `11fa56bd8f7c7180299d3235b586a0bc18004768`, not the later report commit.
Its sole observer modification adds final Go resource counters to the same
harness in both exact-source clones. All 46 ordinary + 4 diagnostic trials,
binary/source identities and outliers are saved in evidence/measurement.

The recorded guest was downloaded from release verify run 38959312232 artifact
`release-generated-inputs-7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`, then its Wasm,
provenance and pinned input identities were checked. `reused-guest.json` records
that reuse; it is not a new guest build. Official regeneration and 99-file
comparison are recorded separately.

The fault probe deliberately bypasses ownership with private-byte access at
TakeRoot→OwnRoot, never after public Snapshot returns. Only a special build tag
and a single saved host-source overlay connect it. Context-scoped selection,
one healthy/one corrupt subprocess, explicit timeouts; no production hook or
injection environment switch. The result characterizes error detection latency,
not the incidence or coverage of all possible corruption.

`collect.py` removes personal paths and records both original and stored hashes.
`analyze.py` replays saved evidence only, including mapping cleanup, positive
counter controls, ordinary/diagnostic separation and exact failure outcomes.
After preserving commits/evidence, finalize and clean the disposable workspace;
retain no compiler/module/download/generated caches.

## Bounded native Ubuntu CI

`.github/workflows/owned-root-native.yml` runs on pushes to candidate branch
`experiment/snapshot-owned-root-guest`.
It uses Ubuntu24.04 x86_64, Go1.26.8, Python3.14 and the same focused/source,
Go lifecycle, Python shared-host/mapped and special-tag corruption checks as macOS.
Artifacts record the exact candidate SHA and stage receipts even on failure.
No performance claims, guest rebuild, independent regeneration repeat, full
Qualification, main adoption or publication is part of this CI submission.
CI owns execution; submission is not a PASS or adoption decision.

Ubuntu run38998771860 passed on source `c2a7664bc2cf5b62a5931bf521f060c4fe11a4b8`.
`ubuntu-evidence/summary.json` verifies receipt identities/exits and records
per-file original/stored hashes; it is separate from the earlier macOS cohort.
The evidence-only `experiment/snapshot-owned-root-ubuntu-review` branch changes
no runtime code and submits no new CI. The candidate branch retains c2a7664.
