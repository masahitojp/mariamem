---
name: release
description: Prepare and submit a mariamem release when the human explicitly requests release <version>; never choose the version.
---

# Release mariamem

Read `AGENTS.md`, `docs/project-status.md`, and `docs/releasing.md` from the
repository root. They own release policy; this skill only prepares and hands off.

Require an explicit human version, e.g. `release v0.1.0-alpha.5`. Missing version
means stop and request it; never infer, choose, or recommend a next version.
The request authorizes preparation, commit, push, and release workflow dispatch
as one transaction. Do not ask for a second publication approval.

1. Before edits, run `python3 scripts/release_prepare.py preflight <version>`.
   Stop on failure. This checks project-supported version syntax, clean tree,
   main/origin identity, fast-forward remote history, and unused tag/release.
   Inspect any unpushed history; include only history belonging to this release,
   never silently include unrelated commits. Do not reset/discard dirty changes.
2. Update only the five semantic components in `python/mariamem/_version.py`
   to the supplied version. Derive Python spelling using that module, not a
   second editable version field. Update current-release examples in `README.md`,
   `docs/go.md`, `docs/python.md`, and the intro of `docs/releasing.md`;
   preserve historical records/evidence. Existing `check_version.py` owns checks.
3. Prepare tracked `release/NOTES-<stage>.<serial>.md`, matching the project style
   in `release/NOTES-alpha.4.md`, with a heading containing the exact requested
   tag. Summarize actual changes; do not invent product/performance claims.
4. Run `python3 scripts/release_prepare.py submit <version>`. It restricts the
   diff to preparation files, invokes `scripts/verify.py check`, commits that
   explicit file set, pushes normally, verifies exact remote source SHA, and
   dispatches existing Release CI with `mode=full`, `operation=release`.
   Stop on failure; never force-push or silently retry a possibly submitted run.
5. Once submit succeeds, immediately report the returned version, candidate SHA,
   and workflow URL. Do not poll, wait, or supervise CI.

Do not build artifacts, manage candidate hashes, create tags/releases, upload
assets, use Docker/Tart, or recreate Release CI locally. CI owns build,
acceptance, READY, publication, and public smoke. If submission returns no run
URL despite success, give the workflow page and stop; do not redispatch.

Return:

```text
Release submitted.
Version: <version>
Candidate: <sha>
Workflow: <url>

CI now owns build, acceptance, publication, and public smoke.
If it fails, invoke Codex again with that workflow run.
```
