# Issue #53 — candidate adoption review

**Review follow-up:** the body below is the c53771cd review, preserved at its
original source/evidence boundary. Human review found missing capacity diagnostics
G1 despite the eighteen-row matrix passing. The current candidate correction and
verification status are in [the G1/G2/G3 follow-up](issue53-review-followup.md).
The previous docs-only tree-equality reuse applies to7c0f6c32, not to the later
runtime correction; a new-source matrix remains required before current adoption.

Decision needed now: adopt the finite-Fork candidate in Draft PR85, including its
WASI write cleanup prerequisite. **Recommendation: adopt.** The fixed eighteen-row
exit has source-bound evidence on both supported hosts and Python minors, and
capacity is acquired before startup and retained until confirmed disposal.

The strongest objection is the ownership complexity across startup, consuming
capture, Live and different-host transfer: a short limiter alone would be easier
to maintain. These paths already exist in the supported product; removing one or
letting it bypass the cap changes the approved scope. The candidate keeps the
plumbing private, exercises controlled late-outcome/failure races and tests the
actual entry paths. That is sufficient for this fixed exit, not a proof against
arbitrary non-cooperative guests or a machine-wide resource guarantee.

This recommendation is not a recorded Human approval. Main integration and
release remain separate decisions; nothing was merged, tagged or published.

## Reviewed object and identity

Inputs were reconstructed from PR85 and the repository because the request was
“continue” after successful CI and the proposed next step was receipt assessment
and adoption review:

- Claim: [implementation checkpoints](issue53-fork-limit-implementation.md),
  read at source_commit `c53771cd9f653f971fdfa677105d46f6787298f9`.
- Candidate: that commit on `feat/issue53-fork-limit`;
  [PR85](https://github.com/masahitojp/mariamem/pull/85).
- Base/main: `8f42948340265ce38fde2d1fa6b2f82bf14ae9d2`.
  Git identity inspection confirms both are commits. PR was draft and mergeable
  at the metadata read; adoption is still pending.
- Prior conditions: [fixed design](issue53-fork-limit-design.md), especially the
  G1/G2/G3, parent-lock, recovery and numeric-range additions authorized after
  `a4929d12`; its eighteen-row stopping point is unchanged.
- Existing [snapshot contract](../decisions/snapshot-product-contract.md) and
  [prepared consumer exceptions](../decisions/prepared-consumer-exceptions.md)
  remain in force. The implementation and earlier detector index retain their
  original source context; their old pending-execution wording is historical.

Hosted evidence is from
[verify41761661883](https://github.com/masahitojp/mariamem/actions/runs/41761661883),
exactly c53771cd, operation=verify/mode=auto. Full run, core, six feature owners,
installed verification and aggregate are successful. Publication/public smoke
were correctly skipped. READY records still carry the existing0.6.0 metadata;
they do not choose a new version or authorize overwriting the published release.

## Evidence and fixed exit

[Saved evidence](issue53-fork-limit-evidence/ci-41761661883/README.md) contains the
four-cell matrix, all eighteen fixed-row dispositions, source/job metadata,
artifact ZIP/member hashes and selected published receipts. Ten downloaded ZIPs
matched GitHub's digests. CI checkout/home prefixes alone are normalized in the
published receipt text; original/published hashes are distinct. Large nested
guard reports are explicitly checked projections, not silently truncated raw
receipts. Binaries, venvs and compiler outputs are excluded.

| Host | Python | Ownership/transport units | Actual guest | Installed Live | D1 serial / xdist |
| --- | --- | --- | --- | --- | --- |
| macOS15 arm64 |3.11|103 PASS|9 PASS|PASS, cap2|20 /15 PASS, cap1|
| macOS15 arm64 |3.14|103 PASS|9 PASS|PASS, cap2|20 /15 PASS, cap1|
| Ubuntu24.04 x86_64 |3.11|103 PASS|9 PASS|PASS, cap2|20 /15 PASS, cap1|
| Ubuntu24.04 x86_64 |3.14|103 PASS|9 PASS|PASS, cap2|20 /15 PASS, cap1|

Each cell also has installed owned Python/Go E2E first/second-case acceptance and
confirmed consumer cleanup. The external owned Go module has no replace directive;
all129 recorded product-file hashes match the candidate. The older external Live
consumer separately uses its documented local candidate replacement. D1 receipts
verify installed=true, exact adapter/host source and dirty=false. Django is5.2.18
on Python3.11 and6.1.2 on3.14; mysqlclient2.2.7, pytest9.0.2,
pytest-django4.12.0 and xdist3.8.0 are recorded in the matrix.

Core jobs
[126352260246](https://github.com/masahitojp/mariamem/actions/runs/41761661883/job/126352260246)
and
[126352260262](https://github.com/masahitojp/mariamem/actions/runs/41761661883/job/126352260262)
actually invoke the thirteen-package Go race owner, full owned-Snapshot actual
module in47 Python runtime tests,33 snapshot checks and selected prepared
consumers. Both logs retain the strict accepted-exception comparator PASS with
the original Python functional failures, rather than treating CALL as functional
success. See the saved core summary for exact invocations and log hashes.

All eighteen fixed rows are **technically satisfied within their stated evidence
scope**, as detailed in
[assessment.json](issue53-fork-limit-evidence/ci-41761661883/assessment.json).
The important prior conditions are:

| Prior condition | Disposition / evidence / detection net |
| --- | --- |
| Finite default; no unlimited path | Satisfied: `internal/forklimit/options.go:59`, `pool.go:29`, immutable public limits; options/pool tests and four-cell actual/installed cap checks. |
| Shared numeric domain, request-local overflow | Satisfied: `options.go:27`, Python validators and control raw-field tests; actual `test_bounded_invalid_control_values_preserve_source_and_sibling_sql` keeps both SQL owners usable after rejection. Huge durations are validated, not waited out. |
| Admission includes starting/live/cleanup | Satisfied: `pool.go:51`, `Lease.Activate` and `TrackCleanup`; cap1/2 four-requester test plus actual/installed progress controls. |
| Parent Close/transfer lock and Session refs | Satisfied: Python constructor retains under parent lock and reserves outside it; `test_parent_close_after_retain_before_reserve_preserves_child_and_balances_refs` covers both spellings. Framed and actual handoff tests retain the child until after parent/waiter completion. |
| Stuck-host watchdog | Satisfied: reserve/export/start barriers and non-reading subprocess pipe; `tests/test_forklimit_transport.py` and `test_stuck_control_writer_has_bounded_callers_and_one_writer` run in each103-test cell. Outer timeout/default-setting mutation control remains. |
| Cleanup debt, consume/preserve, late reply | Satisfied: typed disposal ownership, stable errors and one lease settlement; Go physical ownership/mutation controls plus Python framed late-reply tests. These are controlled fault owners, not actual-engine OOM. |
| Explicit Live recovery with cap2 | Satisfied: `internal/live/capacity_test.go:85`, shared-control adapter tests and Python new-debt-during-retry/reply tests. Actual installed tests separately prove busy retains data/generation and reset succeeds after release. |
| G1 includes D1 | Satisfied: each installed serial/xdist observation asserts cap1/finite Fork waits. Controlled class cleanup failure stops final DROP; source/class owners retire before its last-slot acquisition. |
| G2 CPU limitation | Satisfied by guides and notes: auto is memory-based, not CPU-optimal/OOM-safe; each baseline/worker has its own budget. CI cannot establish optimal CPU settings and none is claimed. |
| G3 supplied fixture finite wait | Satisfied: default30 propagation, invalid/None rejection and held-child pytest failure with no later admission. The held-child test uses a short override; it does not claim a30-second wall observation. |

## WASI cleanup prerequisite

Adoption explicitly includes both the limiter/entry changes and the small host
runtime prerequisite; it must not be described as a limiter-only diff.
`internal/generatedgo/code/base/base.go:12969` previously discarded writer errors.
A broken pipe could return success/zero, leaving the guest retrying output while
Close waited for a joined exit. The [bounded probe](issue53-write-cleanup-probe.json)
reproduced baseline disposal failure at case5; helper-only error propagation
closed90 cases, including28 with an observed interrupted guest. This establishes
the tested failure mechanism, not universal asynchronous worker cancellation.

`TestFDWriteReportsErrorsAndProgress` and the real closed-pipe regression cover
errno, zero/partial/short/later-error and complete writes. Both imports use the
same helper; wasm64 has unit coverage and is not a new advertised guest target.
The checked `scripts/runtime_write.py` adapter, clean-installer negative tests,
generated provenance and both-host regeneration keep the correction reproducible.
`release/generated-license-evidence.json` adds source continuity; the historical
audit source, host and symbol evidence are unchanged. Guest input, translated
MariaDB functions/data, converter and distributed notice bytes do not change.

## Gaps, objections and things confirmed clean

No unresolved technical blocker was found within the fixed exit. The remaining
Human adoption/integration decision is not a CI-detectable condition.

The usage scan found stale “wiring/matrix pending” wording in Go, Python, D1 and
notes. The accompanying documentation delta updates it, adds the explicit nested
acquisition/deadline warning and names the WASI prerequisite. It also states that
old positional Go literals of expanded option structs need field names. CI checks
syntax/public boundaries, not semantic freshness of prose; this required review.
The original published0.6.0 scope and historical reports are not rewritten.

Other missing-things scan conclusions:

- No unlisted entry omission found: Go/Python direct, pytest, G1, Live, owned E2E,
  different-host handoff and D1 are covered at the stated boundaries.
- No generated ownership/input/license omission found: installer inclusion,
  provenance, source-only continuity and Python inventory mirror agree.
- No old receipt was relabelled. b75af56f/33925b14 failures remain at their own
  sources. Their failures are fixed and re-executed in the successful c53771cd run.
- No CPU/resource/performance prerequisite added. Auto16 on a16-GiB host can
  still be too much CPU work; choose an explicit cap. P16, RSS/queue optimization
  and prewarming #84 remain outside this adoption.
- Non-cooperative cleanup can still retain a lease until actual completion or
  lineage end. Controlled failure tests do not prove arbitrary engine faults join;
  guides retain this limitation and no silent slot reuse is allowed.
- No new wire support or new driver-exception disposition found. The selected
  consumer comparator still preserves both named exceptions and original FAILs.

## Next action and review limits

The next action is the Human's candidate-adoption decision for PR85, including
the WASI prerequisite. The candidate product tree is c53771cd. The accompanying
receipt/wording commit is docs-only: its non-doc tree must equal the fingerprint
in assessment.json. Check that equality before pushing; the old full-matrix
receipt remains c53771cd and is not called an independently tested docs head.
Ordinary protected PR checks still apply. This is existing tree-equality evidence
reuse, not a reason to rerun a full runtime matrix for prose.

This is a contract/evidence and critical ownership-path review, not an independent
line-by-line audit of every changed file. No new benchmark or CI execution was
performed for this review. Hosted metadata, digests, selected receipts, source
paths and retained original failure controls were checked. Release version,
publication, new resource claims and later unrelated main changes are outside it.
