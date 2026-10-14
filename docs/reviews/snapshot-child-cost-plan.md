# Direct-copy child cost — bounded diagnostic scope

Human authorized at 2026-10-14 10:58 UTC, maximum four hours including setup,
analysis, report and preservation/cleanup. Deadline 14:58:37 UTC. Stop earlier
when the question has a useful judgment. This is not permission to fix or adopt.

Question: does the candidate introduce a child-window cost which materially
cancels its approximately 0.43-second large-case Snapshot saving?

Use the existing source `3341f99000246fc64ae17b4ea39118f55589de1e`, one binary
original/direct switch, unchanged guest/runtime/SQL. Add only opt-in benchmark
operation-boundary Go runtime metrics and optional child-only CPU/trace capture.
One unchanged case: 100 MiB, 1 table, 16 serial Forks, CRUD, GOMAXPROCS=2,
Go1.26.8/native macOS arm64. No GC-setting sweep or extra forced collection.

Finite schedule, distinct observation groups; no pooling:
- Two minimal one-child pilots validate SQL and metric availability only.
- Four observer-off controls in original/direct/direct/original order.
- Four boundary-counter runs in the same ABBA order, with no existing periodic
  heap sampler or process-counter helper. Compare the added observer's effect.
- One original/direct child CPU-profile pair and one reversed direct/original
  child trace pair for stack and wait attribution. These are diagnostics, not
  candidate speed estimates. Maximum 12 large scenarios, 192 large child lifecycles.
  Skip a diagnostic pair only if already unnecessary, explicitly report it.

Counters: heap goal, last-GC live, allocated/freed/object bytes, automatic/forced
GC count, estimated assist/dedicated/idle/pause GC CPU, scavenging, mutex waits,
operation wall and process CPU. Go CPU-class estimates cannot be subtracted
from process CPU to invent exact non-GC time. Trace wait totals across goroutines
are not critical-path elapsed time. Profiles are sampled evidence, not proof of
absence. Preserve all samples, including unfavorable/failed ones.

Judge cost attribution and investment separately. Observed recurring candidate
cost which cancels the saving -> report required repair scope, no repair here.
Useful attribution without such a penalty -> consider scoped production work,
retaining uncertainty and platform limits. Mixed evidence or deadline -> mark
unresolved questions accurately, recommend retaining current implementation,
no automatic further campaign. Deadline alone is not completion.

Existing small/medium gains, ownership failure tests, whole-suite reversal and
storage alternatives remain in storage-investment-reassessment.md. Do not rerun
those campaigns. No new backend, Python optimization, guest regeneration,
full qualification, main integration or release. Storage guard: 6 GiB task
budget, 8 GiB free reserve; compact profiles/results retained, disposable clones,
compiler cache and binaries removed after commit/push.
