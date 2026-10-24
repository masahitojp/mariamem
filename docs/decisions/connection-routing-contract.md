# Scoped connection routing — conditional implementation approval

On2026-10-24 the Human conditionally approved production implementation following
the [implementation review](https://github.com/masahitojp/mariamem/blob/c22bc213da4bfd97b42f1f5d80e59bd54274d141/docs/reviews/v06x-connection-routing-implementation-review.md).
The subsequent four requested corrections are defined in the
[approval/corrections record](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-review-fixes.md).
Both OSes passed17 spike cases and six strict mutations in
[CI40035962925](https://github.com/masahitojp/mariamem/actions/runs/40035962925)
at source_commit `006f68dd476dfc77c8fe3c1d5f66af37b2007513`.
The source-bound evidence remains at that pushed experimental lineage; this
decision does not relabel it as verification of the production replacement.

## Approved boundary

- Optional Python routing keeps ordinary driver/SQL behavior and selects one
  independent test child. Default acquisition/fixtures remain unchanged.
- One named profile includes original host/port/schema. Another/missing schema
  on that endpoint rejects before dial; other endpoints remain unregistered.
  No schema/SQL rewrite, original-target fallback or transaction replay.
- Guard installation precedes application connection activity. A shorter
  context-local, revocable lease binds a child. Missing/expired/closed targets
  refuse with stage/reason/context and a next action. Context propagation and
  cooperative application shutdown remain explicit.
- Initial pinned entries: PyMySQL1.2.3 direct/saved/deferred/reconnect;
  Connector/Python26.7.0 module factory/default/prepared; SQLAlchemy2.0.54
  default mysql+pymysql QueuePool with explicit enrollment. Required TLS and
  unsupported transports/options refuse on the enrolled entry. Saved advanced
  Connector factories, custom/native handles and arbitrary live applications
  are outside this support boundary; provide explicit configuration/adapter
  guidance rather than silently broadening interception.
- Go uses child-owned settings/pools and ordinary application/GORM injection.
  No shared context-switched Go pool or public Go API change.

## Ownership and lifecycle

`register_engine(..., ownership="test")` hands over administration of a quiescent test
engine's pool, not ownership of the Python Engine object or child DB/Snapshot.
Caller stops application activity before enrollment. Existing checked-out
connections/transactions reject enrollment without closing or rolling them back.
Initial enrollment may dispose unknown idle entries. Normal lease teardown
drains tracked checkouts and closes only its owned physical sessions; it never
globally disposes the shared engine or another live lease's sessions.

Explicit registry close requires all bindings/users/checkouts finished. It may
dispose remaining idle entries and detach its owned hooks. Failed drain/close
retains protection and reports unreleased ownership for explicit retry. No new
bindings are admitted during a failed close. Original setup/test exceptions
survive cleanup failure; structured cleanup errors remain accessible on supported
Python versions. Child Close follows the caller/fixture's existing lifecycle.

Pytest enables protection from static configuration in its early plugin hook,
before conftest/test imports. It integrates the existing session baseline and
function child. Each xdist worker retains its own registry/baseline; there is no
cross-worker/cross-run shared baseline. No minimum Python/pytest/platform change.

## Approved application-test entry — implementation pending

On2026-10-24 the Human accepted the
[marker/preparation entry and naming direction](../reviews/v06x-shadow-maria-entry-design.md#approved-public-surface--not-yet-implemented).
The normal entry is no-argument `@pytest.mark.shadow_maria`; optional
`mariamem_app_db` exposes the same per-test child. `mariamem_prepare` returns a
session preparation callback taking the source DB, once per worker before
Snapshot. For0.6.0, preparation receives explicit DB settings; automatic
preparation routing is excluded and retained for0.6.x reconsideration.

Approved controller/adapter names are `mariamem_router`,
`mariamem_sqlalchemy_engines`, `routing.Router` and `register_engine`.
Extras are `routing-pymysql`, `routing-sqlalchemy` and
`routing-mysql-connector`. Superseded unreleased candidate names require no
compatibility aliases; existing published APIs remain. The tested candidate
uses the old `enroll`/`Registry`/fixture names and has not yet implemented this
approved surface. Ownership semantics above are unchanged by renaming.

Live behavior remains a separate task, including a0.6.0 scope decision based on
required internal changes. Neither marker approval nor this contract adds reset,
shared-state modes, multiple profiles or preparation-time implicit routing.

## Acceptance and separate decisions

Production replacement must preserve the17-case/six-mutation SQL oracles and
their exact failure classification. Add hook install/unwind/conflict, retirement
during connect, ownership/disposal boundaries, drain failure/retry, diagnostic
redaction, verification-floor/current Python/pytest and early-import/worker tests.
As directed by the Human on2026-10-24, future verification excludes EOL
Python3.9/3.10 and starts at3.11; prior receipts remain historical evidence.
This verification policy does not itself change package minimum metadata. Both
native OSes remain required; explicit Ubuntu Connector C may retain its known
import SKIP, while default/pure must execute. Tests cannot call accepted Prepared
exceptions PASS; their [decision](prepared-consumer-exceptions.md) is unchanged.

API implementation under this contract is approved. Main adoption, version
placement, Qualification and release remain separate Human decisions. Broader
frameworks, migration/dump preparation and other capability-map work remain
visible companion work, not implicitly supported or removed from v0.6.
