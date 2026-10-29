# Owned entry physical-session acceptance controls

After installed-consumer CI succeeded, add a finite real-engine check for the
hook/Live boundary. This is a controlled app hook with actual embedded MariaDB,
Snapshot, Live and driver-owned TCP sessions; it is not a full application/job
scheduler or new SQL compatibility claim.

- The app starts with an idle physical SQL session. A deliberately lying
  QuiesceAndRetire returns nil without closing it. Live Reset must return Busy,
  preserving the ready generation and physical session. The entry must latch
  failure and reject later acquisition without retrying the hook.
- A correct hook retires the physical pool before even the first Reset. Two cases
  then each observe the original seed, reuse the same UNIQUE value and close
  their registered pools before the next case.
- A subprocess executes the public Case(t) adapter: both initial busy setup and
  later latched admission fail before body, app cleanup is confirmed, and exactly
  those intentional failures are retained. A missing marker, extra/missing failure,
  timeout or accidental body execution fails the parent control.

These controls are opt-in (`E2E_OWNED_RUNTIME=1`) and run in existing Live jobs on
both hosts. Ordinary component check skips the physical controls; the helper
subprocess entry is a no-op unless selected by its parent. The new SQL table is
fixed diagnostic input, not a native-comparison workload. No guest/runtime/API
behavior changes are included.

Installed happy-path evidence is retained separately under
[e2e-installed-ci-40854876547](e2e-installed-ci-40854876547/assessment.json):
attempt2 succeeded on macOS15 arm64 / Ubuntu24.04 x86_64, both Python minors,
with full artifact ZIP digests verified against GitHub. PR head44062286 and actual
merge source2d10efff remain distinct. Attempt1 was cancelled by the account
operator; the Human explicitly requested retry. No failure/receipt was relabelled.

Remaining #18 conditions still include registered delayed-job pause/join, partial
Live/compound cleanup and other full hook failure controls where evidence is not
yet mapped, plus first/second/repeat time/resource and retained-baseline campaigns.
Main adoption and release remain separate decisions. The installed success is
not full EP1/EG1 completion.
