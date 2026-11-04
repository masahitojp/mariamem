# Release regression and manual measurement — 2026-11-04

The Human approved the three high-priority CI reductions after the0.6.1 review:
run language-independent Go consumers once per OS, move E2E first/second/repeat
timing out of normal Release, and separate G1 regression from repeated resource
measurement. This changes CI responsibility, not runtime behavior or release
publication approval. Historical receipts and their original criteria stay intact.

## Retained Release coverage

- Live installed consumer, owned E2E installed consumer and Live documentation
  examples execute Go on Python3.11's invocation only. Python executes on both
  3.11 and3.14 on both OSes. The second invocation uses `--skip-go` and its receipt
  claims Python-only success; it never invents a second Go PASS. The same job
  still fails if the first Go invocation or either Python invocation fails.
- Ordinary E2E orders/independence/retirement and physical controls remain.
  Remove only `e2e_workflow_timing.py` from automatic acceptance; its first,
  second and repeat commands otherwise rerun existing example cases.
- G1 uses `go_fixture_campaign.py --profile release`: cap1/2 × parallel1/4,
  four SQL/DDL isolation cases per mode, one preparation per fixture, two physical
  connections per child, child/connection budgets, FD/disk guards and final owner/
  backing/connection cleanup. The pre-admission FD-stop negative control remains.
- G1 completion, physical fault mutations and external-module acceptance remain.
  Source, toolchain, OS, input and checksum binding still gate both host receipts.
  A measurement receipt cannot masquerade as a Release-profile receipt.

## Manual-only observations

`--profile measurement` (the backward-compatible default) retains the original
G1 first/second example builds, warmup plus three observed batches, retained
baselines and RSS/available-memory observations. Its existing strict validation
is unchanged. Release regression receipts explicitly state that those resource
measurements did not run. No weaker resource PASS or new performance estimate is
issued. The historical v06x acceptance JSON describes that measurement cohort;
this decision owns the new normal Release execution policy.

In an authorized clean workspace with required exact-source inputs available:

```sh
python scripts/go_fixture_campaign.py --expected-source-commit SOURCE_COMMIT --output OUTPUT --profile measurement
```

The existing E2E timing command also remains available manually after preparing
its host/application executables and fixed dependencies:

```sh
PYTHONPATH=python E2E_OWNED_RUNTIME=1 MARIAMEM_TEST_HOST=HOST E2E_GO_APP=APP \
  python scripts/e2e_workflow_timing.py --expected-source-commit SOURCE_COMMIT --output OUTPUT --include-go
```

Use the existing disposable-workspace/disk guard process for these commands.
No new workflow/trigger/job is added. Daily checks, required contexts, exact-SHA
READY reuse, native/guest comparisons, D1/Fork/Live faults and final wheel/module
acceptance retain their existing owners. Other audit candidates are not selected
by this decision. A future resource claim requires a new identity-bound manual
measurement, not inference from the shorter Release regression.
