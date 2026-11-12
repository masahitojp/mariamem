# Issue156 controlled generated guest

Scope: establish whether the native pending-clear mechanism also occurs through
actual generated MariaDB pool/task code and Go/WASIX thread/futex execution.
This is not SQL/PREPARE attribution, performance measurement, or product adoption.

Baseline source_commit: 8df45792a927e440972266ee799d6f7223713e14.
Guest SHA256: 332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22.

Fixed matrix: pending/unreported + explicit maintenance; pending/reported;
late submission. Each at concurrency 1/16, three repetitions: 18 cases.
A worker init callback gates first creation. Synthetic A blocks on actual WASIX
futex; B signals completion. Actual pool scheduling and task::execute run.
Only this pool's periodic timer scheduling is suppressed; real maintenance is
primed empty and then invoked explicitly. Unreported arm must remain queued for
50ms, with pending clear/one active/no waiting, then progress on maintenance.
Reported/late arms must progress without that maintenance trigger. All tasks
release refs, pool destructor returns, StartInstance joins actual guest workers,
and active mappings return to warmed baseline. Case scheduling >250ms before
recovery invalidates the case, not counted as a favorable result.

Exact-function hashes guard diagnostic overlays. No canonical/generated runtime
files change. One Go diagnostic build; no guest rebuild, CI, natural SQL sampling,
or timing retries. Tooling budget 30min, execution deadline 120s. If bounded
construction fails, preserve failure and missing step rather than broaden scope.
macOS arm64 only. End with compact cases/events/source bindings; clean owned
cache/test binary/overlay. Keep #156 open until original-tail attribution or
an explicit disposition; a controlled PASS alone cannot close it.

## Harness preflight correction

Initial diagnostic build succeeded; first case was INVALID before A started,
with an unaligned-atomic trap. Source inspection showed Fn157 is aligned
allocation (malloc fast path), not calloc. Uninitialized task.group made the
synthetic task invalid. Explicit zero initialization and alignment assertions
are required before submission. Preserve attempt1; perform one bounded harness
repair/relink, not additional natural sampling. Matrix/oracles remain unchanged.

Second harness attempt reached the final hook-count assertion, then root panic
prevented normal guest shutdown. One 3s stack-only execution (same binary) showed
that exact assertion plus ordinary guest background workers awaiting shutdown.
Unlike the native standalone test, normal guest startup also creates another
pool. Scope timer suppression to the controlled constructor; filter events by
its exact pool pointer. Keep normal guest timers untouched. Final harness-only
repair/relink is bounded; preserve both INVALID attempts and the diagnostic.
