# Disposable experiment workspace

This is development tooling only. It does not start benchmarks, choose a product
design, or change runtime behavior. Use one workspace per fan-out branch, and
keep generated/build output in its owned `temp/` directory. The default root is
`build/experiment-work`. Shared expensive toolchains, `GOCACHE`, `GOMODCACHE`,
downloads and `mariamem-cache` stay outside each workspace.

## Prepare and supervise

From the repository root:

```sh
python3 scripts/experiment_workspace.py cleanup
python3 scripts/experiment_workspace.py prepare trial-a \
  --branch experiment/trial-a --min-free-gib 8 --budget-gib 2
python3 scripts/experiment_workspace.py run --timeout 900 trial-a -- <command> <args>
```

Replace the command placeholder with the explicitly authorized experiment script.
No experiment is run by prepare or cleanup. Omit `--branch` for a scratch-only
job. An existing experiment branch can be used; a new one starts at `HEAD`.
Raise the budget before preparation if a full source checkout itself exceeds it.
Options for `run`, including `--timeout`, precede the workspace name.

The runner sets `TMPDIR`, `GOTMPDIR`, `MARIAMEM_EXPERIMENT_TEMP` and
`MARIAMEM_EXPERIMENT_EVIDENCE`. Adapt experiment commands to write bulky generated
sources and binaries to the first owned path; save final reports, compact
JSON/CSV, checksums and selected profiles to the evidence path. It retains
`evidence/console.log`, command, source SHA, exit status and sampled disk usage.
Existing Go cache settings are inherited; the tool does not clear caches.

Preflight checks available space and the entire owned workspace's allocated
blocks. During execution the guard repeats these checks, and stops the owned
process group on a breach, interruption or timeout. Descendants must remain in
that group; detached jobs need separate supervision. On failure it exports
compact evidence from temp, verifies SHA-256, and removes disposable temp where
safe. Source/worktree and evidence remain available for review.
If child-group shutdown cannot be confirmed, scratch is retained as REVIEW;
verify all children have stopped before manually finalizing and cleaning it.

The budget is a sampled limit, not an OS quota: a rapid write can exceed it
between samples. Shared cache writes count against free space but are outside
the per-workspace budget. Keep sufficient headroom; use a filesystem quota when
a strict upper bound is required. Parallel jobs share free space, so set each
budget and free-space reserve with the planned fan-out in mind.

## Finalize and clean

Commit source changes to the experiment branch, preserve compact evidence and
record any required release inputs before cleanup. Verify no job still uses the
workspace. For manually supervised work, mark it complete only after that check:

```sh
python3 scripts/experiment_workspace.py finalize trial-a
python3 scripts/experiment_workspace.py cleanup --name trial-a
python3 scripts/experiment_workspace.py cleanup --name trial-a --apply
git worktree list
```

Cleanup is read-only by default. `--apply` removes only recorded completed/failed
`temp/` and registered clean worktrees with a retained local branch reference.
It uses `git worktree remove` without force; branch history is retained whether
or not it has been pushed. Push policy remains the experiment owner's decision.
Reports/checksums and small selected profiles are copied and hashed before
removal; committed source remains in Git. Evidence archives and receipts stay.
Do not use `finalize` to override an active process: the runner holds a lock.

Classification is `CACHE` (keep), `EVIDENCE` (keep), `KEEP` (prepared/running),
`DISPOSABLE` (eligible), or `REVIEW` (manual). Dirty/unregistered worktrees,
unknown ignored files, linked paths, nested caches/Git checkouts, and evidence
over 8 MiB require review. For a large selected profile, preserve and verify it
manually outside temp before retrying cleanup. Failed jobs with such data retain
their scratch. Unknown legacy paths never become eligible merely because they
are old; do not fabricate an ownership receipt for them.

`--root <real-path>` before the subcommand selects an explicit alternate root,
including a parent workspace's `build/mariamem-work`. Legacy contents there will
be reported for review. Repository source roots and `mariamem-cache` are refused.
Uncertain raw data and required release artifacts should be kept until their
owner confirms they can be reproduced or safely archived.

## Guard an existing script

Preflight only, or wrap an explicitly requested command:

```sh
python3 scripts/experiment_disk.py --work-dir build/experiment-work/trial-b \
  --min-free-gib 8 --budget-gib 2
python3 scripts/experiment_disk.py --work-dir build/experiment-work/trial-b \
  --min-free-gib 8 --budget-gib 2 --timeout 900 -- <command> <args>
```

For Python callers, import `DiskGuard` and `run_guarded` from
`scripts/experiment_disk.py`; call `guard.check()` before launching and at phase
boundaries if not using the wrapper. This standalone guard stops owned children
but does not delete files; the workspace runner owns failure cleanup. Errors
print measured usage and guidance to inspect cleanup dry-run before applying it.
