# G1 first implementation checkpoint

The Human approved implementation against reviewed design source_commit
`39f97573fe490ad86f37a4dbb25d762141d9114c`, recorded before code in decision
source_commit `5b0a20ef86ec874dd4d52c4b9291297dde061656`. Diagnostic profile is
readable-owned; basic-first fallback was not activated. Stage wrapping, joined
errors and normal testing output cover helper-owned operations without global
assertion/SQL interception. Main adoption and release remain separate decisions.

This candidate introduces the separate mariamemtest package (New, Run, DB,
Close), keeps the root runtime API unchanged, uses the existing pinned MySQL
driver and fixes default MaxForks2/preparation pool1/child pool2. It always
finalizes owned sources through public idempotent Close, registers test cleanup
before publishing pools, retains permits on unconfirmed disposal and closes
owned children actively before baseline shutdown. No guest/generated/runtime
engine change or new dependency is part of this checkpoint.

Component fault injection covers consumed/preserved/invalid sources, partial
backing responsibility, combined errors, setup failure, bounded acquisition,
early/concurrent Close, cleanup debt and suite exit behavior. Actual guest
integration is in tests/gointegration/fixture_test.go: prepared schema/rows in
normal/reverse order and four parallel cases, committed DDL/data mutation,
an intentionally failing subprocess followed by a healthy child and exact
1146/42S02 preparation error propagation. Component mocks are not proof of
actual backend/temp/backing disposal; existing root ownership tests remain
anchors and additional G1 fault/runtime accounting remains an obligation.

## Verification and remaining work

Local verification and CI status are recorded in the checkpoint PR; no new
both-host receipt or resource PASS is claimed by this document. The existing
Development full check discovers package unit tests through go test ./...;
integration adds helper race coverage and discovers actual guest cases in the
existing integration package. Those are correctness checks, not the full
timing/resource campaign.

Before G1 is complete, retain source-bound macOS arm64 / Ubuntu x86_64 results,
prove actual cleanup/temp/backing accounting and required mutation controls,
exercise cap1/2 with -parallel1/4/-p1, and record first-test setup, second-test
edits and repeated-batch phase timings. Run the fixed retained-baseline1/2/3
diagnostic with RSS/available-memory/FD/connection/temp counters and finite
guards from the acceptance contract. Do not relabel a warm local run as a cold
setup-cost measurement. Installed helper consumer/example verification is also
separate from the ordinary root module proxy inventory tests.

P1/EP1/EG1 remain required; difficult Django-specific D1 work may be deferred
with its obstacle and remaining work recorded. Shared defects still need
assessment against required entry contracts. This PR is an implementation
checkpoint, not G1-complete, overall v0.6-complete, main adoption, Qualification
or release approval.
