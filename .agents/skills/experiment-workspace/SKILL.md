---
name: experiment-workspace
description: Prepare, disk-guard, finalize and safely clean disposable mariamem benchmark or experiment workspaces. Use when organizing fan-out scratch or cleaning completed experiment output; does not authorize new experiments or product decisions.
---

# Experiment workspace lifecycle

Read `AGENTS.md`, `docs/project-status.md` and `docs/experiment-workspace.md` from
the repository root. This skill performs mechanical storage management only.
Architecture, experiment selection and product decisions remain human/model work.

1. Audit `git status --short`, `git worktree list`, disk usage and available space.
   Identify active jobs. Run `python3 scripts/experiment_workspace.py cleanup`
   in default dry-run mode. Keep caches, evidence and REVIEW items intact.
2. For an explicitly authorized experiment, prepare a fresh named workspace with
   `prepare <name> --branch experiment/<name> --min-free-gib <reserve>` and
   `--budget-gib <budget>`. Choose thresholds from the requested fan-out and
   expected build size. Never initiate a benchmark merely to clean storage.
3. Use `run --timeout <seconds> <name> -- <authorized-command>` so disk limits
   and child-group shutdown apply. Put reproducible output in the exported temp
   path; put compact final evidence/checksums and selected profiles in evidence.
   Keep reusable expensive caches outside the owned workspace.
4. After work ends, preserve compact evidence and commit unique source. For jobs
   supervised outside the runner, verify inactivity before `finalize <name>`.
   Review `cleanup --name <name>`. Apply only eligible completed scratch with
   `cleanup --name <name> --apply` within the user's authorized cleanup scope.
5. Verify retained evidence/checksums, Git branch history, `git worktree list`
   and disk usage after cleanup. Report reclaimed bytes, retained paths and
   REVIEW/manual items. Leave uncertain legacy raw data untouched.

Do not force worktree removal, delete branches/caches, create synthetic receipts
for old directories, or treat failure as permission to discard unique evidence.
