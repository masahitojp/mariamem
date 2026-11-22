---
name: create-issue
description: Draft and create a decision-driven GitHub issue (via gh issue create) with a clear user/maintainer outcome, current behavior evidence, scope boundaries, and explicit uncertainties. Use when turning a raw bug report, feature idea, maintenance task, or follow-up item into a structured issue ready for investigation or polish-issue. Never invents speculative implementation designs or starts coding.
---

# Create a raw decision-driven issue

> Capture the problem, the decision to inform, and verified observations. Leave unresolved design choices and deep hypothesis testing to `polish-issue`.

Read `AGENTS.md` and [decision-driven investigation](../../../docs/development.md#decision-driven-investigation) from the repository root. This skill creates a structured, factual issue (by default via `gh issue create`) that either prepares a small, obvious fix or feeds directly into `polish-issue` (`$polish-issue` / `/skill:polish-issue`).

## Boundaries and responsibilities

- **Input:** A user request, bug observation, review follow-up, or architectural question, plus the current repository state.
- **Allowed actions:** Read-only repository inspection (`git`, `rg`, file reads) to anchor paths, symbols, and current behavior; check existing issues (`gh issue list` / `gh issue view`) to prevent duplicates; create the issue via `gh issue create` (or write to a local file/draft when explicitly requested).
- **Prohibited actions:** Modifying repository code, running expensive benchmarks/spikes, prematurely locking in an unverified design, or setting a `READY` evaluation when technical uncertainties remain.

## Workflow

1. **Deduplicate and pin context:**
   - Resolve the exact 40-character `source_commit` (`python3 scripts/git_identity.py inspect HEAD` if available, else `git rev-parse HEAD`).
   - Search open issues (`gh issue list --search "<keywords>"`) to confirm whether this belongs as a new issue or an update to an existing parent issue.
2. **Fast factual grounding (<= 5 minutes):**
   - Locate the relevant files, functions, tests, or docs (`file:line`).
   - Separate **Confirmed facts** (what you directly read or reproduced) from **Reported / unverified assumptions** (what still needs investigation).
3. **Classify initial evaluation and depth:**
   - Default to `Evaluation: NEEDS_RESEARCH` (or `NEEDS_DECISION` if blocked on product/policy choice).
   - Use `Evaluation: READY (candidate)` **only** for a small, self-contained defect or doc fix where the root cause, target `file:line`, and verification test are already 100% certain without further design trade-offs.
4. **Create the issue via `gh issue`:**
   - Write the body to a temporary file (e.g. `mktemp`) and run `gh issue create --title "<concise outcome-oriented title>" --body-file <temp_file>`, then remove the temporary file.
   - Return the created Issue URL, number, `source_commit`, and initial `Evaluation`, and indicate whether to invoke `polish-issue` next.

## Issue body template

Respect project-specific issue templates if present; otherwise use this structure so `polish-issue` can consume it directly without destructive rewrites:

```markdown
## Summary & Metadata
- **Evaluation:** `NEEDS_RESEARCH` | `NEEDS_DECISION` | `READY (candidate)`
- **Source commit:** `<40-char SHA>`
- **Parent / Related issues:** `<#id or none>`
- **Outcome:** <What improves for the user or maintainer?>
- **Decision needed:** <What technical or product choice must be made before/during implementation?>
- **Exit / stop conditions:** <What evidence is enough to decide or stop?>

## What & Why
<Problem statement or motivation. State user/maintainer impact before internal implementation terms.>

## Scope & Non-goals
- **In scope:** <Concrete boundaries of this issue>
- **Out of scope (Non-goals):** <Follow-up work or adjacent areas explicitly not authorized here>

## Current Behavior & Initial Evidence
- **Observed facts:** <Cite `file:line`, existing test names, commands, or error outputs>
- **Expected behavior:** <Desired contract or behavior>
- **Unverified assumptions / Open questions:** <Specific technical uncertainties or trade-offs that `polish-issue` must resolve>
```

## Quality checks before `gh issue create`

- Title states **what** needs to be solved or decided, not a vague component name.
- Every factual claim about current code cites `file:line` or a command output; unverified claims are explicitly labeled as assumptions.
- Solution options are not disguised as requirements when uncertainties remain.
- Working tree (`git status --porcelain`) is completely unchanged after execution.
