# EP1 / EG1 acceptance map — 2026-10-30 checkpoint

This maps the approved [E2E contract](v06x-e2e-entry-contract.md) and
[dogfood scope](v06x-dogfood-scope-draft.md) to evidence. It does not change
their requirements or approve adoption. [Issue #18](https://github.com/masahitojp/mariamem/issues/18)
owns the actionable completion checklist. Historical reports keep their original
candidate identities; a previous PASS is not acceptance of this combined source.

## Finite completion boundary

The EP1/EG1 task ends after the approved fixed profiles have their failure,
installed-consumer, workflow and resource acceptance assessed on the supported
hosts, the Human decides on main adoption, and the approved candidate is
integrated with its required checks. Successful example execution or green CI
alone does not close it. P1, D1, independent dbt revalidation, version selection,
Qualification and publication remain separate obligations/decisions.

The current consolidation includes PR #28, registered-job controls from PR #32
(`0af24639e27f3a8b96696072377dbd9c2fe6757b`), and adopted main
`80354f7b9e5c50e576fe9f040d4ee764200f6370`. It preserves the pre-code decision
ancestor `3ead1bc8d1ebb984f912cf4062c7a6dd759698c9`. It does not incorporate
the unmerged P1 implementation or change the engine/Live contract.

## Evidence and remaining work

| Approved obligation | Existing evidence and its boundary | Remaining acceptance |
| --- | --- | --- |
| Two cases, same app/endpoint, reset seed and reused UNIQUE input | [Owned-entry CI](e2e-owned-entry-ci-40833174501/assessment.json), then [installed consumers](e2e-installed-ci-40854876547/assessment.json), on both hosts and Python minors | Re-execute the consolidated candidate; include order variation in the repeat campaign |
| Installed wheel/default bundled host and external Go module | Exact-byte/package/source receipts in installed CI40854876547 attempt2; earlier bootstrap failure retained separately | Retain exact-source results for consolidated candidate, without substituting source-checkout imports |
| Physical idle pool cannot bypass drain; no body/later admission on Busy | [Physical controls CI40871306020](e2e-physical-ci-40871306020/assessment.json); actual DB/Live and public Case subprocess, both hosts | Preserve original Busy and generation/no-Resume assertions in consolidated CI |
| Registered job joins before Reset, or broken hook is rejected | [Registered-job controls](e2e-registered-job-controls.md): real transaction/Live; normal and race local PASS at code source0f843cb5 | Both supported hosts; this proves only the explicitly registered controlled job, not arbitrary future jobs |
| Partial startup/preparation, cleanup order and original cause | Python `test_partial_start_and_all_cleanup_attempts`, `test_partial_source_and_prepare_failure`; Go `TestHTTPPartialStart` | Component evidence only. Map partial Live ownership and the complete app/Live/baseline compound-failure path, adding missing boundary controls |
| Reset/Resume/external-state failure stops body and future admission | Python setup/resume/external controls; Go `TestHTTPFailureLatches` | Controlled failures prove entry behavior, not every physical replacement failure. Reconcile with real Live fault evidence and explicitly state uncovered boundary/cost |
| Assertion/cancel/interrupt and per-case resource disposal | Python assertion/interrupt/browser-close controls; Go Fatal subprocess, context cancellation and owned HTTP body controls | Complete cancellation/cleanup-context and concurrent-close mapping; preserve original plus cleanup failures and attempted versus confirmed shutdown |
| Reject overlap; independent owners do not leak state | Python overlap and Go lease/parallel-suspension controls; earlier controlled-owner adapter probe | Actual two-owner EP1/EG1 campaign, including independent endpoint, app and DB mutation identities |
| First test and second test without duplicated lifecycle | Runnable fixed-profile examples and installed consumers exist | Save reproducible commands, authored second-test diff/steps and phase times. Do not invent human editing time or claim a clean machine |
| Repeat elapsed time and bounded resources | G1 campaign is a tooling/reference input, not EP1/EG1 evidence | EP1/EG1 warmup plus three observed four-case batches, serial and two independent owners; retained baselines1/2/3; required counters and guard STOP control |

Component controls above are in `tests/test_e2e_entry.py` and
`mariamemtest/http_test.go`; their implementation and historical verification
are described in [the implementation checkpoint](e2e-owned-entry-implementation.md).
They are not labelled physical-fault or supported-host campaign PASS here.
Python Live construction cleans its own partial protocol handle in
`python/mariamem/live.py`; Go construction can return a non-nil cleanup owner
with an error. Map these different boundaries rather than inventing a common
return contract or treating an entry mock as actual host cleanup evidence.

## Next execution sequence

1. Submit the consolidated source to existing Live CI on macOS15 arm64 and
   Ubuntu24.04 x86_64, Python3.11/3.14 and Go1.26.10. Manual dispatch can verify
   a Draft without changing its review/adoption state. Keep required gates and
   native/regression checks; retain the actual executed SHA and artifact hashes.
2. Close the finite failure-evidence mapping above. Add controls only for a
   missing oracle, and distinguish controlled faults from actual engine faults.
   Any unverified requirement needs its concrete missing evidence and acquisition
   work before the adoption recommendation; it cannot disappear behind a green job.
3. Extend the existing campaign machinery for the two E2E entries, preserving
   phase/batch timing and fixed64-table retention input. Observe process-tree RSS,
   available memory, FD base/peak/final, physical sessions, transient old/new
   Reset children, baselines, owned temp and confirmed cleanup. Use the approved
   incremental2GiB RSS /8GiB owned disk /16GiB free /64 FD-headroom bounds.
   Missing counters are UNVERIFIED, never zero. One Live may temporarily own two
   replacement children; two owners must budget/observe that overlap.
4. Produce one source-bound acceptance review against this full contract and
   record the Human's adoption decision. Integrate only after approval and
   required candidate checks; keep release approval separate.

The next hosted run validates the existing examples and physical/job controls;
it does **not** contain the unfinished resource campaign. CI submission is a
handoff, not a claim that these later steps have completed.
