# AGENTS.md

For project history, architectural decisions, release philosophy, and roadmap
context, read `docs/project-status.md` before planning substantial changes.

Development cycle:

Explore → Challenge → Human decision → Implement → Verify

Do not mix architectural exploration and full implementation in one task unless
explicitly requested.

Use small spikes to reduce uncertainty before expensive architectural changes.

Mechanical verification belongs in deterministic scripts and CI where possible.

Use `docs/development.md#local-verification` to choose the canonical check for
the changed boundary; release acceptance and benchmarks are separate.

Release CI responsibility and handoff:

The human decision is "release this candidate". Codex submits the exact candidate
to Release CI and hands off; CI owns build, acceptance, and guard evaluation.
The intended publication path is NOT READY → stop; READY → tag, publish, and
post-publication smoke. Starting that release workflow is the publication
approval for the transaction; there must be no second approval gate after READY.
The workflow defaults to `operation=verify` (no publication). Explicitly selecting
`operation=release` authorizes READY → exact tag, release, and public smoke.
`operation=dry-run` validates publication inputs without remote writes.

Codex submits work to CI; it does not supervise CI. After successful submission,
return the run URL, candidate SHA, and mode, then stop. Do not poll, wait, or
report elapsed build time. Re-enter only for a human status request, requested
failure/NOT READY diagnosis, or an unexpected engineering decision.

For an explicitly versioned release request, use the repository-local
`.agents/skills/release/SKILL.md` (`$release vX.Y.Z-alpha.N`). It prepares and
submits the existing workflow; it never chooses the release version.
