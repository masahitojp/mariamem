---
name: polish-issue
description: Resolve pre-implementation technical uncertainties on an issue (by default via gh issue view/edit) through codebase investigation, option comparison, bounded hypothesis validation, implementation planning, and critical review. Concludes with READY, NEEDS_RESEARCH, NEEDS_DECISION, SPLIT, or NO_GO without performing unapproved production implementation.
---

# Polish issue: pre-implementation uncertainty resolution

> Separate resolving technical uncertainty from writing production code. An evidence-backed `NO_GO`, `SPLIT`, or `NEEDS_DECISION` is as successful as `READY`.

Read `AGENTS.md`, [decision-driven investigation](../../../docs/development.md#decision-driven-investigation), and [Human Review recommendations](../../../docs/development.md#human-review-recommendations) from the repository root. This skill takes a raw issue (created by `create-issue` or a human) and updates it via `gh issue edit` so another developer or agent can act without making major unverified design decisions.

## Responsibility boundaries

- **Default I/O:** Read with `gh issue view <id> --json title,body,comments,labels,state` and update with `gh issue edit <id> --body-file <temp_file>` (remove `<temp_file>` afterward). Also accepts a local file path if specified.
- **Allowed:** Code/spec/history inspection, option analysis, targeted tests, benchmarks, and minimal isolated validation spikes.
- **Prohibited:** Unapproved production implementation, PR creation, branch creation on the main checkout, closing/transitioning the tracker's permanent issue state (`In Progress` / `Closed`), or leaving dirty changes in the working tree.
- **Clean Working Tree Guarantee:** Record `git status --porcelain` and the 40-char `source_commit` (`python3 scripts/git_identity.py inspect HEAD` or `git rev-parse HEAD`) at start. Any validation spike must run in an isolated disposable workspace (such as `experiment-workspace` / `git worktree`) or be reverted after capturing reproduction commands, patches, and observations. At skill completion, the checkout must match its initial clean state.

## Adaptive depth

Match investigation cost to uncertainty; time spent is not a quality metric:

| Tier | When to use | Required actions & output adjustments |
| --- | --- | --- |
| **Small** | Clear defect or small change; single obvious design | Verify `file:line` and existing tests; state 1-line reason why no alternative is needed; define concrete files, steps, and DoD. |
| **Standard** | Feature addition, refactoring, or module boundary change | Compare viable options (including "do nothing"); check callers/contracts/compatibility; write full implementation & test plan; run critical review. |
| **Spike / Perf** | Performance, concurrency, compatibility, or feasibility risk | Define hypothesis, comparison table, and stop conditions *before* running; separate **Observed facts**, **Interpretation**, and **Unverified hypotheses**; allow `NO_GO` when evidence fails adoption criteria. |

## Workflow (max 2 review iterations)

1. **Investigate:** Verify whether the problem exists in code (`file:line`), tests, and docs. Separate current vs. expected behavior and list unverified assumptions.
2. **Explore:** Compare realistic options (including not changing code) across correctness, compatibility, maintainability, performance, and cost. Identify uncertainties that could flip the choice.
3. **Validate:** Resolve decision-changing uncertainties via spec checks, existing tests, measurements, or a minimal isolated spike. Check security boundaries, permissions, and failure modes. Never hide inconclusive results, measurement noise, or environment limits.
4. **Design (or conclude No-go / Split / Decision):**
   - If adopting an approach: specify target files, implementation order, **invariant contracts that must not change**, planned branch name (following project conventions), test plan, and objective DoD.
   - If `NO_GO`, `SPLIT`, or `NEEDS_DECISION`: omit speculative implementation steps; instead record the rejection evidence, proposed sub-issues, or the human decision brief.
5. **Critical Review & Stop Rule:** Re-read the updated issue from an implementer's perspective (or invoke an independent reviewer with only `source_commit` + the issue body). Check for unverified assumptions, scope creep, missing failure-mode tests, or ordering traps. Iterate back to Step 1–4 at most **2 cycles** (or until budget/time limit). Hitting the limit without proof yields `NEEDS_RESEARCH` or `NEEDS_DECISION`, never `READY`.

## Readiness gate & hard blockers

Assign exactly one skill evaluation (distinct from GitHub's Open/Closed state; `READY` is a candidate for human approval, not auto-authorization to code):

- `READY`: All Definition of Ready checks pass and **none** of the 3 hard blockers apply.
- `NEEDS_RESEARCH`: Technical evidence is incomplete or budget/environment blocked validation. State concrete missing evidence and bounded cost to obtain it.
- `NEEDS_DECISION`: Requires human choice on product requirements, breaking compatibility, risk/cost trade-offs, or priorities.
- `SPLIT`: Better decomposed into independent deliverables or prerequisites.
- `NO_GO`: Evidence shows the change is unnecessary, ineffective, or not worth its maintenance/complexity cost. Preserve evidence for future reference.

**Three Hard Blockers against `READY` (any one forbids `READY`):**
1. A decision-critical premise remains an **Unverified hypothesis** deferred to "check during implementation".
2. An unresolved product, compatibility, or security trade-off still requires human agreement.
3. Target files, invariant contracts, or objective verification commands/oracles (DoD) are unspecified.

## Issue output structure (non-destructive update)

Keep the actionable current summary at the very top of the issue. When direction changes, reconcile prior conditions as **Retained**, **Non-applicable**, or **Replaced** with reasons, and preserve prior context/history at the bottom rather than deleting it.

```markdown
## Summary & Metadata
- **Evaluation:** `READY` | `NEEDS_RESEARCH` | `NEEDS_DECISION` | `SPLIT` | `NO_GO`
- **Source commit:** `<40-char SHA>`
- **Planned branch:** `<branch-name or N/A>`
- **Outcome & Decision:** <1-3 lines: what improves and what approach is recommended/chosen>
- **Remaining work / Exit conditions:** <What blocks implementation or what defines completion>

## 1. What, Why & Scope
- **Problem / Motivation:** <User/maintainer impact>
- **In scope (Goals):** <Concrete deliverables>
- **Out of scope (Non-goals):** <Explicit exclusions>

## 2. Current Behavior & Evidence
- **Confirmed facts:** <Code references `file:line`, existing tests, reproduction>
- **Assumptions & constraints:** <Platform, compatibility, security, or resource bounds>

## 3. Options, Validation & Decision
- **Options compared:** <Alternatives including "no change", or 1-line justification for single option in Small tier>
- **Validation results:** <Hypothesis, method/command, and strict separation of **Observed facts** / **Interpretation** / **Unverified hypotheses**; or reason validation was unnecessary>
- **Decision & rationale:** <Adopted option (or `NO_GO` / `SPLIT` reason) and why alternatives were rejected>

## 4. Implementation & Contract Plan
*(Omit for `NO_GO`; replace with split breakdown for `SPLIT` or decision brief for `NEEDS_DECISION`)*
- **Changed files & order:** <Step-by-step targets and dependency order>
- **Invariant contracts:** <APIs, wire protocols, data formats, or behaviors that must NOT break>

## 5. Test Plan & Definition of Done (DoD)
- **Verification commands & oracles:** <Exact unit/integration/benchmark commands and pass criteria>
- **Definition of Ready checklist:**
  - [ ] What/Why, scope, and non-goals are concrete
  - [ ] Major design decisions and rejection reasons are recorded with evidence
  - [ ] Decision-critical technical uncertainties are resolved (no hard blockers)
  - [ ] Target files, implementation order, and invariant contracts are specified
  - [ ] Objective test plan and measurable DoD exist
  - [ ] Another developer/agent can start from this issue and the codebase alone

## 6. Review Summary & Open Questions
- **Critical review findings:** <Self/peer review objections and how they were resolved>
- **Human decision request (if `NEEDS_DECISION`):**
  - **Question:** <One decision needed now>
  - **Options & Recommendation:** <Options, recommended choice, decisive reason, and strongest objection>
  - **Impact of deferral:** <What is blocked until decided>

---
<details>
<summary>Prior Context & Investigation History</summary>

<Preserve original issue text, superseded conditions (Retained / Non-applicable / Replaced), and dated spike logs here>
</details>
```
