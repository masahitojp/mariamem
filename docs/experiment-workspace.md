# Disposable experiment workspace

**Preserve knowledge, not workspace state.** Experiment workspaces are disposable
by default, and recreatable data normally goes away when its task ends. High
regeneration/download cost is not a KEEP reason. The recent local cleanup
reduced 59.64 GiB to about 0.89 GiB while retaining source/history, refs and compact
results; unlimited cache/build retention defeated the former policy.

This is mechanical development tooling, not runtime behavior or experiment
selection. Use one workspace per branch, put build/temp output in its `temp/`,
and keep final knowledge in `evidence/`. Shared caches can live outside the
workspace for concurrent use, but that location does not grant permanent KEEP.
The only temporary exception is a task actually using them.

## Prepare, run and finish

Completion includes cleanup:

`prepare → run → collect → reduce → commit/push → cleanup → verify`

```sh
python3 scripts/experiment_workspace.py cleanup --json
python3 scripts/experiment_workspace.py prepare trial-a \
  --branch experiment/trial-a --min-free-gib 8 --budget-gib 2
python3 scripts/experiment_workspace.py run --timeout 900 trial-a -- <authorized-command>
# Reduce results, commit/push useful changes, and confirm no task still uses it.
python3 scripts/experiment_workspace.py finalize trial-a
python3 scripts/experiment_workspace.py cleanup --name trial-a --json
python3 scripts/experiment_workspace.py cleanup --name trial-a --apply --json
git worktree list
```

Replace the placeholder only with an authorized command. No cleanup starts an
experiment. An existing branch can be reused; a new branch starts at HEAD.
`run` options precede the name. `finalize` is for manually supervised or abandoned
work after checking inactivity; it must not override an active lock. For `run`,
`completed` means the process exited successfully, not that the experiment's
storage lifecycle is complete. `cleaned` records removal of owned scratch/worktree; experiment completion also
requires the post-cleanup retention check to have no unexplained debt.

The runner sets `TMPDIR`, `GOTMPDIR`, `MARIAMEM_EXPERIMENT_TEMP` and
`MARIAMEM_EXPERIMENT_EVIDENCE`. Save reports, CSV/JSON, input/source SHAs,
reproduction commands, checksums and selected small profiles in evidence. Git
preserves committed code; do not duplicate entire source trees to retain it.
If a result cannot be reconstructed from compact evidence and Git history,
preserve the missing unique information first, then delete the recreated tree.

Before large experiments, choose explicit disk budgets and free-space reserves.
The guard checks before spawning and while running, records peak owned usage
and minimum free space, and stops owned children on breach/interruption/timeout.
Failed jobs export/hash small knowledge and remove disposable temp. If source,
result preservation or child shutdown needs work, resolve the reported concrete
issue before claiming completion. Root/worker forced runtime termination is not
part of this storage tool.

Budgets are sampled limits, not filesystem quotas; rapid writes can overshoot.
Shared cache growth is outside the workspace budget but reduces available disk.
Monitor it, bound concurrent jobs, and remove cache after its final user exits.
Use a quota if a strict write ceiling is needed.

## KEEP / DELETE / REVIEW

| Class | Required basis / next action |
| --- | --- |
| KEEP | Explicit unique value or active ownership: unique source/history/results, compact durable evidence, active task/release inputs |
| DELETE | Default for recreatable caches, downloads, generated/build/copied source, temp/staging, duplicate artifacts and completed worktrees |
| REVIEW | Inspected concrete source/history/result/ownership issue, with reason code/path; preserve compactly and delete the large workspace |

Rebuilding is expensive, downloading is inconvenient, maybe useful later, large,
and unclear are invalid KEEP reasons. An unfamiliar directory is inspected,
not automatically assigned perpetual REVIEW. A malformed receipt or unsafe path
is an inspection error; it does not prove unique information exists.

Default cleanup is read-only. `--json` emits `classification`, `code`, `reason`,
`path`, `automatic`, size, all `retained_large_paths` with their KEEP reasons,
and cleanup debt. Policy classification and deletion
permission are distinct: shared/unmanaged caches can be DELETE candidates while
`automatic=false`. Confirm ownership, current use, relevant history and unique
files before manually removing them within the authorized cleanup scope. The
helper never fabricates receipts for old trees or recursively deletes arbitrary
unmanaged paths. `--root <real-path>` before the subcommand selects an explicit
root such as a parent workspace's build directory; source roots and symlink
ancestors are rejected.

For completed owned worktrees, inspect status and untracked/ignored files,
confirm commits are pushed **or otherwise preserved** by retained refs/bundles,
export unique evidence, then use `git worktree remove` without force. Branch/tag
history remains. Dirty worktrees are protected with a `unique_source` REVIEW;
preserve a patch/commit first, then resolve it. A clean worktree is normally
DELETE, including ignored recreatable build caches. Tracked benchmark tooling is
source, not a cache merely because its directory is named `tools`.

Small unique files in owned scratch are copied and hashed before deletion.
Committed worktree reports/source already in retained Git history are not
copied again. Known compiled output is disposable. Larger unrepresented
source/results need compact preservation or an inspected reproduction record;
size alone is not a long-term KEEP justification. An export failure stops
removal. No source/history/release correctness gate is weakened.

## Reproduction and retention records

A workspace can contain `cleanup-policy.json`, outside disposable `temp/`:

```json
{
  "reproducible": {
    "temp/generated": {
      "reason": "generated module; useful converter changes already committed",
      "command": "converter --guest pinned.wasm --output temp/generated",
      "inputs": "guest SHA256 and converter/source commit recorded in evidence/input.json"
    }
  },
  "keep": {
    "evidence": {
      "kind": "durable-evidence",
      "reason": "canonical generation CSV, report, hashes and selected profiles"
    }
  }
}
```

Declare reproducible paths only after checking actual contents, recipe and input
identities. A declaration cannot bypass dirty worktree or nested unpreserved Git
history checks. Do not include unique measurements or user edits in a broad
reproduction declaration. If needed, first move/hash missing knowledge to
`evidence/`, commit it, or preserve a verified patch/bundle/small archive.
`keep` on `evidence/` does **not** retain unrelated temp/build state.
KEEP kinds are `unique-source`, `unpushed-history`, `active-task`, `unique-results`,
`durable-evidence`, or `active-release`, with a nonempty specific reason.
Cache cost is not a KEEP kind. Paths must stay inside the workspace.

After apply, every remaining file/directory over 1 GiB needs its own `keep` entry
and specific justification (including `.` for an aggregate workspace).
The helper lists unqualified paths as `cleanup_debt` and exits 2, not a clean
completion. A parent explanation must not hide large cache children. A necessary
500 MiB canonical CSV may remain; justify why reduction loses observations and
prefer a compact format. Huge ordinary raw logs and full build trees are not
canonical evidence by default.

For caches outside owned scratch, check all current users before manual removal.
If a concrete source edit/only-copy result is found inside a nominal cache,
preserve it first. Delete recreatable remainder; do not preserve an entire cache
because one small unique file was found. Local retention policy does not purge
hosted immutable release artifacts or evidence needed by an active release.

## Guard an existing script

```sh
python3 scripts/experiment_disk.py --work-dir build/experiment-work/trial-b \
  --min-free-gib 8 --budget-gib 2
python3 scripts/experiment_disk.py --work-dir build/experiment-work/trial-b \
  --min-free-gib 8 --budget-gib 2 --timeout 900 -- <authorized-command>
```

Python callers can use `DiskGuard` / `run_guarded` from `experiment_disk.py`.
The standalone guard stops owned children but does not delete files. The
workspace runner owns failure scratch cleanup; committing knowledge, normal
worktree cleanup and checking retained-vs-deleted state remain part of the
experiment's completion workflow.
