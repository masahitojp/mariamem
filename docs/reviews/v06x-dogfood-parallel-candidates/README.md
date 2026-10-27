# Parallel dogfood candidates — CI handoff

Three bounded workstreams are assembled for exact-source CI evaluation before
any main-adoption decision. Django still needs fresh native/guest results; the
local Live proof covers only macOS arm64 with Python3.14 and Go HTTP. Static
guide checks do not establish execution of the manual parallel examples.

The common starting source_commit is
`250bceb80be4cfc9f7c844d888af864fc1d38d25`. Orca Run
`run_a8caf5db2ad9` supervised separate worktrees with exclusive heavy verification.
All three workers reported success for their assigned preparation scope and
their terminals were released. The coordinator selected their commits and added
navigation links; exploratory history was not merged.

| Workstream | Original candidate source_commit | Confirmed evidence | Remaining evidence |
| --- | --- | --- | --- |
| Django standard runner | `f08abc10e65fa75ba33c4b991607b1033e119555` | 24 pure ownership/receipt checks on each Python minor | Fresh Ubuntu native references and macOS/Ubuntu guest comparisons on Python3.11/3.14 |
| Runnable Live examples | `342e63ea4233eeea5f03f05292041e2c56df2e38` | Go HTTP and Python3.14 real-browser first/second cases on local macOS arm64; 53 focused checks | Current assembled source, Ubuntu and Python3.11 CI |
| Serial/parallel guides | `c0d4586a2662fd7f8dadf5aad3c03974a8325519` | Python syntax, Go formatting, links and ownership checks | Manual snippet runtime execution |

The assembled tree passed 77 focused tests with three explicit real-host skips:

```sh
PYTHONDONTWRITEBYTECODE=1 build/release-v051-venv/bin/python -m pytest \
  tests/test_usability_examples.py tests/test_live_ci_workflow.py \
  tests/test_django_recipe_unit.py -q -p no:cacheprovider
```

The coordinator found that moving pytest documentation before manual examples
would silently omit those examples from an existing harness. The Live worker
fixed extraction by section, tested both section orders, and checked both base
and guide candidate inputs. This preserves admission to existing runtime checks;
it is not a claim that those guide snippets ran locally.

Original [Django](django-report.md), [Live](live-report.md) and
[guide](guides-report.md) reports retain their source identities, commands,
FAIL/SKIP limitations and cleanup results. The compact
[Live receipt](live-example-evidence/functional/result.json) and its
[checksums](live-example-evidence/SHA256SUMS.json) still bind the original worker
source, not the assembled candidate. Absolute paths identify now-removed
disposable inputs, not reusable binaries. Fresh CI must build its own exact
source and use new receipts.

No product API, runtime, guest, generated source, package requirements, version
or release ledger changed. Branch protection is unchanged. This combined
candidate is not guide-only, so it cannot settle the separate actual guide-only
skip observation or allowlist policy. Main adoption, Qualification and publication
remain separate Human decisions.
