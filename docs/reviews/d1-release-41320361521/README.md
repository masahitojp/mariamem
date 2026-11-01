# D1 installed-wheel results and core failure — Release41320361521

Executed source_commit: `ad9c7e67884d257a52283ce646aabcbd8af69b8b`.
[Run](https://github.com/masahitojp/mariamem/actions/runs/41320361521).
This is not Release READY: both core jobs failed. No publication was requested.

The existing Release Django job succeeded on macOS15 arm64 and Ubuntu24.04
x86_64. Each Python3.11/3.14 cell recorded `installed=true`, a clean adapter
checkout and the same exact host/adapter source commit; all20 scenario
assessments passed. The four installed-wheel cells satisfy condition(a) for
that executed candidate. Conditions(b)(c) were already staged at that source.
Later test/report-only changes are not a new executed Release SHA.

| Hosted cell | Python | Installed | Scenarios |
| --- | --- | --- | --- |
| Ubuntu24.04 x86_64 | 3.11.17 | true | 20 PASS |
| Ubuntu24.04 x86_64 | 3.14.9 | true | 20 PASS |
| macOS15 arm64 | 3.11.9 | true | 20 PASS |
| macOS15 arm64 | 3.14.10 | true | 20 PASS |

`receipt.json` binds downloaded ZIPs to the GitHub artifact SHA256 values and
records raw/saved JSON hashes. Eight compact JSON files preserve the cell input
and aggregate assessments. Home prefixes are normalized in saved inputs.
Per-case raw stdout and the original standard/native campaign outputs remain
in those GitHub artifacts; they are not duplicated here. Their artifact retention
is finite. This receipt does not claim that all original logs are retained here.

## Why both core jobs failed

[core_ubuntu](https://github.com/masahitojp/mariamem/actions/runs/41320361521/job/124889576701)
and [core_darwin](https://github.com/masahitojp/mariamem/actions/runs/41320361521/job/124889576705)
failed the same four tests in `tests/test_django_recipe_workflow.py`.
The added prepared entry renamed its workflow step; the existing test still
searched for the old literal name. `re.search(...)[1]` therefore raised
`TypeError: 'NoneType' object is not subscriptable`. Both logged1731 PASS,
70 explicit SKIP and4 FAIL. These were workflow-policy test failures, not
failures of the installed Django entry. Prior focused verification missed this
existing workflow test module.

The repair updates that test to select the current step and gives a clear
assertion if it disappears. The actual workflow shell now runs four commands per
interpreter, so the executable test covers the standard campaign, focused unit
checks, shared-wheel installation and installed prepared campaign. It separately
injects failure into each of the three status-aggregated checks on each Python
minor; either failure must preserve the second interpreter and fail the job.
No workflow, product, guest, generated code or version is changed by this repair.

Focused workflow/recipe/owner/API/reuse/CI tests passed on both local interpreters:
73 PASS,10 explicit SKIP because the unit-only environments lack Django. Those
framework tests already ran in the successful hosted Django jobs; these local
SKIPs are not relabelled as new framework evidence. Public-source and diff checks
also pass. Heavy Release verification was not duplicated while the original
run continued. The original core FAIL remains; no repaired-source READY or
protected merge is claimed.
