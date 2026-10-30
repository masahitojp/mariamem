# P1 fixed-exit reconciliation

Prepared from source_commit `cb4553a43c1ee4df4f9aa67f4c0fc57373b3af4b`
on 2026-10-30, following the [Human's fixed exit](../decisions/p1-fixed-exit-v060.md).
This maps existing evidence and the final candidate checks; it is not adoption
approval. The submitted CI SHA identifies the candidate containing this record.

## Six-condition ledger

| Fixed condition | Evidence and detection net | Current disposition |
| --- | --- | --- |
| Compatibility / approved PrepareCommand contract | `test_prepare_command.py`: argv/env copy, parent overlay, reserved target, literal execution, bounded/truncated output, exit/spawn/timeout/interrupt and group retirement. `test_routing_pytest.py`: None/callable, ignored return, side-effect fixtures, overrides, no-marker and no automatic preparation routing. `test_p1_pytest_entry.py`: descriptor as third input, unknown-input rejection. | Existing implementation evidence; final candidate focused checks and CI required. |
| Preparation and independent schema/seed | `test_p1_runtime.py::test_real_prepared_entry`: actual command/callback, workers1/2, reverse order, committed schema/data and ordinary failure, exact six-child JUnit counts, preparation once and worker-local owners. `time_campaign.py`: four-case warmup plus three observed batches, workers1/2 and unchanged second-test scaffolding. | Required-host installed-wheel correctness and time receipts already exist; final candidate CI will rerun the supplied entry. |
| Failure diagnostics and admission | Command tests and real pytest controlled-owner tests cover original/cleanup failure preservation, readable stage, worker-local debt stop, ordinary failure continuation, routing/disconnect, interrupt and xdist independence. Added two controlled-source capture rejection cases (preserved/consumed) verify no test body/fork and source finalization. | New capture cases need final candidate CI; controlled owners do not prove a new guest capture-failure reproduction. Existing backend ownership controls retain their scope. |
| Owned lifecycle cleanup | Actual runtime receipts require child/baseline/source close counts and final host reaped/temp directory removed; routing exits wait for physical disconnect. `test_p1_pytest_entry.py` checks real FD closure on partial unwind, original+cleanup errors and no closed-flag shortcut. `test_owned_snapshot_unit.py` checks source consumption, last-owner reaping, late/unreturned handles, start failure and interrupted operations. | Lifecycle oracles retained; no claim of full process-tree FD peak census or hard-kill recovery. Final candidate runs these unit and actual-runtime owners. |
| Supported-host consumer/native/usability evidence | Source-bound native command/callback and installed wheels on macOS15 arm64 / Ubuntu24.04 x86_64, Python3.11/3.14. Native input admission and exact module/host stamps reject stale inputs and source fallback. Three-time receipts preserve separate phases, edit counts and explicit unmeasured acquisition/human time. | Historical PASS at original sources; exact final candidate CI pending. |
| API documentation / review | `docs/python.md` and unreleased notes describe PrepareCommand, 16KiB output tails and worker-local admission change. `check_fixture_design.py` rejects removal of notices or weakening of the approved API and fixed exit. | Notice/contract checks retained. One adoption review after final candidate evidence; no main/Qualification/publication decision here. |

## Reusable evidence and its limits

- [CI40829538394 assessment](v06x-python-fixture-implementation-evidence/ci-40829538394/assessment.json):
  source_commit `5a9f3172639f626b82a6e303a6de4942e0c42ace`, native command/callback
  reference and four installed-wheel configurations in each host/minor cell.
  Native schema_count_after is zero. Exact test counts and final host/temp owners
  are retained; controlled-owner failures are distinct from actual guest runs.
- [CI40962108392 assessment](v06x-python-fixture-implementation-evidence/ci-40962108392/assessment.json):
  source_commit `9e52f82e358c640dd18c54ddc209de173caa8144`, required-host/minor
  installed-wheel time checkpoint and bounded real FD STOP. The latter is now
  optional resource evidence, not a P1 completion gate.
- Both receipt directories' SHA256SUMS.json were rechecked against their stored
  files. Python product modules and the P1 migration/application inputs have no
  diff from the correctness source above to cb4553a4. This supports reuse at the
  recorded boundary; it does not relabel an old run as this candidate's CI.

## Final candidate and stopping rule

The only added correctness cases are capture-failure admission/finalization for
preserved/consumed sources. Explicitly run the existing compatibility and owned
snapshot unit owners in the both-minor P1 CI step. Pin resource experiment opt-in
to zero there; four resource runtime controls skip by the approved v0.7.x
placement. A skip is not runtime PASS. Preserve their code and historical receipts.

After the focused checks, submit the exact candidate to existing CI. Once its
source-bound both-host/minor installed-consumer/native results are available,
verify and save that receipt, resolve any failure of these six conditions, and
present one P1 adoption review. Do not add retention, allocated-temp accounting,
observation barriers, continuous guards or another measurement-tool milestone.
The broader dogfood entries and wire dispositions remain separately tracked.

Local verification of this increment used Python3.11/pytest7.0.0 with the fixed
PyMySQL1.2.3/SQLAlchemy2.0.54 environment: 286 focused tests passed (command,
pytest entry, routing compatibility, owned snapshot, design contract and Live
workflow). Contract lint also passed. An initial run in the smaller probe-only
environment lacked PyMySQL and failed 28 routing cases; rerunning in the existing
application environment resolved them. These are local unit/subprocess results,
not the final installed-wheel supported-host receipt.

## First final-candidate CI failure — 40979625348

Source `4cc74f9a7f541afe96a958360eb60ac2fa77fb93` passed both native input
cells, but both host canonical checks failed the same three obsolete workflow
assertions: resource probe, resource guard and observation barrier suites were
still required by their old tests in the ordinary P1 CI step. Each host reported
3 failed / 1591 passed / 60 skipped. Installed-wheel P1 acceptance did not run.
The [checksummed original failure](v06x-python-fixture-implementation-evidence/ci-40979625348/assessment.json)
retains both check logs, native input files and original artifact digests.

The correction removes those three superseded workflow obligations. The central
fixed-exit workflow test instead requires resource opt-in zero and excludes all
three suites from the P1 step. Resource helper behavior/negative controls remain
intact; no P1 lifecycle or failure oracle is relaxed. Unreleased notes now also
state the approved resource deferral. A corrected candidate CI is required.

## Corrected final-candidate result — 40987752495

Source_commit `b108abf11a623c18c45adfab2968d357bf40718b` passed the corrected
both-host/minor CI. Each installed-consumer cell reports 220 unit PASS and
5 runtime PASS; the four resource experiments are explicitly SKIP. Both native
input cells pass with schema_count_after=0. Four original ZIP digests and the
898-file selected archive are checked and retained in the
[receipt](v06x-python-fixture-implementation-evidence/ci-40987752495/assessment.json).
All six fixed conditions now have evidence at their declared boundary. See the
[adoption review](v06x-p1-fixed-exit-adoption-review.md) for recommendation and
remaining protected-PR/Human decisions. Historical FAIL and earlier PASS records
keep their original source/scope; full resource characterization remains deferred.
