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

Release CI handoff:

Codex submits work to CI; it does not supervise CI. After successfully dispatching
long-running release work, return the run URL, candidate SHA, and mode, then stop.
Do not poll, wait, or report elapsed build time. Re-enter only for a human status
request, requested failure/NOT READY diagnosis, or an unexpected engineering
decision. Short feedback loops while fixing a known CI issue are allowed.
CI owns build, acceptance, and READY evaluation. Publication approval is a
separate future gate; READY does not currently request approval or publish.
