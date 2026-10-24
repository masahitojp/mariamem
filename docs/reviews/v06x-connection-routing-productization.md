# Connection routing — production implementation candidate

2026-10-24. Base source_commit: `9f29194bbddd6a9431a4a250bd2f93ee813734af`,
confirmed by `scripts/git_identity.py` after fetching main. Branch:
`feat/connection-routing`. The Human conditionally approved implementation;
the four added conditions passed both-OS spike CI40035962925. The continuing
[contract](../decisions/connection-routing-contract.md) records authority and
the unchanged main-adoption/release boundary.

## Current result

The candidate implements optional public Python routing, an explicitly owned
SQLAlchemy adapter and early pytest integration. Local lifecycle/early-plugin/
receipt tests pass on Python3.14.8/pytest9.0.2 and Python3.9.6/pytest7.0.0:
31 tests each. The3.14 run additionally reports25 receipt subtests. These tests
exercise real pinned driver/framework hooks with fake connections where no guest
is needed; they do not establish native SQL acceptance. **Production-native
acceptance remains pending.** The earlier spike PASS is not substituted for it.

The user can configure the original endpoint/schema once and use the ordinary
application driver code under `mariamem_routed`. Existing settings/pool injection
remains available for Python and Go. The strongest limitation is the startup/
ownership boundary: installing after SQL or taking over an already-active pool
cannot be made safe retrospectively. The [usage guide](../connection-routing.md)
documents activation, exact entries, ownership and next actions together.

## Implemented change

| Owner | Behavior |
| --- | --- |
| `python/mariamem/routing.py` | Immutable profile, exclusive installed guard, revocable context-local lease, pending-connect/checkout drain, original exception retention, close failure/retry and hook conflict refusal |
| `_routing_drivers.py` | Lazy pinned PyMySQL/Connector hooks; schema/transport checks before dial; retained provenance across failed connects; required TLS from pre-install deferred objects preserved |
| `_routing_sqlalchemy.py` | Optional pinned adapter; quiescent ownership handoff, generation validation and per-record invalidation, invalidated checkout retirement, idle disposal only at enrollment/explicit close |
| `pytest_plugin.py` | Config/CLI early guard, collection-failure unwind, optional registry/engine/function fixtures, worker-local lifetime and disconnect wait before normal child cleanup |
| `tests/routing_acceptance` | Reused17-case business SQL matrix via a test-only facade over the public module, all six exact faults injected outside production, Go prepared consumer and four real pytest/xdist child tests |
| CI / `verify.py` | Minimum/current unit jobs, both native OSes, source-bound host/SDK/package receipts; normal main integration retains native oracles, targeted workflow remains on relevant main changes |

The reused tests retain the exact schema, session state, target, refusal and
original-endpoint oracles. The facade only maps APIs, observes counts, holds idle
resources for the diagnostic generation check and deliberately removes guards.
It contains no implementation of routing. Production code has no mutation flags.
Native pytest additionally exercises four isolated tests with two workers and
the real baseline/function-child lifecycle; its JUnit gate requires4 PASS and
no SKIP/errors. Receipt tests reject arbitrary fallback errors, missing cases and
wrong mutation reasons. Seven compact prior receipts are retained as test data
with source/hash identity; experimental runtime/helpers/history are not merged.

Normal CI/Qualification dependency installation includes the new optional adapter
test pins because these source checks now execute that boundary. Existing pytest
pins at those gates are retained. No pipeline is submitted as a release or as
final Qualification by this task.

## Verification and remaining gate

- Local31 tests PASS at both Python/pytest boundaries above; no minimum-version
  change needed. Scope/conflict/failed-connect/retirement/drain/pool ownership,
  conftest/module import, CLI/config, collection failure, malformed-input secrecy,
  worker registration and strict receipt matching are covered.
- Public-source/version check PASS; generated source inventory, pinned inputs
  and guest identity PASS. These check unchanged generated ownership; no new
  independent regeneration is claimed.
- Current guest SHA256 remains
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`;
  Go1.26.10/converter/guest patches and accepted Prepared exceptions are unchanged.
- Native replacement17+6 and real pytest4 tests, with exact host/candidate
  identity and required Connector modes, still need results from the candidate
  workflow. macOS Homebrew's known Connector import problem must remain a local
  SKIP if encountered; CI uses its normal Python distribution and requires
  actual default/pure execution.
- No performance benefit, Qualification, Product Validation, main adoption or
  release readiness is claimed. After native results, return to Human Review
  for main adoption; no repeat implementation approval is requested.

Disposable local environments use the experiment-workspace lifecycle with a4GiB
budget and8GiB free-space reserve. Source/results are committed; recreateable
venvs/cache are removed after saving compact receipts. CI remains responsible
for its submitted candidate; Codex hands off rather than supervising it.
