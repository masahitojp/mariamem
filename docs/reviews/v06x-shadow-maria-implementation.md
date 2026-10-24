# shadow_maria implementation — acceptance passed; main adoption approved

2026-10-24. Branch: `feat/connection-routing`. Approved design/source_commit:
`48a6da087ba9912e8135ac58e72dfecea4bdc015`, resolved with
`scripts/git_identity.py`. The Human authorized implementation and Python3.11+
support, dropping3.9/3.10. The [entry design](v06x-shadow-maria-entry-design.md)
records the seven reviewed gaps and their implementation contract.

## Current result and next gate

The approved marker, preparation fixture and public names are implemented.
[CI40061580952](https://github.com/masahitojp/mariamem/actions/runs/40061580952)
passed at exact source_commit `204f106264def67d32da8ac7733be052c928a26c`.
The Human approved main integration on2026-10-24 and requested the five
recordkeeping/usage clarifications below. Main integration records the tested
candidate separately from these documentation/evidence-only follow-ups.
Qualification and release remain separate, unstarted decisions.

The strongest remaining condition is that ordinary application fixtures must
start SQL under the test binding. Import/session-scoped application SQL does not
have a per-test target. The early guard refuses it rather than touching the
original DB. The guide documents explicit preparation settings and application
lifetime/fixture dependencies; live/reset remains a separate task.

Local verification source_commit: `e61d10f493b76c698a83253b57f5c38c4db482b0`.
[Inputs and source hashes](v06x-shadow-maria-implementation-evidence/inputs.json),
[Python3.11 log](v06x-shadow-maria-implementation-evidence/python311.txt),
[Python3.14 log](v06x-shadow-maria-implementation-evidence/python314.txt), and
[original/stored hashes](v06x-shadow-maria-implementation-evidence/files.json)
retain environment and results. Paths were scrubbed and trailing whitespace
normalized; that explains differences between original and stored hashes.
Versions were Python3.11.17/pytest7.0.0 and Python3.14.9/pytest9.0.2 on macOS arm64.
Subsequent changes before CI submission are documentation/evidence only.

Reproduce with an isolated Python3.11 or3.14 venv and
`tests/routing_acceptance/unit-requirements.txt`. Run
`PYTHONPATH=python <venv>/python -m pytest tests/test_routing.py tests/test_routing_pytest.py tests/test_routing_receipts.py -q`.
The3.14 selection additionally includes diagnostics, development scope,
CI/publication workflow, packaging-license mirror and canonical toolchain suites
listed in the input receipt's exact command arrays. Native acceptance is run by the
existing exact-source `tests/routing_acceptance/run.py` workflow.

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
  Those native results passed on the exact candidate204f106; see saved receipts below.

Earlier [CI40045368302](https://github.com/masahitojp/mariamem/actions/runs/40045368302)
passed both OSes at0698698, verifying the previous entry/core. It does not prove
the new marker/preparation workflow. Ubuntu explicit Connector C retains its
permitted environment SKIP; required default/pure must execute in updated CI.

## Native CI receipts and adoption follow-up

The [run metadata](v06x-shadow-maria-implementation-evidence/ci-40061580952/run.json),
[job results](v06x-shadow-maria-implementation-evidence/ci-40061580952/jobs.json),
[artifact IDs/digests](v06x-shadow-maria-implementation-evidence/ci-40061580952/artifacts.json)
and [independent assessment](v06x-shadow-maria-implementation-evidence/ci-40061580952/assessment.json)
are retained in the repository. Native [macOS inputs](v06x-shadow-maria-implementation-evidence/ci-40061580952/macos/inputs.json)
and [Ubuntu inputs](v06x-shadow-maria-implementation-evidence/ci-40061580952/ubuntu/inputs.json)
bind host, guest, SDK, consumer and test identities. Each platform's `files.json`
records original/stored hashes and runner-path/whitespace transformations.
The input receipt's evidence hashes refer to original bytes; scrubbed copies are
verified using stored hashes. Hosted artifact digests are recorded as reported
by GitHub, not claimed as independently recomputed ZIP digests.

| Gate | Result |
| --- | --- |
| Python3.11/pytest7 and3.14/pytest9 compatibility jobs | PASS |
| Canonical `verify.py check` source job | PASS |
| Native17 control cases per OS | PASS |
| Six exact injected defects per OS | All detected by independent receipt assessment |
| New marker/default preparation chain,4 real tests/2 workers per OS | PASS |
| Original endpoint and campaign host cleanup | Zero control contacts; all campaign hosts reaped |
| Connector default/pure prepared behavior | PASS on both OSes |
| Explicit Connector C | PASS macOS; permitted environment SKIP Ubuntu |

The Human's five adoption follow-ups are addressed: current pending wording is
removed; native receipts are saved; the next release must document Python3.11+
(and dropping3.9/3.10); the callback return is explicitly not a teardown hook;
and the import/session-scoped SQL boundary remains prominent in the guide.
No runtime source, tests, workflow, guest or generated input is changed by this
adoption follow-up. It does not create new Qualification or release evidence.

## Continuing constraints

Source support is3.11+, while published v0.5.3 retains its historical metadata.
Preparation-time automatic switching is excluded from0.6.0 and retained for
0.6.x reconsideration. Live behavior has its separate design task and0.6.0 scope
decision. Existing Go/public acquisition, Prepared exceptions, early-profile
protection, resource ownership and strict failure oracles remain unchanged.
