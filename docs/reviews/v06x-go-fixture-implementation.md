# G1 first implementation checkpoint

Latest status: the [both-host time/resource campaign](v06x-go-fixture-campaign.md#both-host-resource-time-receipt-confirmed--run40730646806-attempt2)
passed at executed source b594527 (PR head e8c0380). This closes the campaign
receipt gap; actual backing/disposal fault controls and an installed helper
consumer remain outstanding. The earlier checkpoint descriptions below retain
their original evidence context. G1 completion/main adoption/release are not declared.

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

## Local observation — 2026-10-29

Code source_commit `5c739b7d4df84b13a16374ebbce00bec45ee69c4` was inspected
with scripts/git_identity.py before verification. Observed host: macOS27.2
arm64, Go1.26.10, Python3.14.9. This is not a macOS15/Ubuntu matrix receipt.

| Check | Observed result |
| --- | --- |
| scripts/verify.py check (full) | PASS: generated source/inclusion, 22 source-oracle Python tests, Go unit/vet, then1167 Python PASS /47 explicit SKIP /76 subtests; one existing shadow_maria registration warning; public source check PASS |
| go test -race ./mariamemtest -count=1 -timeout=60s -cover | PASS; statement coverage81.9%, component mocks rather than raced actual-guest qualification |
| go test -p 1 -tags=integration ./tests/gointegration -run '^TestFixture' -count=1 -parallel=4 -timeout=3m -v | PASS: normal/reverse and four parallel prepared children, prepared parameters, committed schema/data changes, ordinary-failure subprocess, original1146/42S02 |
| Exact Go block extracted from docs/go-prepared-fixture.md, go test with -shuffle=on | PASS: TestMain/Run plus both tests, observed Seed-before-Commit order on this source |

The first full-check attempt failed three unchanged Python routing tests because
SQLAlchemy was absent from the selected local venv. Installing the existing
fixed tests/routing_acceptance/unit-requirements.txt restored the final full
PASS above; no test or client was relaxed. The broad Python suite is not the
separate Connector/Python/OpenSSL runtime integration gate.

Follow-up commits may update status/records without relabelling this observation
as a different tested source. The contract lint's runtime NOT_RUN refers to the
lint itself/full future campaign; these specific local correctness results do
not grant full G1 acceptance. Both-host CI and all remaining resource/disposal/
installed-consumer work above are still pending.

## G1 campaign follow-up

The [campaign and checkout correction](v06x-go-fixture-campaign.md) now implement
actual cap/parallel/time/retention/resource observations and require both CI host
receipts. Local macOS27.2 arm64 observations passed at232fc19, including an actual
pre-admission guard STOP. Original failed and successful local receipts are
preserved separately with checksums. The original local code observations above
remain pinned to5c739b7; they were not relabelled.

The macOS15/Ubuntu receipts were pending at the first checkpoint; the
time/resource receipts are now confirmed in the latest status above. Full G1
acceptance still requires the fault/consumer work below. Disposal/backing fault controls and installed-helper consumer
acceptance remain separately tracked. The declaration lint is no longer the only
check: selected Live CI jobs execute the campaign, and the existing required
aggregate rejects missing/stale/incomplete measurements or either host artifact.

## Physical faults and installed-helper follow-up

The [completion implementation and local verification](v06x-go-fixture-completion.md)
now cover the remaining fault/consumer mechanisms: real FD/temp state at the
root/fixture interfaces, 8 semantic mutations and a separate private-module
consumer exercising public Run/DB(t) with command failures and cancellation.
Fault injection found and fixed capture cleanup overclaiming; the helper now
separates its own owner finalization from unverified capture-internal cleanup.
Local final source 50f9817 passed. Fresh both-host source-bound completion receipts
remain pending, so full G1 acceptance/main adoption/release are not declared.
The earlier b594527 resource receipts retain their original source and attempts.
