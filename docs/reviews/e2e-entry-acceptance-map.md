# EP1 / EG1 current acceptance map — Human-approved bounded adoption

[Issue #18](https://github.com/masahitojp/mariamem/issues/18) owns completion
tracking. The [bounded adoption review](e2e-v060-adoption-review.md) recommends
accepting the fixed v0.6.0 profiles. The Human approved adoption subject to the
[five integration conditions](../decisions/e2e-integration-conditions.md).
Protected merge-commit integration remains open.
This is not whole-dogfood, Qualification or release completion.

The original reviewed and executed source_commit is
`edfee47807cc7ad76aed798947ba70af0a7fb2c9`. Both supported hosts, native minors
and the required gate passed in
[CI41058866706](https://github.com/masahitojp/mariamem/actions/runs/41058866706).
[Saved assessment](e2e-ci-41058866706/assessment.json) binds both complete ZIP
SHA256 matches and the four installed host/Python cells. Report-only descendants
are not relabelled as this executed source. Earlier checkpoints retain their
original scope; their previously pending functional tests now have evidence.

The integrated executable source is
`d38deb043bc84bda064cee06b8568bc5174b744c`, including main
`ce66b9df2067c546c88f6748fcbce2dc175a619a` and P1 #26. Both hosts, native
references, four installed cells and the full Live gate passed in
[verify41095184074](https://github.com/masahitojp/mariamem/actions/runs/41095184074);
[its assessment](e2e-integration-ci-41095184074/assessment.json) records the
separate overall verify success and both-platform/aggregate READY. Existing
0.5.3 metadata does not qualify a future versioned0.6.0 release.
Documentation descendants retain this exact
executable source identity and still require protected PR checks.

| Retained condition | Evidence and detector | Current disposition |
| --- | --- | --- |
| Pre-code probe condition | Decision ancestor3ead1bc8; tests/test_e2e_decision.py | Satisfied; preserve ancestry during integration |
| Fixed app, seed/UNIQUE reset, stable identities | Actual source/installed examples on both hosts/minors | Satisfied for the fixed profiles |
| Independent actual owners and reverse order | Go independent_test.go; Python test_independent.py; active first-owner mutation survives the other Reset | Satisfied; interleaved owners, not scheduler stress |
| Failure then fresh state | Actual Python assertion/recovery; Go Fatal/next-case controlled subprocess | Satisfied at the stated boundaries |
| Physical retirement and registered jobs | Python test_retirement.py positive/lying-hook Busy controls; real Go physical pool/job controls | Satisfied for controlled hooks; no arbitrary-work discovery promise |
| Partial owners, original plus cleanup failures, Reset/Resume/external errors | Both-host Go component/race and Python17-case suites | Satisfied at controlled owner/error boundaries |
| Close wait, timeout and case resources | Python close-wait/timeout and actual browser context close; Go HTTP body/Fatal/canceled-case controls | Satisfied; cooperative cleanup and honest uncertainty retained |
| First/second/repeat usability | Workflow records with exact case census and minimal parameter edits | Satisfied for command wall times using existing CI caches; no cold/human-time claim |
| Candidate checks and installed consumers | Integrated Live CI41095184074 native/host/gate success, four installed cells, temporary cleanup complete | Evidence saved for d38deb04; preserve normal protected PR checks for integration |
| Documentation/review | Current sequencing, guides and e2e-v060-adoption-review.md | Human approved bounded main adoption; publication remains separate |

Detailed retained-baseline1/2/3, peak RSS/FD/session/temp census, resource guards
and tuning remain deferred to shared v0.7.x by the
[existing sequencing decision](../decisions/e2e-v060-work-sequencing.md).
They are unmeasured, not PASS, and not v0.6.0 blockers. Observed cleanup or
isolation defects would still block acceptance.

No further functional gap was found in this bounded review. Future blockers
must identify a violated retained condition, not require universal proof of
arbitrary user hooks. The prototype at3e59bce0 remains outside this candidate.
P1, D1, independent dbt and later release gates keep their separate owners.

Next: complete the approved merge-commit integration with protected checks and
preserved decision ancestry. No new resource campaign is required.

The [Human sequencing correction](../decisions/e2e-integration-conditions.md#human-sequencing-correction--no-further-full-ci-2026-10-31-jst)
accepts subsequent CI-only main changes after focused537-test verification and
final protected daily checks, without another full verify transaction. The
d38deb04 full READY source is unchanged as an evidence identity; later heads
are not relabelled as its full-run source.
