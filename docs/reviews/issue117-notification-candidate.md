# Issue #117 — disconnect notification product candidate

On 2026-11-07 the Human authorized preparing this candidate toward adoption.
This does not record main integration, qualification or release approval.
The product base is source_commit `0c4e75dc2c21421a59d04661efd72a1f58efecaa`.
The candidate's exact source is the PR head; execution receipts bind their own
source commit. Prior experiment receipts are not relabelled as this candidate.

## Change and limits

`Database.WaitDisconnected` uses a generation notification from the Go host
session map instead of its 5ms polling interval. Count and registration share
one lock; every removal broadcasts to all registered waiters. A new generation
is allocated lazily. Close wakes waiters without requiring their lock, and the
first guest failure has a separate notification from completed worker join.
Every wake rechecks state. Context cancellation/deadline preserves a healthy DB.
Internal backends without notifications retain the old polling fallback.

The three runtime files are `mariamem.go`, `internal/host/server.go`, and the
Go guest manager `internal/guest/guest.go`. There is no MariaDB C/WASM patch,
regeneration, new public option or runtime measurement selector. The guest,
limiter, Database.Close and completed-disposal boundary are unchanged. A zero
session count permits capture; it does not establish completed runtime disposal,
prevent new connections or replace caller quiescence. Keep SQL pools closed.

This benefits callers of WaitDisconnected. It is not a claim that all fixture
teardowns use this method or that DB startup/Fork became faster.

## Evidence motivating the candidate

The [Mac cap comparison](https://github.com/masahitojp/mariamem/blob/bfef4027e1ed7e6a17e95b541c55b247c9f87a11/benchmarks/cleanupcaps/results/README.md)
contains 20 pairs per cap, four callers and 48 children, on one M1 host:

| MaxForks | Mean batch ms, polling → notification | Paired median CPU change |
| --- | --- | --- |
| 1 | 1854 → 1668 | +2.0% |
| 2 | 1015 → 948 | +3.2% |
| 4 | 890 → 676 | +2.5% |

All 60 pairs reduced local cleanup; cap1 reduced batch elapsed in 20/20 pairs,
cap2 in 17/20. Neither cap1 nor cap2 had primary SQL over100ms. The cap4 wall
comparison includes an unequal SQL tail count and is not a transferable 24%
gain. CPU penalty did not increase monotonically with cap; its cause is still
unknown. Cap1 pair1 spans a controller pause, explicitly retained in that report.
Earlier five-pair CPU guard FAIL and additional20 results retain their own
conclusions. There is no automatic rejection/acceptance threshold in this PR.

Those experiments used product `1862f4a89397bddfa1820d835106d3437a438cf7`,
including the separately adopted UCA candidate, with diagnostic Go overlays.
Their performance numbers are not measurements of current origin/main or this
new product candidate. The three affected runtime files are byte-identical
between that product and this candidate's starting main. Only the selected
notification change and relevant tests are ported; exploratory history and
UNDO instrumentation are not imported.

## Finite verification and handoff

- Unit controls: active-session refusal, cancellation/deadline, eight waiters,
  partial disconnect, disconnect before select, concurrent Close, failure before
  join, completed exit, generation renewal and late failure registration.
- Existing retained-resource disposal and worker-trap controls remain intact.
- Real TCP/Pipe: repeated pool retirement, timeout preserves health, multiple
  waiters, capture and two sequential children with cap1.
- Handwritten race coverage excludes `internal/generatedgo/code/...` from race
  instrumentation, explicitly; it is not full generated-engine race proof.
- Normal PR daily checks remain required. The manual-only `disconnect-notify.yml`
  workflow runs the focused boundary on macOS15 arm64 and Ubuntu24.04 x86_64.
- A small manual-only benchmark compares pool.Close + WaitDisconnected on one
  reusable Pipe DB. It hides the notification interface in the polling arm;
  production has no mode switch. SQL/setup and final Database.Close are excluded.
  Six fixed alternating pairs of 48 retirements per arm, plus Go's one-operation
  calibration per process. No retries, outlier removal or timing pass threshold.
  This checks the direction of connection retirement only, not CPU, Fork,
  full cleanup or the earlier48-child batch. It performs SELECT, no UPDATE/UNDO
  attribution, so the earlier holder observer is not needed for this boundary.

The exit is a reviewable minimal diff, local focused correctness results,
and one submitted both-platform CI run with retained source-bound output.
CI owns execution; Ubuntu/macOS15 results remain unverified until they finish.
If this narrow check fails, diagnose it before adoption; do not reopen the
whole startup/UNDO investigation. Full release qualification is a later task.

## Local verification

On macOS27.2 arm64 / Go1.27.3, source_commit
`8e31f4424b53acd5182271ceee62f571edf69c93`. Focused handwritten race contracts and real
TCP/Pipe/capture/cap1 checks PASS. CI selection tests:91 PASS; public-source and
diff checks PASS. This is not a macOS15/Ubuntu receipt. Later changes to this
record and the candidate workflow do not relabel those original executions.


## Development CI trigger correction

Development run [42245489882](https://github.com/masahitojp/mariamem/actions/runs/42245489882)
failed the existing automatic-workflow policy: the candidate workflow had a
branch-scoped push trigger. Python results were 1 FAIL, 1854 PASS, 98 SKIP and
92 passing subtests. Runtime smoke was skipped; integration and the required
gate failed as consequences, not independent runtime failures.

Remove that push trigger; keep workflow_dispatch and the existing policy test.
The original candidate run42245431439 keeps its original source d8a03176.
This workflow/documentation-only correction changes no runtime, test or benchmark
code, and does not require another performance campaign. New PR Development
checks must pass; the original both-host candidate results remain separately
bound rather than relabelled as the corrected head.

Local verification of the correction: `tests/test_ci_efficiency.py` and
`tests/test_development_scope.py`, 115 PASS; diff whitespace check PASS.


## UCA main integration and combined candidate

PR112 merged at main source_commit `61973daa19b6f665d7342338c3252dd7af61fc90`
after successful Development42249730837 on d4409411 (identical Git tree).
The earlier main-base statements describe the first notification candidate.
PR118 now includes this adopted UCA main through a normal merge, without
changing the notification implementation or its oracles.

Original notification run [42245431439](https://github.com/masahitojp/mariamem/actions/runs/42245431439)
PASSes both macOS15 and Ubuntu24.04 at its original source d8a03176. Development
[42247478801](https://github.com/masahitojp/mariamem/actions/runs/42247478801)
PASSes all three required contexts at 5a261ab2 before the new-main merge.
Those receipts do not qualify the combined head. Submit its exact-SHA focused
both-host workflow once; ordinary PR checks also run on the combined head.
The notification-only benchmark remains a narrow retirement observation;
no combined 0.6.2-versus-UCA-plus-notification batch result is claimed.

Combined-head preparation checks:116 CI policy/selection tests PASS; guest,
generated runtime and generation-input bytes match the new main exactly;
public-source and diff checks PASS. Runtime boundary execution is submitted to
CI on this combined source rather than reusing the old-head platform PASS.
