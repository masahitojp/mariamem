# shadow_maria implementation — candidate acceptance pending

2026-10-24. Branch: `feat/connection-routing`. Approved design/source_commit:
`48a6da087ba9912e8135ac58e72dfecea4bdc015`, resolved with
`scripts/git_identity.py`. The Human authorized implementation and Python3.11+
support, dropping3.9/3.10. The [entry design](v06x-shadow-maria-entry-design.md)
records the seven reviewed gaps and their implementation contract.

## Current result and next gate

The approved marker, preparation fixture and public names are implemented.
Local3.11/pytest7 and3.14/pytest9 checks pass. **Updated native acceptance is
pending**; the next Human decision is main adoption after those results, not
another approval of the same entry direction. No main merge, Qualification or
release is authorized by this implementation.

The strongest remaining condition is that ordinary application fixtures must
start SQL under the test binding. Import/session-scoped application SQL does not
have a per-test target. The early guard refuses it rather than touching the
original DB. The guide documents explicit preparation settings and application
lifetime/fixture dependencies; live/reset remains a separate task.

## Review-gap disposition

| Gap | Implemented response and evidence |
| --- | --- |
| Uncommitted design | Design/contract/status/report fixed at48a6da0 before runtime edits |
| Preparation default/override | `None` no-op; side-effect fixture returningNone or callback accepting source DB; other values reject; callback return unused |
| Marker/fixture identity | Autouse marker dispatcher requests cached function `mariamem_app_db`; same child as `mariamem_fork`; fixture alone also explicitly activates routing |
| Scope and override ordering | Function/class/module markers all retain function child scope; default prepare -> disconnect wait -> Snapshot -> Fork -> binding; custom server feeds chain, custom Snapshot/Fork owns replaced boundary |
| Names and documentation | New controller/adapter/extras and marker names in source, tests, native facade and usage guides; no unreleased compatibility aliases |
| Python policy | `python_requires >=3.11`, current-source guide minimum3.11;3.11/3.14 compatibility matrix; historical release/receipt metadata retained |
| Failed preparation | Setup/callback/wait errors prevent Snapshot/Fork; original error retained; source context manager finalizes. Dedicated subprocess failure cases verify this ordering |

## Verification

- Python3.11/pytest7:58 routing/early-plugin/receipt/public-surface tests PASS.
- Python3.14/pytest9:139 selected routing/source-boundary tests and25 receipt
  subtests PASS. Selection additionally covers diagnostics, development scope,
  CI/publication workflow, license mirrors and toolchain pins.
- New subprocess coverage includes marker-only activation, marker+fixture same
  child/binding, class/module function isolation, standalone DB fixture, default
  and side-effect/callback preparation, invalid callbacks, setup/callback/wait
  failures, custom server/Snapshot/Fork overrides, no-marker inactivity, strict
  argument refusal, original-profile refusal during preparation, and once per
  worker with four isolated tests across two xdist workers.
- Public source/version/diff checks PASS. No guest/converter/generated Go owner
  is changed; no independent regeneration or new performance result is claimed.
- Updated native pytest workflow uses `mariamem_prepare` with explicit DB
  settings, the default Snapshot chain, module `shadow_maria`, and assertions
  that direct access/Fork/controller see the same child. Its existing strict
  four-test/two-worker gate remains. The17-case/six-mutation routing acceptance
  remains intact; only the test facade's production method spelling changes.
  Those native results must come from the newly submitted exact candidate.

Earlier [CI40045368302](https://github.com/masahitojp/mariamem/actions/runs/40045368302)
passed both OSes at0698698, verifying the previous entry/core. It does not prove
the new marker/preparation workflow. Ubuntu explicit Connector C retains its
permitted environment SKIP; required default/pure must execute in updated CI.

## Continuing constraints

Source support is3.11+, while published v0.5.3 retains its historical metadata.
Preparation-time automatic switching is excluded from0.6.0 and retained for
0.6.x reconsideration. Live behavior has its separate design task and0.6.0 scope
decision. Existing Go/public acquisition, Prepared exceptions, early-profile
protection, resource ownership and strict failure oracles remain unchanged.
