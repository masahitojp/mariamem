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

Keep verification proportional to the changed boundary. For experiment-workspace
skill/helper/docs/tests changes, run the relevant helper tests, skill validation,
touched Python tooling checks, affected public-source/boundary checks, and clean
diff/status checks. Do not run full `verify.py check`, Go runtime integration,
SQLAlchemy/GORM, Snapshot/Fork runtime acceptance, or broad release acceptance
unless a focused check identifies a concrete reason to expand scope. Before
expanding, explain the exact dependency from the changed files to that subsystem.

For documentation-only changes, inspect wording, references and diff/status;
do not rebuild or test unchanged runtime code. Report pre-existing user changes
separately rather than removing them to claim a clean checkout. This scope rule
does not weaken runtime-change or release gates when those boundaries are changed
or a release is explicitly requested.

Release CI responsibility and handoff:

The human decision is "release this candidate". Codex submits the exact candidate
to Release CI and hands off; CI owns build, acceptance, and guard evaluation.
The intended publication path is NOT READY → stop; READY → tag, publish, and
post-publication smoke. Starting that release workflow is the publication
approval for the transaction; there must be no second approval gate after READY.
The workflow defaults to `operation=verify` (no publication). Explicitly selecting
`operation=release` authorizes READY → exact tag, release, and public smoke.
Normal operations are only `verify` and `release`. CI automatically selects
valid exact-SHA READY reuse or full qualification in the same run; a preceding
verify is optional, never a required release step. Recovery modes/run IDs are
advanced overrides, not part of the normal human ceremony.

Codex submits work to CI; it does not supervise CI. After successful submission,
return the run URL, candidate SHA, and operation, then stop. Do not poll, wait, or
report elapsed build time. Re-enter only for a human status request, requested
failure/NOT READY diagnosis, or an unexpected engineering decision.

For an explicitly versioned release request, use the repository-local
`.agents/skills/release/SKILL.md` (`$release vX.Y.Z-alpha.N`). It prepares and
submits the existing workflow; it never chooses the release version.

0.2 architecture experiments use `experiment/<short-purpose>` branches (for
example `experiment/wasix-continuation` or `experiment/storage-overlay`). Main
remains the stable product/measurement baseline: production behavior,
instrumentation, benchmarks, diagnostics, analysis and low-risk tooling.
Exploratory engine patches, runtime/VFS changes, cloning and disposable
prototypes belong on experiment branches, which are not assumed merge-ready.
Before integration, summarize hypothesis, correctness, benchmark results,
semantic differences, platform limits, upstream patches and the decision
(reject / continue / integrate). Integrate the smallest production-quality
change rather than blindly merging exploratory history.

Keep `guest/source.patch` canonical. Temporary guest changes belong in
`guest/experimental.patch` on the experiment branch; preparation records it
separately and release provenance rejects it. See `docs/development.md` for
measurement artifact reuse and experiment preparation.
