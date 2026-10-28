# Issue #5 — main adoption review and Human decision

## Decision

Recommend adopting source_commit `8383f09b4043eafed07fcb048f8edcbde30d0c6a`:
the previously hanging TEXT/BLOB temporary-table path now matches the native
reference, and actual worker failures notify callers before joined cleanup on
both supported hosts. The Human approved adoption in the task conversation.
The strongest concern is resource ownership after a fatal worker trap. Controlled
running-owner tests preserve the join-before-unmap rule, and actual guest tests
exercise failure, cleanup and independent DB survival on macOS and Ubuntu.
Non-cooperative Go execution still cannot be forcibly stopped; this limit is
explicit rather than hidden by early resource release. No blocking gap was found
within this bounded repair. Integration must use the existing protected PR path;
qualification and publication are separate decisions.

## Pinned objects and cross-checks

Inputs reconstructed from the investigation, repair report and task history:

- Candidate: `8383f09b4043eafed07fcb048f8edcbde30d0c6a`.
- Original baseline: `cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`.
- Current main integration base: `0cf113e3c7da9d197a151331ebd7abf9baceb464`.
- Reviewed artifact: [repair report](issue5-host-repair.md) at the candidate SHA;
  prior conditions: [investigation](issue5-text-dedup.md), Issue5 definition of
  done, project-status authorized implementation and development completion rules.
- One metadata read of [CI40737308463 attempt2](https://github.com/masahitojp/mariamem/actions/runs/40737308463/attempts/2)
  returned candidate headSha exactly, completed/success, and successful full check,
  integration, native reference and both worker-failure host jobs. Attempt1's
  runner communication failure remains historical FAIL with unknown root cause.

| Prior condition | Judgment and evidence |
| --- | --- |
| Bind the canonical host import, preserve FD ownership | Satisfied: `scripts/generate_runtime.py:85`, `internal/generatedgo/host_dup_test.go`, `code/base/fd_dup_test.go`; native equality and race jobs succeeded |
| Prompt fatal failure with original cause and explicit instance fate | Satisfied: `code/base/runtime_failure.go`, `internal/guest/linked.go`, `internal/guest/worker_failure_test.go`, `internal/mysqlwire/worker_failure_test.go`; actual guest trap step succeeded on both hosts |
| No unapproved guest patch or blanket WASIX expansion | Satisfied: candidate diff leaves guest inputs and translated bodies unchanged; remaining14 imports inventoried in repair evidence |
| Finite native matrix on both supported hosts | Satisfied: both-host exact-source/native-equality steps succeeded in run40737308463, together with SQL and Snapshot/Fork regressions |
| Regression fails on original runtime and passes after repair | Satisfied: original three failures retained in investigation evidence; repaired SQL cases passed in local evidence and both-host CI |
| Generation ownership/provenance and current failure contract documented | Satisfied: canonical adapters, handwritten inventory, two generated hashes, explicit source-only license continuity, Go/Python/architecture guides; full check succeeded |
| Main integration checks on combined tree | Pending: current main has separate docs/Live selector updates; protected PR check/integration/Live gate must pass before merge |

## Detection net and remaining limits

The worker/descriptor lifetime concern is covered by ownership races,
`runtime_failure_test.go` (held non-cooperative owner and cancelled waits),
`memory_controlled_test.go` and actual `worker_trap_integration_test.go`.
SQL follow-up, native result bytes/multiplicity/materialized DML and Snapshot/Fork
are covered by maintained comparator and SQL tests. Adapter/preimage and comparator
negative controls remain enabled. Existing failure oracles are not weakened;
prepared consumer bounded exceptions retain their original functional FAILs.

General reachability of all14 remaining panic imports, arbitrary non-cooperative
Go execution, performance and dbt replay are not established by these checks.
No CI test proves universal absence of worker deadlock or a bound on arbitrary
worker retirement. The adopted behavior fails the instance promptly while
retaining live-worker memory. Those limits do not negate the observed repair.

Missing-things scan: no unlisted adoption condition, current-guide contradiction,
generated ownership mismatch or stale changed-path contract found. Independent
full guest regeneration and release/library requalification are not claimed;
source-only continuity retains prior audit identities and unchanged guest inputs.
No new public API, connection-limit or Live reset contract is adopted. README and
release guidance need no repair-specific change because those boundaries stay
unchanged. Cold-vs-warm performance and broad workload support are out of scope.

## Integration and limits of this review

Construct a production commit from the candidate diff on the current main base,
without merging exploratory history. Preserve current main changes and the
original reports; add only this decision/status record. Confirm the production
files match the reviewed candidate and submit a protected PR. Main has strict
freshness, admin enforcement and three Actions-app-bound required contexts:
`check`, `integration`, `Live required gate`. No bypass is permitted.
Repository auto-merge is disabled; do not change repository settings to avoid the
existing merge gate. The protected PR must finish before adoption can be marked
landed. The issue stays open until integration completes.

This review inspected the changed failure path, canonical adaptation, ownership
controls, provenance delta, guide changes, current main delta and exact run
metadata. It did not rerun unchanged runtime suites locally, repeat release
qualification or reclassify historical evidence as a new integration-source PASS.
