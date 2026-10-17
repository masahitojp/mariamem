---
name: review
description: Conduct a mariamem milestone technical review of a plan, candidate diff, or evidence bundle - verify claims against code, CI records and primary sources, then report one decision with a grounded recommendation, its decisive reason and the strongest objection. Use when the Human asks for a review or a missing-things check at a gate such as main integration, qualification or adoption. It never authorizes integration, release or code changes.
---

# Milestone technical review

> The reviewed document is the claim, not the evidence.

Read `AGENTS.md`, [Human Review recommendations](../../../docs/development.md#human-review-recommendations)
and [scope and completion](../../../docs/development.md#scope-and-completion) from
the repository root. They own the report format, the completion rule and the
Human's decision boundary; this skill only says how to verify and what to look
for. Reviewing is not approving: candidate adoption, main integration,
qualification and release stay separate Human decisions.

## How this skill runs

A skill is instructions the executing agent loads, not a standalone program.
This file lives at `.agents/skills/review/`, which Pi (`/skill:review`), dsh and
Codex (`$review`) discover. Invoke it yourself; do not rely on automatic
selection for a gate. A fresh session starts with no conversation history, so the
request must carry everything below.

The Human provides:

- the reviewed artifact path, and the revision it was written from;
- candidate and base commit as full 40-character SHAs;
- the branch / evidence location the artifact points at;
- the one decision to make now, and what is explicitly *not* being decided;
- the cross-check list: prior review sections, decision documents, status docs.

## Fix the reviewed object first

Never review "the latest" of anything: review the SHA-pinned artifact the Human
supplied. If an input above is missing, reconstruct it from the repository and
say which parts you inferred. Read branch content with `git show <sha>:<path>`
and check `git rev-parse --abbrev-ref HEAD` first: the working tree is often on a
different branch than the artifact. Verify recorded run claims with one metadata
read of those run/job IDs; never re-run, poll or supervise CI.

## Mandatory verification rules

1. Check the artifact's claims against the repository, not against the artifact.
   Cite `file:line`, a run/job ID, an artifact digest, or an independently
   fetched primary source for every material claim.
2. Cross-check the previously accepted conditions. List the adoption or
   prerequisite conditions from the linked prior reviews and decisions and judge
   each satisfied / unsatisfied / unverified. Unverified is not satisfied.
3. Check the detection net. For every candidate gap, name the existing check,
   test or oracle that would catch it — or state that it is invisible to CI. The
   second case decides materiality; do not demand proof a check cannot give.
4. Separate facts, inference and unknowns, including specification differences,
   real-workload reachability and reproduced user harm.
5. Never present unit or limited-guest PASS as runtime behaviour proven, and
   never weaken, delete or bypass an existing failure oracle to make a change
   look valid. State what the evidence covers and what it cannot.
6. Only assert numbers that existing measurements support; label cohorts
   (measured/diagnostic, macOS/Ubuntu) and never present a lower bound as proven.
7. Treat "PASS", "complete" and "verified" in the artifact as claims to test
   against the artifact's own stated scope.

## Missing-things scan

Give a conclusion for each; say "none found" explicitly where clean.

- unsatisfied, unlisted or re-approval-gated adoption conditions;
- current usage documents contradicting a changed contract (`README.md`,
  `docs/go.md`, `docs/python.md`, `docs/releasing.md` are the version-gated set);
- generated-source ownership and bookkeeping (`HANDWRITTEN_FILES`,
  `release/generated-go-inputs.json`, `release/baselines/`, `release/NOTES-*`);
- boundaries no verification reached: path, branch, OS, failure mode, cold vs warm;
- work described as done but actually outstanding: independent regeneration,
  performance re-measurement, qualification, opposite-platform runs;
- mixed decisions, or a next step that silently assumes an unapproved one;
- stale in-code comments describing behaviour that was removed.

## Report

Follow the Human Review format:

1. The one decision needed now, your recommendation and decisive reason, then the
   strongest material objection and why you still recommend it (or what would
   change your recommendation).
2. Gaps and unsatisfied conditions in materiality order, each with its evidence
   and whether existing checks detect it.
3. What you confirmed is *not* a gap, with evidence, so it is not re-investigated.
4. Next actions, and the limits of this review (what you did not inspect).
5. If no judgment is possible, state the missing evidence and the concrete work
   and cost to obtain it.

## Do not

- poll, wait for, or supervise CI the Human submitted; the Human reports results;
- change code, tests, branches or evidence unless this task asked for it;
- treat the review as integration, qualification or release approval;
- edit historical reviews; keep new decisions in current status/decision docs;
- repeat the artifact's own rationale back as if it were evidence.
