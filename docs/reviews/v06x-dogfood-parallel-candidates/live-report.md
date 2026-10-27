# Runnable public Live examples candidate

Recommendation: select this bounded candidate for coordinator synthesis and exact-source Live CI. The exact macOS arm64 Python3.14 browser and Go HTTP examples now PASS; the material remaining objection is that Ubuntu and Python3.11 have not run on this candidate. The maintained CI step covers those inputs without replacing native, actual-defect, Fork or installed controls. Main adoption and release remain separate decisions.

## Identity and ownership

- base source_commit: `250bceb80be4cfc9f7c844d888af864fc1d38d25`
- candidate source_commit: `342e63ea4233eeea5f03f05292041e2c56df2e38`
- initial examples commit: `93c2f71636d7fc45b51b572981f6728d94c1e890`; follow-up extractor commit is the final candidate above
- donor source_commit: `a759cf8f90b4a75cf3456d221ef811e8bda20b34`
- branch: `masahitojp/v06-live-usage-main`
- Base, donor and both candidate commits inspected with `python3 scripts/git_identity.py inspect`; each object_type is commit. No tag object substituted.
- Reused donor example source only, adapted to current API/application corpus. No historical receipts copied or relabelled. Existing lifecycle guide tests retained, with focused checks appended.

## Changed paths and SHA256

- `.github/workflows/live-host.yml`: `2ad184085ce20c8ba227515764c9b0465d1061961f9a773d6e0b14b00323ff5e`
- `docs/examples/live/README.md`: `9637b181f8f5880628c326fd80b29403198dd7e6d3cb1d1d7cef3edd3b2c1b39`
- `docs/examples/live/go/live_test.go`: `c4e08312562ad4bdf7d5ab8c56adbe8a5f6c1965aeaf8d347572428ff60ee040`
- `docs/examples/live/python/test_orders.py`: `fb90398876206cf4c8ea70805d0ede0bac3d44eefa38a8f9f33c6f5b5dc60219`
- `docs/examples/live/verify.py`: `6c2551c539120d9196dbdc076f4e0ea7a540cfdbbd17109ba477bc075ca1262d`
- `tests/test_usability_examples.py`: `728d315468104b480568989045a28e54fb86d63b40063c0bbaafcf28e5f4c5e3`

## Confirmed current-run results

PASS: `PYTHONDONTWRITEBYTECODE=1 build/experiment-work/live-examples-check/temp/venv/bin/python -m pytest -p no:cacheprovider tests/test_usability_examples.py tests/test_live_ci_workflow.py -q`: **53 passed, 3 skipped**, 0.09s, Python3.14.9, pytest8.4.2. New checks parse Python structure, exercise result acceptance against PASS/FAIL/SKIP controls, inspect cleanup/admission ordering and preserve existing workflow owners. The three SKIPs are existing README/Python/Go lifecycle tests requiring MARIAMEM_TEST_HOST; these are not new functional passes.

PASS: `python3 scripts/check_public.py`: 5432 public files; `gofmt -l docs/examples/live/go/live_test.go`: no output; Python AST parsing for both new Python files; `git diff --check`: clean. Runtime SDK, internal, guest/generated, dependencies, version, release ledger and historical receipt files unchanged.

PASS: leased exact-source standalone build and `docs/examples/live/verify.py` at final candidate342e63e: **PASS_PUBLIC_EXAMPLES**, Go first/second HTTP cases PASS and Python3.14 first/second real-browser cases PASS, no skips. Go1.26.10 host/application embedded vcs.revision equals342e63e with vcs.modified=false. Python3.14.9, macOS27.2 arm64, Playwright1.56.0 / Chromium headless141.0.7390.37, mysqlclient2.2.7. Exact inputs, commands, buildinfo and raw results: `build/live-example-evidence/functional/result.json`, `go.txt`, `python.txt`, `pytest.xml`; binary checksums in `binary-sha256.json`; campaign transcript/script and all compact-file checksums retained. This is a bounded current-source macOS run, not CI/Qualification or cross-platform acceptance.

PASS: cross-guide extraction/AST checks against base250bceb (2 manual Python blocks) and guidec0d4586a2662fd7f8dadf5aad3c03974a8325519 (3 manual Python blocks), with pytest fixture definitions excluded. New pure regression checks both fixture-before/manual and manual-before/fixture order. The manual guide snippets themselves were not executed. One initial diagnostic assertion incorrectly looked for source.snapshot rather than setup_db.snapshot; corrected diagnostic passed without changing product/example code.

FAIL (verification invocation only): default system Python and Homebrew Python3.14 initially lacked pytest (`No module named pytest`). Resolved with a small task-owned venv, without product/dependency changes. The later exact-candidate runtime campaign passed; no candidate runtime FAIL observed in that bounded campaign.

Historical FAIL preserved: Python3.14/OpenSSL4 Oracle Connector/Python26.7.0 import AttributeError (`ssl.PROTOCOL_TLSv1`) remains documented in docs/development.md. Current interpreter readback is Python3.14.9 / OpenSSL4.0.3 / macOS27.2 arm64. Connector import not rerun in this task; no constant alias, driver patch or native-profile change made. OpenSSL3 CI cannot qualify this local gap.

## Runnable verification and remaining CI inputs

`docs/examples/live/README.md` has exact setup commands. The source-bound functional owner is:

```sh
python docs/examples/live/verify.py --host build/mariamem-host --go-app build/go-live-orders --expected-source-commit "$GITHUB_SHA" --output build/live-evidence/examples-py3.14
```

Use an exact clean candidate checkout; Go1.26.10; build host and tests/live_acceptance/goapp with `go build -p 1 -trimpath`; pinned `tests/e2e_native_control/requirements.lock.txt`; installed Playwright Chromium shell; native mysqlclient dependencies. Execute on both existing Live host OSes with Python3.11 and3.14. Runner verifies actual embedded Go identity (including clean source), hashes example/application inputs, requires both sequential Go HTTP cases and both Python browser cases without SKIP, and retains logs/JUnit/startup logs. Linked-worktree parent-SHA stamping is rejected, never relabelled. Remaining **not-run** inputs: Ubuntu actual examples; Python3.11 actual browser example; native acquisition, installed-consumer campaign, all historical/current failure-control campaigns and CI submission. The selected macOS/Python3.14/Go example campaign did run as detailed above; all original acceptance owners remain present.

Examples migrate/schema-seed once; retain one application PID and DB endpoint; reset before sequential tests; check SEED and absence of prior committed NEW mutation; close browser context per test; stop application before Live before Snapshot. Reset/setup failures stop test admission. Go is HTTP E2E, explicitly not claimed as browser coverage. Quiescence, physical-session retirement, delayed-job limitations and parent lifetime are documented.

Proposed navigation wording for the coordinator (not edited in other owners' guides): “For complete runnable examples, see [reuse one application across sequential tests](examples/live/README.md): Python uses Django and a real browser with a fresh context per case; Go uses HTTP E2E. Both restore the prepared seed through public Live and require quiescence and physical SQL session retirement before Reset.”

## Resource and retention

Experiment-workspace prepared `live-examples-check` with min-free16GiB/budget8GiB. Coordinator granted the exclusive min-free16GiB/budget8GiB/timeout1200s lease, including repinning the corrected final candidate. No heavy work ran before lease. Campaign returncode0, peak owned3796381696 bytes and minimum free78381608960 bytes. Heavy lease-released status sent before worker_done. No Docker or independent native campaign. Compact evidence is22,486 bytes before final report/checksum updates. Worktree/branch source remains for coordinator review; no push, PR, CI, main adoption or release action.

Cleanup PASS: `experiment_workspace.py cleanup --name live-examples-check --apply --json` reduced owned bytes3,094,634,496 →53,248; no retained paths over1GiB and cleanup_debt empty. Browser opaque-data inspection was resolved with an explicit reproduction recipe after preserving compact inputs/results. A concurrent dry-run lock initially prevented redundant finalize; the campaign was already completed and cleanup later succeeded. Original Orca source worktree remains; no task caches or duplicate source checkouts remain. Final tracked/untracked Git status is clean, and diff check passes. Initial checkout had no user changes.
