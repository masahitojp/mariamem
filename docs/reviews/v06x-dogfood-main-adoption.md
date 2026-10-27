# Human-approved bounded dogfood main adoption

On 2026-10-27, the Human approved proceeding with main adoption after the
candidate review, including the explicitly stated limitations below.

The selected source_commit is `d389306f9ae0514824f79fccbe2800776786a7ac`, based on
`250bceb80be4cfc9f7c844d888af864fc1d38d25`, through
[PR3](https://github.com/masahitojp/mariamem/pull/3). It comprises the ordinary
Django standard-runner recipe, runnable public Python browser/Go HTTP Live
examples, sequential/parallel Snapshot/Fork guides and bounded CI improvements.
The original independent candidates and their preparation claims remain in the
[parallel work record](v06x-dogfood-parallel-candidates/README.md); that historical
record is not rewritten as a later CI result. Exploratory history is excluded.

## Reviewed evidence and prior conditions

The actual reviewed PR CI source_commit is
`3ed2c8e0790499c215869e33154272b062c35a88`, with tree
`a2ed60283d62023a2ea754f8160c5c60291edcba`, identical to the approved head's tree.
The merge commit's parents are the base and head above. Source identity is a
commit/tree relationship, not a copied tag object or relabelled receipt.

- [Django40492425975](https://github.com/masahitojp/mariamem/actions/runs/40492425975):
  native Python3.11/3.14 references and guest macOS15 arm64/Ubuntu24.04 x86_64 on
  both minors all PASS. Each cell has 18 lifecycle/mixed suites and two deliberate
  migration-failure oracles. Four guest recipe entry checks per cell preserve
  original exits and prove completed owner cleanup. The same authored application
  hashes and native reference digest were independently cross-checked. Failed
  migration leaves the expected partial DDL, admits zero test bodies, captures no
  baseline and disposes the entire guest owner.
- [Live40492426087](https://github.com/masahitojp/mariamem/actions/runs/40492426087):
  public examples PASS on both hosts/Python minors; positive campaigns PASS,
  skip-reset/restart-app mutations detected, installed consumers PASS. Both-host
  Live race checks remain. Native references and required aggregate succeed.
- [Development40492425939](https://github.com/masahitojp/mariamem/actions/runs/40492425939):
  required check/integration PASS. Its Ubuntu check and macOS integration own
  the two invocations omitted by Live on this full PR event. Live's opposite-host
  canonical invocations executed successfully. Standalone/uncertain-scope behavior
  is model-tested, not newly observed in a standalone CI run.
- [Dump regression40492426188](https://github.com/masahitojp/mariamem/actions/runs/40492426188)
  also succeeded; this adoption adds no dump support claims or parser changes.

[Run/job/artifact metadata and semantic assessment](v06x-dogfood-main-adoption/ci-d389306/assessment.json)
retain original identities and hashes. Raw downloaded Django/Live result files
remain in the coordinator's ignored build receipts; the committed assessment is
an explicitly selected summary, not a raw artifact ZIP. SHA256SUMS hashes the
published evidence files. Prior preparation and first-definition-failure receipts
are preserved under their original sources.

## Limits accepted for this bounded adoption

The strongest review objection was that the new manual parallel guide snippets
were not executed. Their syntax, structure, ownership and extraction were checked;
existing real Go/Python parallel Snapshot/Fork tests remain in canonical integration.
This accepts them as documentation of existing behavior, not as independently
executed examples or a performance result. The executable guide tests remain
opt-in and normally skip in canonical check; exact snippet execution is still a
follow-up. Their current experimental-only workflow is not PR/main coverage.

Django is an explicit parent-process recipe using ordinary backend settings,
not a new public adapter or a general compatibility promise. Multiple aliases,
parallel/xdist Django runners, async, independent multi-module applications and
arbitrary projects remain unverified. Django CI is visible but is not a required
protection context; this approval preserves the existing three required contexts
and does not authorize adding another. The local OpenSSL4/Oracle Connector import
failure remains documented; mysqlclient/OpenSSL3 CI does not close that gap.

The first new Live cache namespace missed, then saved successfully. Warm-cache
speedup is unmeasured; no cold setup, cost reduction in minutes or Qualification
claim is made. The cache reuses compiler/module data, clears restored test
results and preserves embedded exact-source checks. See the
[CI change record](v06x-live-ci-dedup-cache.md). Existing guide-only skip versus
model acceptance, docs/reviews allowlist and broader Go/native interruption
coverage remain separate open decisions.

No product runtime/API, guest, generated source, dependency pins, version or
release ledger changes are part of the selected diff. Usage documents retain
the published-v0.5.3 versus unreleased-main distinction. Generated ownership,
bookkeeping and release acceptance therefore have no new delta to qualify.

## Authorized integration and completion boundary

This approval authorizes updating current documentation with the fresh CI results,
recording the decision/evidence and adopting through PR3. These later changes
must remain documentation/evidence only relative to the approved candidate.
They are a new PR head and require their own strict-base checks; old receipts
are not renamed as that head or an eventual squash/main commit.

The [protection readback](v06x-dogfood-main-adoption/protection-before.json)
confirms check/integration/Live required gate, all bound to GitHub Actions app15368,
strict=true and administrator enforcement. No policy edit or bypass is authorized.
Before merging, reread head/base and all candidate checks, require this recipe's
Django matrix as well as protected checks to pass, and reread protection. If
head/base or settings changed, reconcile them before proceeding.

Submit the updated PR and hand CI off without polling. On the Human's CI-result
report, continue this already-authorized adoption without asking again: merge
the exact checked head through the PR only when strict-base conditions pass.
Do not force or use admin bypass. Record the actual main/squash source identity
and protection readback before declaring adoption complete. If repository
auto-merge is unavailable, the Human's result report is the continuation point.

At submission adoption remains incomplete. Qualification, release version and
publication are not authorized by this adoption decision.

## Completion after PR3

The Human reported final CI completion and the already-approved integration
continued on 2026-10-27. All20 checks succeeded for final head
`0490b43a21dceeab10b33d94b5b92bf383e4055e` against unchanged base
`250bceb80be4cfc9f7c844d888af864fc1d38d25`. Required checks, recipe matrix,
mergeability and current protection were reread before normal squash merge;
the merge request matched that exact head and used no bypass.

PR3 merged at 2026-10-27T13:36:39Z. Main adoption source_commit is
`ebb97260788710b2065e81481b2c2f516d6f7e52`. Actual final PR CI source_commit
`730bd17c935928dd37e2cd7df14aa115c40e89a7`, checked head0490b43 and landed
squashebb9726 share tree `c98a74c854d59cf19f1584a7cb5fa994e0f6632b`.
The [completion receipt](v06x-dogfood-main-completion/README.md) records those
separate identities, successful check contexts and post-merge protection.
The submission-stage condition above is closed. Qualification, version,
publication and the separate policy/coverage follow-ups remain undecided.
