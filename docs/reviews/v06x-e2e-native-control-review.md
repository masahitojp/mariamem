# Native E2E control — CI receipt and next comparison

Decision now: use the executable order-entry/browser control as the reference
for the next mariamem comparison. **Recommend accepting it for that purpose.**
Both supported Python versions on native Ubuntu execute the real Python and Go
child applications, preserve exact post-commit-failure isolation, and detect
actual skipped-reset and restarted-app defects. This is now a reproducible app,
not only a requirements document. The strongest objection is that native Python
flush/reseed is a different mechanism from guest baseline restoration. That is
acceptable for defining observable app behavior, but it cannot establish live
feasibility or justify advertising mariamem support.

No new product API, general Django adapter or live implementation is approved by
this review. Go's existing per-test Fork/configuration route is the smaller next
comparison; Python's retained-process/DB-address requirement still needs a bounded
live/reset design. Those two paths must retain their different lifecycle claims.

## Reviewed source and evidence

Reconstructed from the user's successful-CI report and previous handoff:
source_commit `3446b5c927239542fb4203d5c6b4a4342c6b4984`, branch
`experiment/e2e-native-control`. Its direct predecessor with local functional
receipts is `0776d7a368a1e162e3884bec9a84b23031ad8e59`; the difference is only the
native CI workflow's environment/scratch fix. Main runtime basis remains
`bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. This review is written on
`design/v06x-dogfood-e2e-plan`; it does not relabel any tested source.

The [executable/local report](v06x-e2e-native-control-results.md),
[first guide target](v06x-e2e-guide-target.md) and
[whole workload plan](v06x-dogfood-replanned.md) are the cross-check basis.
[CI40286173347](https://github.com/masahitojp/mariamem/actions/runs/40286173347)
is success on exact3446b5c, with job121450249234 (Python3.11) and
job121450249509 (Python3.14). Saved
[assessment](v06x-e2e-native-control-evidence/ci-40286173347/assessment.json),
[metadata](v06x-e2e-native-control-evidence/ci-40286173347/run.json),
[jobs](v06x-e2e-native-control-evidence/ci-40286173347/jobs.json),
[artifact identities](v06x-e2e-native-control-evidence/ci-40286173347/artifacts.json)
and [checksums](v06x-e2e-native-control-evidence/ci-40286173347/SHA256SUMS.json)
retain original ZIPs losslessly as base64. Their SHA256 digests were independently
verified against GitHub. Raw XML/event streams were independently reclassified
using the pinned oracle, then checked for exact source/build flags, app/browser
version and observed semantics. CI was not rerun or polled by this review.

| Boundary | Native positive controls | Real defect injections | Result |
| --- | --- | --- | --- |
| Ubuntu24.04 x86_64, Python3.11.17 | Python and Go | skipped reset and restarted Python app | PASS reference / both detected |
| Ubuntu24.04 x86_64, Python3.14.8 | Python and Go | skipped reset and restarted Python app | PASS reference / both detected |

Both CI jobs use Django5.2.8/mysqlclient2.2.7, Playwright1.56.0 and Chromium
141.0.7390.37, native MariaDB12.3.3 and source-stamped Go1.26.10 applications.
The Ubuntu mysqlclient build uses native client library8.0.46; the earlier Mac
control used Connector/C3.4.11. These distinct observed dependencies are recorded,
not generalized to every client library or represented as identical builds.

There are two normal parent campaigns and four detected real mutations across
the two jobs. Their36 raw browser cases include exact intentional failures and
mutation setup errors;36 must not be described as36 passing tests. Go controls
continue to pass when the Python lifecycle alone is deliberately broken.

## Prior conditions and what detects regressions

| Condition | Judgment / evidence |
| --- | --- |
| Actual authored app, real browser and separate server process | Satisfied for this finite order app. source tests/e2e_native_control/browser_cases.py performs DOM form submission; conftest.py launches child processes and records browser/app identities. Raw UI tests and committed rows agree. |
| Python retains its app/HTTP endpoint across sequential cases | Satisfied for native control: positive events have one start/PID/URL, three reset boundaries, seed before each case and A's committed rows only in A. run.py assess checks those facts. |
| Go gets independent per-test child/configuration | Satisfied for native schemas/apps: three PIDs/schema names and graceful exit0 before schema removal. These are native schemas, not observed mariamem Forks. |
| Failure after commit does not poison next test | Satisfied for the prescribed failure: exact test02/message/exit1 and test03 seed-only state required. Generic failure/skip/setup error cannot pass the positive assessor. |
| Detect fake success from omitted reset or app restart | Satisfied for these two actual mutations. run.py mutation_detected requires stale ORDER-A rows/expected setup counts or the exact four-start/three-case-PID signature, with cleanup. Static oracle mutations also run in CI. |
| Native acquisition and source/Go identity | Satisfied for observed Ubuntu inputs: acquisition receipt PASS binds current source; runner verifies clean exact commit and compiler/VCS stamp. No stale binary accepted. |
| Durable source-bound receipts, original failures retained | Satisfied. Both raw ZIP digests and encoded-file checksums verified; local0776d7a results, initial29c8515 DOM failure and workflow-rejected run40285909685 remain under their own source/status. |

No blocker was found to using this as a reference input. It does not close the
entire guide/workload plan: startup capture, persistent physical-session behavior,
background workers, multi-worker concurrency and general Django runner behavior
are not exercised by these cases.

## Next mariamem work and remaining detector gaps

1. Keep the same Go app/browser operations and preparation rows. Replace only the
   native per-test schema allocator with existing mariamem Snapshot/Fork plus
   explicit child DSN, preserving shutdown before DB close. Record native/guest
   comparison and exact failure classification rather than changing the app's SQL.
2. For Python, specify the smallest retained-app/stable-DB-address experiment.
   Current Snapshot consumes a disconnected source and new children receive new
   listeners (pytest_plugin.py:117–129; internal/host/server.go:94). The reference
   fixture's native flush/seed is not an implementation of that missing primitive.
   Define accepted connection retirement/reconnect, busy behavior, reset failure
   admission, ready boundary and baseline source before choosing host/relay changes.
3. Retain the real defect oracles and add guest-specific late-writer, held-
   transaction/reset failure and cleanup gates. Existing native tests cannot
   detect incorrect MariaDB guest restore or prove physical-session preservation.
   This is a concrete CI blind spot, not proof that such behavior is impossible.

These are scoped next comparisons/design deliverables, not permission to add a
public reset API or reinstate automatic preparation routing. A browser proof may
use disposable test-only orchestration; productization is a later reviewed step.

## Missing-things scan and limits

No current README/Go/Python/releasing contract, runtime API, guest/generated
ownership/HANDWRITTEN_FILES, provenance/version or release-ledger change is
introduced here. No stale public-support claim was found: the executable and
reports label native control explicitly. No broad runtime checks/regeneration
are warranted for the evidence/status/review-only changes in this task.

Native macOS MariaDB-server coverage remains unverified; the local Mac app/browser
control used a Linux amd64 Docker Desktop server. Opposite supported app host
coverage is not the same as proving both native server platforms. No multi-worker,
background worker, other browser, full Django runner, startup capture, large-load,
cold-install or performance result is claimed. Those remain visible cells in
the plan. This receipt does not satisfy mariamem E2E acceptance, a live spike,
main adoption, Qualification or release.

Verification here: original ZIP/file checksums, source-bound metadata, raw XML/
events, candidate diff and local references/public-source/whitespace checks.
No new browser, runtime test, benchmark, CI submission or integration was started.
