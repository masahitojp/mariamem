# EP1 / EG1 implementation decision

Human approved implementing the bounded entry design, conditional on recording
the probe result in this decision document before implementation.

Approved design source_commit: `ca3d3937c9dcc12c536bcedf75cb5b9ad090bb6c`,
[design](../reviews/v060-e2e-entry-design.md), PR #27.
Probe execution source_commit: `03b90c17f558d6ab3f9d0f376fa50db9435261fb`;
result/evidence commit: `870af0ab793b7adc48c11f3e39108416dce0b330`.
[Probe result, inputs and checksum-bound logs](https://github.com/masahitojp/mariamem/blob/870af0ab793b7adc48c11f3e39108416dce0b330/docs/reviews/v060-e2e-entry-probes/README.md).

On observed macOS27.2 arm64, Go1.26.10 race-instrumented controlled owners passed
four healthy controls repeated20 times. Lease lifetime across t.Parallel, duplicate
acquisition rejection, cleanup debt and independent owners were exercised.
An intentional t.Fatal/Goexit retained its expected failure while running cleanup
and permitting the next healthy case. Early-release and late-registration mutants
failed their named semantic oracles. Python3.11/3.14 each passed five registration
controls, including real FD/file disposal and interrupt identity. This supports
Case(t) lifetime through t.Cleanup and registration before readiness can fail.

This is controlled-owner evidence, not actual Live/app/browser, native comparison,
installed consumer, resource campaign or both-supported-host acceptance. Those
remain required by the approved design and #18. No probe result is relabelled
as this decision's source or a future SDK candidate's acceptance.

## Authorized implementation boundary

Implement Python BrowserEntry/case contexts and Go mariamemtest.NewHTTP/Case(t)
using existing Live, with readable-owned diagnostics, early partial-handle
registration, exclusive case admission, cleanup-debt latching and app-before-DB
cleanup. Keep original failures and honest attempted/confirmed cleanup state.
Use cooperative deadlines; no forced cancellation or arbitrary job/pool discovery.
The supplied hooks own app-specific quiescence and physical connection retirement.

G1 PR #6 and P1 PR #26 remain independent candidates with their own adoption
conditions. Avoid importing unmerged helper internals. Keep new Go HTTP code in
separate files; use callback preparation without depending on P1 PrepareCommand.
No guest/generated/Live semantics change or mandatory browser dependency is approved.

#18 owns implementation and full acceptance tracking. Main adoption, Qualification,
Product Validation and publication are later decisions. D1's prepared-state
mechanism/deferral and independent dbt #19 are outside this implementation task.

## Source reconciliation before product code

The design commit's actual parent is `16a2f78e5e64cb099b2c61c60d53d6375428aa86`,
although its input section cites intended main `3ced8933`. This was caused by
cloning a checkout whose local main lagged its remote. Before product code,
merge actual main `3ced89330997d711675a303df831680b699ebd8c` and preserve this
distinction. The source-linked Live mechanisms remain unchanged. Probe evidence
stays bound to its actual source; no missing repair is assumed present there.
