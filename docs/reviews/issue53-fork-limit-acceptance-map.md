# Issue #53 — fixed acceptance evidence map

Code source_commit: `8566c8ad6b5dbb62d5540120bec0e9abe3d97519`.
Scope: the18 rows of the approved
[fixed acceptance table](issue53-fork-limit-design.md#fixed-acceptance-and-stopping-point).
This is a detector/evidence index, not another completion checklist; [Issue #53](https://github.com/masahitojp/mariamem/issues/53)
owns execution tracking. No row below is an installed/platform matrix PASS.

The design/API decisions are fixed. Major entry implementations and named local
detectors exist. Known planned work is to execute the exact-candidate matrix,
retain and bind its receipts, then judge these rows against those results.
Whether execution finds another defect, and its repair cost, remain unknown.
That uncertainty is distinct from an undecided design or a missing matrix run.

## Local evidence and its limits

On macOS arm64 / Go1.26.10 / Python3.14, clean code source above passed canonical
daily check (67 source tests, Go tests/vet,1870 Python tests plus106 subtests,
91 skips), Go/Python DB/Live source smoke and9 selected actual-guest ownership
cases with a same-source clean host. The installed consumer's source-smoke route
now explicitly asserts cap2, third-child timeout and capacity-busy Live data/
generation retention. This is not an installed-wheel result.

Earlier D1 source-entry20 serial/15 xdist cases passed on `6df2f5c6`; earlier
control/live/forklimit race cases passed for the `737f4414` change. Those remain
historical evidence at their own sources, not receipts for this candidate.
[Implementation records](issue53-fork-limit-implementation.md) retain the context.

| Fixed row | Named detectors and evidence scope |
| --- | --- |
| Inputs/compatibility | `internal/forklimit/options_test.go`, public `TestSnapshotLimitValidationPreservesSource`, `tests/test_forklimit_unit.py`: immutable limit, invalid values, old/mismatched target rejection before capture/export. |
| Numeric limits | `tests/test_forklimit_options.py`, `internal/forklimit/options_test.go`: full validator boundaries, subnanosecond/max waits without real long waits. `internal/control/fork_test.go::TestOutOfRangeControlFieldsDoNotKillSharedHost` covers framed raw fields; `test_bounded_invalid_control_values_preserve_source_and_sibling_sql` supplies representative actual SQL survival. |
| Default resolution | `internal/forklimit/options_test.go::TestResolution` and `TestCgroupMountRootsAncestorsAndUnavailableLimits`; each capture owns one pool. D1 controlled capture tests independently resolve auto instead of inheriting a prior result. No OOM or CPU optimum is inferred. |
| Admission | `internal/forklimit/pool_test.go::TestConcurrentBoundAndProgress` uses caps1/2 with4 requesters; disposal tests retain cleanup occupancy. Public wait/progress tests and actual cap1/2 consumers exercise the attached owners; independent-pool and consumed-child capture tests prevent shared counters. |
| Wait/Close races | Public Go `TestConcurrentForkCloseOwnership`, `TestSnapshotCapacityWaitWakesOnCloseWithActiveChild`; `tests/test_forklimit_unit.py` full-wait and pre-reservation barriers; real racing-Close/child SQL cases in `tests/test_owned_snapshot.py`. |
| Python transfer/parent lock | `test_parent_close_after_retain_before_reserve_preserves_child_and_balances_refs` covers both public spellings; the existing full-capacity transfer barrier holds the child until parent Close and waiter completion. `tests/test_forklimit_transport.py` covers late reservation cleanup without target creation. |
| Disposal | Public `TestConsumedCaptureRetainsCleanupAndStableCloseResult`, `internal/forklimit/disposal_test.go`, existing owned-Snapshot interrupt tests, and `tests/test_handoff_failures.py`: consumed/preserved state, original errors, retained cleanup, duplicate Close and unreturned late baseline ownership. Controlled faults are not guest OOM reproductions. |
| Live | Go actual consumer and Python source/installed consumer capture cap2, hold its spare slot, require busy to preserve data/generation and reset after release. Cap1 rejection and drain-reservation return have unit/control detectors. |
| Live cleanup recovery | `internal/live/capacity_test.go`, public Go adapter retirement tests and control `TestControlAdapterCapTwoRecoveryJoinsBothCleanupOwners` / `TestControlAdapterRecoveryCannotForgiveUnrelatedDebtOrParentClose`; Python `test_new_remote_debt_during_reset_is_not_forgiven` covers debt during retry and reply. Pool recovery/Close barriers own the atomic race. |
| Python entry | `tests/test_forklimit_entries.py`, `tests/test_forklimit_unit.py`, `tests/test_p1_pytest_entry.py`: settings propagation, both Fork spellings, None/callable/PrepareCommand semantics, ownership and worker admission. |
| Python watchdog | `tests/test_forklimit_transport.py` holds replies after reserve/export/start across timeout/KeyboardInterrupt and late success; `test_stuck_control_writer_has_bounded_callers_and_one_writer` fills the non-reading host pipe; responsive-full finite/indefinite waits have separate timeout/Close tests. |
| Supplied pytest wait | `test_held_child_fails_with_finite_deadline_and_stops_next_admission` observes actual pytest reports and keeps the held child usable. Setting/default30 and None/range validation are separate declaration/propagation tests; the held-child deadline uses a short explicit override. |
| Handoff | `tests/test_handoff_failures.py`, `tests/test_forklimit_transport.py`, control actual-backing ACK/export tests and actual different-binary/resnapshot/whole-host-loss cases. A source acknowledgement is not inferred from dropping Python refs. |
| Existing Go fixture | `mariamemtest/fixture_test.go` cap propagation, admission, cleanup ordering/debt and Close; existing G1 physical fault/campaign owners remain. Default2 and outer/inner occupancy remain explicit; the prior backing-close mutation detector was preserved. |
| Owned E2E entry | `tests/test_e2e_entry.py` validates before allocation and forwards explicit2; the real Live/controlled browser two-case oracle is in `tests/test_owned_snapshot.py`. Existing owned E2E examples/installed owner carry the browser/framework profile separately. |
| D1 serial | `tests/test_django_prepared_owners.py` declaration, independent auto and cap1 ordering; existing `tests/django_prepared/run.py` runs both prepared case classes under standard runner/pytest, now asserting cap1/finite waits at capture/Fork. |
| D1 failure/xdist | Controlled preserved/consumed/setup/cleanup failure cases plus existing `tests/django_prepared/xdist/run.py` load/loadscope, idle/controller, crash/replacement and cleanup-failure cases. Every capture/Fork is traced for declared cap1/finite wait; the prior source run is not final-candidate evidence. |
| CPU documentation | Go/Python/Live/D1/E2E guides and unreleased notes call auto a memory heuristic, recommend explicit tuning and distinguish per-worker totals. CPU-optimal settings, P16, new RSS/queue campaigns and prewarming #84 remain outside this exit. |

## Existing execution owners

- Development's daily check executes source/unit detectors and representative
  source smoke; ordinary PR success does not imply the full matrix ran.
- `scripts/verify.py integration --host` owns source actual-guest/race regression
  execution, including the full owned-Snapshot module, on existing core hosts.
- `.github/workflows/live-host.yml` now names Fork-limit unit/transport detectors
  and bounded actual-guest cases inside its existing two-interpreter loop, and
  runs its installed consumer under both3.11/3.14 on macOS15/Ubuntu24.04.
- `.github/workflows/django-lifecycle.yml` already executes the updated installed
  D1 serial/xdist owners on those same OS/interpreter boundaries.
- Existing workflow contract tests detect missing detector paths and per-minor
  installed result binding. They cannot prove runtime results: matrix receipts
  still have to be produced, checked and source-bound.

No new trigger/job or qualification pipeline is introduced. Integration and
release remain their separate decisions. Known pending execution is not labelled
"inconclusive research"; an unexpected test failure is reported and repaired under
the same fixed contract rather than adding another acceptance theme.
