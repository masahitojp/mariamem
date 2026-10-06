---
name: experiment-workspace
description: Prepare, budget, finalize and clean disposable mariamem experiment workspaces while preserving compact knowledge and unique user state. Use for experiment storage lifecycle; does not authorize new experiments or product decisions.
---

# Disposable experiment lifecycle

> Preserve knowledge, not workspace state. Keep evidence, not build residue.
> Experiment workspaces are disposable by default. Cache is disposable.

Read `AGENTS.md`, `docs/project-status.md` and [the workspace workflow](../../../docs/experiment-workspace.md).
Architecture and product decisions remain human/model work. This skill performs
storage mechanics within the task's authorized scope; it never starts a new
experiment merely to clean storage.

## Classification: KEEP needs a reason

- **DELETE** is the default for recreatable state: Go build/module/compiler and
  toolchain caches, downloads, copied/extracted source, generated/build trees,
  package/release staging, benchmark scratch, duplicate artifacts and completed
  clean worktrees. Cost, inconvenience and possible future usefulness do not
  justify KEEP. A cache in use by an active task is protected only until that
  use ends. Protect committed product source, not disposable generated copies.
- **KEEP** requires concrete unique value or current ownership: unique user
  changes, the only copy of unpushed history/results, compact durable evidence,
  demonstrably active experiment state, or files required by an active release.
  State the path and specific reason. Prefer commits/pushed refs, reports,
  CSV/JSON, checksums, small selected profiles, reproduction commands and input
  SHAs. Size is not evidence of importance.
- **REVIEW** is exceptional and temporary. Inspect first and name the actual
  source change, unpreserved commit, unique measurement or active-task ownership
  conflict. Record a machine-readable reason code and concrete path, then
  preserve that information as a commit/patch/report/checksum/small archive and
  delete the large tree. "Unknown directory" is an investigation action, not a
  REVIEW or KEEP reason. Invalid receipts/path permissions are inspection errors,
  not unique-value claims.

If compact evidence and Git history cannot reconstruct a result, preserve the
missing unique information first, then delete the recreatable workspace. Never
lose unique user changes, the only copy of history/results, or active task state.

## Completion includes cleanup

`prepare → run → collect → reduce to durable evidence → commit/push useful changes → cleanup → verify`

1. Audit Git status/worktrees, disk usage, free space and active processes/locks.
   Inspect default dry-run `python3 scripts/experiment_workspace.py cleanup --json`.
2. Before large experiments, set explicit `--min-free-gib` and `--budget-gib`
   on `prepare`. Use `run --timeout` to monitor free space/workspace growth and
   stop owned children on budget breach/failure. Put reproducible output in
   `temp/`, final knowledge in `evidence/`. Cache location does not confer KEEP.
3. Reduce results and preserve source/input SHAs, commands and checksums.
   Commit/push useful changes. Inspect untracked **and ignored** files; a clean
   Git status alone does not prove that evidence is preserved.
4. Confirm inactivity, then `finalize` manually supervised work. Run cleanup
   dry-run, resolve concrete REVIEWs and apply within the authorized scope.
   Use Git-aware worktree removal without force, retain relevant refs or a
   verified bundle, and remove completed worktrees. Shared/unmanaged DELETE
   candidates need scope/activity checks before manual removal; do not fabricate
   ownership receipts or broaden deletion to arbitrary directories.
5. Verify saved evidence/checksums, Git integrity/status/refs/worktrees and
   before/after usage. Enumerate **every remaining path >1 GiB** with a concrete
   KEEP justification. "Cache", "expensive", "maybe useful" and "unclear" are
   invalid. Resolve or report unexplained residue as **cleanup debt**, including
   failed jobs; process exit alone does not complete an experiment.

The helper exports small unique files before deleting owned scratch, respects
active locks and dirty Git state, and emits structured reasons. Explicit
reproduction/retention records and manual cleanup procedures are documented in
[the workspace workflow](../../../docs/experiment-workspace.md). Safety limits on
automatic removal do not turn recreatable state into KEEP.

## Examples

| Completed state | Decision |
| --- | --- |
| 20 GiB Go cache | DELETE after confirming its users stopped |
| 5 GiB generated build tree, committed source + checksums/report + recipe | DELETE |
| clean completed worktree | inspect ignored evidence/refs, then DELETE using Git |
| worktree with unique uncommitted patch | preserve patch/commit first, then DELETE |
| 500 MiB canonical benchmark CSV/report | KEEP only if that size preserves necessary observations; otherwise reduce further |
| unknown 4 GiB directory | inspect source/history/results/ownership; preserve unique information and DELETE recreatable state; do not park it as REVIEW |
