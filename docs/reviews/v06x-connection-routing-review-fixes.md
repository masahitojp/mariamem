# Connection routing — conditional implementation approval and review corrections

2026-10-24. Source_commit: `c22bc213da4bfd97b42f1f5d80e59bd54274d141`,
the [implementation Human Review](v06x-connection-routing-implementation-review.md).
The Human conditionally approved production implementation, then requested the
four corrections below. Approval remains limited to the
[declared implementation boundary](v06x-connection-routing-product-design.md);
main adoption, Qualification and release remain separate decisions.
Branch: `experiment/connection-routing-review-fixes`.

The previous15-case/six-mutation observations remain evidence of what ran.
The subsequent review exposed a permissive fallback gate and missing schema/TLS
combinations, so that earlier completion statement must not stand in for these
additional checks. This follow-up requires17 control cases and the six retained
mutations under contract `routing-r1-r8-profile-tls-v3`. **Native results are
pending; the six local receipt-gate tests PASS.** Production implementation
continues under the conditional approval after these corrections are verified.

## 1. Fallback mutation: reject the wrong failure reason

Previously `assess` accepted fallback if the expected case failed and the
sentinel saw an attempt, without requiring the expected exception type/cause.
The preserved native receipts really show the controlled listener's immediate
disconnect (OperationalError2013); no different SQL error was observed. However,
the gate could accept a different failure and did not substantiate the stronger
claim in the design that an unexpected SQL error cannot close an oracle.

The campaign now converts **only** OperationalError2013 plus exactly one newly
observed controlled-original contact into an AssertionError with structured
observation `{reason: original_endpoint_contacted, sentinel_delta: 1,
driver_errno: 2013}`. Other driver/SQL errors propagate normally. The runner
requires that AssertionError, exact observation, expected case, exit1, one
sentinel contact, no fatal error and completed cleanup. It does not treat a
generic connection failure as successful detection.

The new contract test accepts that exact outcome and rejects SQL error1054,
wrong exception type, wrong errno/reason, zero/two contacts, wrong case, fatal
setup and failed cleanup. The old permissive OperationalError receipt is now
rejected by the new gate; its historical result file is not edited. The five
other original mutation receipts remain accepted. Synthetic gate tests are not
new runtime PASSes.

## 2. Schema is part of the registered profile

Profile selection now checks host, port **and requested schema**. The initial
contract is one registered application schema. Another or missing schema on the
same registered endpoint raises `schema_mismatch` before opening a connection;
it is neither redirected silently nor passed through to the original endpoint.
Another endpoint remains outside this registered profile.

PyMySQL constructor and deferred/reconnect paths, Connector module/common
connect paths, and SQLAlchemy enrollment apply this rule. A tagged reconnect
also checks schema after its endpoint has been replaced with child metadata.
PyMySQL's deprecated `db` alias follows the pinned driver's precedence over an
absent/None `database`; schema comparison does not rewrite SQL or change names.

New real-guest case `schema-profile-boundary` checks a different and omitted
schema, an object deferred before install, a matching-endpoint SQLAlchemy engine
with another schema, and normal/saved ordinary Connector factories where
available. Required result is explicit refusal with no original-endpoint contact.
Existing named-schema/qualified-SQL cases remain. Multiple-profile mapping and
advanced saved Connector factories remain separate boundaries; the correction
does not implicitly introduce either.

## 3. Required TLS on an object deferred before install

The exact pinned PyMySQL1.2.3 wheel is
[this recorded input](https://files.pythonhosted.org/packages/a9/4b/0a906d8184f011ff8dbd4722743783867589b33269d2c5fff238d636fdcb/pymysql-1.2.3-py3-none-any.whl),
SHA256 `14f1c68e2ed859243ae5ca41ffbe677027fc46bc136a9f0be8a4e928e5e7415a`.
Its `pymysql/connections.py:276–305` stores explicit required TLS in
`_ssl_required=True`; ordinary PREFERRED mode has it False. This field is set
by the original constructor even before the routing constructor hook exists.
The current connect hook already reads this field, so no TLS downgrade or new
TLS implementation is needed for this correction.

New case `deferred-tls-before-install` constructs an explicit TLS/deferred object
before installation, confirms it has no hook-created TLS marker, binds a child,
and requires `tls_unavailable` before socket creation. It then checks that the
required-TLS flag remains True. Existing pre-install default/deferred connections
still have to pass R1, and post-install required TLS still has to reject in R6.
The source finding is confirmed; the combined native case remains pending.
The downloaded source file also matches the previous CI's installed-file hash.
A local constructor probe confirmed required/default TLS flags True/False with
no socket opened; this does not substitute for the pending combined guard test.

## 4. Meaning of `ownership="test"` in the product API

This is an explicit administrative handoff for a **quiescent test-owned engine**
and the physical sessions created through its enrolled adapter. It is not
permission to take over arbitrary application resources. The engine object
remains the caller's object; the adapter gains the following bounded authority:

| Boundary | Permitted action | Required condition |
| --- | --- | --- |
| Enrollment | `engine.dispose()` to discard all pre-existing idle pool entries, then install the ownership/checkout adapter | Caller has stopped application activity; no checked-out session/transaction. Refusal leaves active handles and transactions unchanged |
| One test lease exits | Drain that lease's cooperative work/checkouts, then close/invalidate **only its owned physical sessions** | Never globally dispose the shared engine or touch another live lease's session. A drain timeout reports unreleased ownership instead of claiming cleanup succeeded |
| Registry/adapter is explicitly closed | Dispose remaining idle entries and detach its hooks | All leases are retired, caller has stopped registered users and no checkout remains. If those conditions fail, report `active_pool`/cleanup failure and retain protection until an explicit successful retry |
| Caller retains an external handle | No automatic close, rollback, statement replay or reassignment | The caller must release it before enrollment can succeed |
| Child DB / Snapshot | No ownership transfer through engine enrollment or `bind` | Fixture/caller retains Close and the existing consuming-Snapshot contract |

The helper does not destroy the Python Engine object. After successful registry
removal that engine may create connections under its original configuration;
registered users must therefore stop before removal. The engine remains enrolled
across normal test leases, with per-record invalidation rather than per-test
`engine.dispose()`. Creating an engine inside an application test factory is the
alternative when a quiescent handoff cannot be provided.

Production acceptance must exercise all three disposal boundaries, active
refusal without rollback, one scope closing while another remains usable,
drain failure, and explicit close retry. These are implementation tests under
the existing conditional approval. The spike's `Router.enroll` has no public
ownership parameter; this definition governs its product replacement, not a
claim that a new public API is already installed.

## Verification and continuing work

The unchanged native workflow will run the17-case control and six strict
mutations on macOS arm64 and Ubuntu x86_64. Required default/pure Connector
execution and the explicit Ubuntu C import SKIP policy remain. Runtime source,
guest, Go/driver pins and existing failure controls are unchanged. No generated
Go is hand-edited. New native outcomes must be recorded before presenting these
review corrections as runtime-verified.

Once the corrections pass, continue the already-approved optional routing core,
SQLAlchemy adapter and early pytest integration, including this ownership
definition and the original production acceptance conditions. No additional
implementation approval gate is introduced by this follow-up.

Local preparation: six receipt-gate tests PASS; pinned TLS constructor probe,
Python syntax,137 local file-link targets, version check and diff check PASS.
No unchanged guest/runtime build or broad integration was run locally.

## Native correction results — 2026-10-24

[CI40035962925](https://github.com/masahitojp/mariamem/actions/runs/40035962925)
passed on exact source_commit `006f68dd476dfc77c8fe3c1d5f66af37b2007513`.
Both OSes passed17 controls and detected all six exact mutations, including the
strict fallback observation. Schema mismatch/missing schema and pre-install
required TLS reject before socket/original-target access. All control sentinel
counts are zero and all hosts reaped. Required Connector default/pure executed;
explicit Ubuntu C retains its known allowed import SKIP. All19 original evidence
hashes and five prototype hashes matched per platform.

[Saved summary and evidence](v06x-connection-routing-evidence/ci-40035962925/summary.json)
retain artifact IDs/API archive digests; per-platform files.json binds scrubbed
paths and original/stored hashes. Earlier pending text describes the pre-CI
checkpoint. The added conditions are now verified for the spike; continue the
already-approved product implementation, with ownership semantics above and its
separate production acceptance tests. No new Human implementation gate is needed.
