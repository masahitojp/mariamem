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
- Normal PR daily checks remain required. The manual `disconnect-notify.yml`
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
