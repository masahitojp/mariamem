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
