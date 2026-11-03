# Django6 support — minimal verification (2026-11-03)

Human-approved scope: support Django5.2 LTS/6.0/6.1; keep new verification minimal.
Implementation source_commit: `98f063887fdb3f46597eaf422d29814de0493feb`.
Base: `ce423ff517cb1b97eae3d9b9a38e1c332a62447b` (adopted local xdist PR73).
The adapter, SDK, Go/guest and lifecycle test workload are unchanged.

- Extras widen to `Django>=5.2.8,<6.2`. Generated egg-info for both extras admits
  5.2.8/5.2.18/6.0.9/6.1.2 and excludes6.2; no runtime rebuild required.
- Existing recipe/workflow tests:36 PASS, including actual shell failure
  aggregation and framework input guards rejecting the wrong per-Python pin.
- Additional real check: macOS27.2 arm64, Python3.14.10 + Django6.0.9;
  existing healthy manage.py, healthy pytest and2-worker loadscope assessments
  all PASS. Source-entry check with identity-verified reused host from
  `d99f07cd16a8a11c1644225206a3d1fcc0a39edd`, not a rebuilt candidate wheel.
- Existing [Django6.1.2 probe](https://github.com/masahitojp/mariamem/blob/38c9775435718a3d7b353acf88e2939e818cc324/docs/reviews/d1-django61-probe.md):
  Python3.14,20 serial +15 parallel expected assessments PASS without adapter
  changes. It was not rerun. Expected failure assessments retain raw failures.

Django6.0 healthy assessment hashes:
- `parallel-2-loadscope/assessment.json`: `c2a147bd6e2e3cda30050d547a562f47fc76ebedb7eadbf5dbbc772e3e0aee90`
- `manage-healthy/assessment.json`: `810edb137e207e20eed30eec15aa81a27521269fd2bc32fb3f79e02c3d314c36`
- `pytest-healthy/assessment.json`: `8ff2292961eca65cb6a363e1993fbb8e1b2830b0442db5069f2b7d2827761a2f`

The existing Release job selects3.11/5.2.18 and3.14/6.1.2 through requirement
markers and the input manifest. Native and guest inputs must still match exactly;
job count, shared wheel/host, failure oracles and time budgets are unchanged.
This replaces5.2.8 on both Python minors; it does not multiply the matrix.

No full Release run or additional broad runtime campaign was submitted. The next
existing Release invocation will provide opposite-platform6.x acceptance;
this change does not claim that fresh evidence already exists. Python3.12/3.13,
every patch combination and arbitrary applications were not individually tested.
The Human accepted this bounded verification scope. Version/publication are
unchanged; published0.6.0 extras are not retrospectively widened.
