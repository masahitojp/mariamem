# Connection routing — production implementation candidate

2026-10-24. Base source_commit: `9f29194bbddd6a9431a4a250bd2f93ee813734af`,
confirmed by `scripts/git_identity.py` after fetching main. Branch:
`feat/connection-routing`. The Human conditionally approved implementation;
the four added conditions passed both-OS spike CI40035962925. The continuing
[contract](../decisions/connection-routing-contract.md) records authority and
the unchanged main-adoption/release boundary.

## Current Human Review state

The Human accepted the [marker/preparation surface and naming direction](v06x-shadow-maria-entry-design.md)
after inspecting the fixture-based candidate. The new surface is implemented in
the [marker/preparation candidate](v06x-shadow-maria-implementation.md). Native
acceptance passed inCI40061580952 at204f106 and the Human approved main
integration. Qualification/release remain separate decisions.
Preparation uses explicit DB settings in0.6.0; automatic preparation routing is
reserved for0.6.x reconsideration. Live is a separate task and scope decision.

[CI40045368302](https://github.com/masahitojp/mariamem/actions/runs/40045368302)
passed for source_commit `0698698eb77bbb4df91aea0d83f62e901b711d77` on both OSes:
17 control cases, all six strict injected defects, and4 real pytest tests with
two workers. Default/pure Connector executed on both; explicit C executed on
macOS and retains the permitted Ubuntu SKIP. This establishes the old fixture
candidate, not the new marker/preparation entry. The new report records local entry tests onPython3.11/3.14 and the completed
updated native acceptance; this older run is not relabelled.

The sections below preserve the pre-CI implementation/local-evidence checkpoint;
their pending-CI statements and old API names are historical, superseded by this
status and the accepted entry design. Existing receipts are not relabelled.

## Pre-CI checkpoint — original result

The candidate implements optional public Python routing, an explicitly owned
SQLAlchemy adapter and early pytest integration. Local lifecycle/early-plugin/
receipt tests pass on Python3.14.8/pytest9.0.2 and Python3.9.6/pytest7.0.0:
32 routing tests each. The3.14 selected source-check run totals113 tests
and25 receipt subtests. These tests
exercise real pinned driver/framework hooks with fake connections where no guest
is needed; they do not establish native SQL acceptance. **Both-OS production-native acceptance remains pending.** The earlier spike PASS is not substituted for it.

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

- Local32 routing tests PASS at both Python/pytest boundaries above; no minimum-version
  change needed. Scope/conflict/failed-connect/retirement/drain/pool ownership,
  conftest/module import, CLI/config, collection failure, malformed-input secrecy,
  worker registration and strict receipt matching are covered.
- Public-source/version check PASS; generated source inventory, pinned inputs
  and guest identity PASS. These check unchanged generated ownership; no new
  independent regeneration is claimed.
- Current guest SHA256 remains
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`;
  Go1.26.10/converter/guest patches and accepted Prepared exceptions are unchanged.
- Local macOS native at source_commit
  `a3bac987afaa9fa3eed12ce1cf3bf11b8fe4f919`:16 control PASS,
  Connector import1 SKIP; six injected faults detected at their exact oracles;
  real pytest4/2 workers PASS; no control original-endpoint contact and all
  campaign hosts reaped. The local receipt deliberately records `complete=false`;
  this is partial evidence, not full acceptance. The only subsequent changes
  before CI handoff are documentation/evidence.
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

## Evidence and reproduction

[Local Python3.14 source checks](v06x-connection-routing-productization-evidence/local-python314.json),
[minimum-version checks](v06x-connection-routing-productization-evidence/local-python39.json),
[native inputs/results](v06x-connection-routing-productization-evidence/macos-local/inputs.json),
[control cases](v06x-connection-routing-productization-evidence/macos-local/control.json)
and [original/stored hashes](v06x-connection-routing-productization-evidence/macos-local/files.json)
retain the result. Path scrubbing and trailing-whitespace normalization account
for original/stored hash differences; the input receipt refers to original bytes.

Recreate a bounded workspace and a Python3.14 venv with
`tests/routing_acceptance/requirements.txt` and `unit-requirements.txt`. From a
clean candidate checkout run `tests/routing_acceptance/run.py --runtime-root <repo>
--source-commit <full-commit-SHA> --output <workspace>`. The runner validates
commit identity, builds/identifies the host, executes the control, six mutations
and real pytest workflow, and saves hashes. Only the local Homebrew diagnostic
uses `--allow-connector-import-skip`; CI never uses it.

## Verification-version policy update — 2026-10-24

The Human directed that Python3.9/3.10 need no further verification because
both are EOL ([lifecycle reference](https://endoflife.date/python)). Future
routing compatibility jobs use Python3.11/pytest7 and Python3.14/pytest9.
The3.9 results above remain dated evidence; no3.11 PASS is claimed yet.
Published package minimum metadata is unchanged by this CI-only policy update.
Run40045368302 was submitted before this change and retains its original matrix.
The workflow change will take effect on the next submission; no duplicate native
campaign is started solely for this version-policy change.
