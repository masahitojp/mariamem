# Snapshot/Fork guide candidate

Recommendation: accept this documentation-only candidate for coordinator synthesis and Human review. It fulfills the approved serial/parallel guide backlog using existing APIs and explicit resource ownership; no main adoption, release, or runtime qualification is claimed. The principal limit is that the snippets were checked statically rather than run with real guest databases.

## Identity and scope

- Exact base source_commit: `250bceb80be4cfc9f7c844d888af864fc1d38d25`.
- Candidate source_commit: `c0d4586a2662fd7f8dadf5aad3c03974a8325519`.
- Branch: `masahitojp/v06-snapshot-parallel-guides`; candidate parent is exactly the required base.
- Both objects inspected with `python3 scripts/git_identity.py inspect <ref>`: object_type commit, object_sha equals source_commit. These are source identities, not CI proof identities or tag objects.
- Only tracked changed paths: `docs/go.md`, `docs/python.md` (278 insertions / 92 deletions, including moving the existing fixture section).
- Initial working status was clean. No pre-existing user changes were removed. No push, PR, CI submission/polling, main integration or release occurred.

## Changes

Python leads reusable test preparation with session baseline/function child fixtures, shows ordinary pytest and pytest-xdist commands, and expands the existing worker-local note. It separately demonstrates sequential children and a two-thread ThreadPoolExecutor batch from one in-process Snapshot. Each task owns a child and SQL connection; future.result propagates the first observed failure and executor teardown joins every submitted task before baseline teardown.

Go provides a complete test example with a sequential loop and a bounded goroutine batch, a separate pool per child, errors.Join for operational and Close errors, and a buffered result channel plus WaitGroup. Preparation pools close before capture, successful capture consumes the source, and all child cleanup completes before baseline Close. Both guides distinguish wall elapsed time from overlapping operation sums, make no numerical performance claims, and keep Live scoped to sequential cases. Original README section anchors remain valid.

## Verification results

PASS:

- `python3 scripts/git_identity.py inspect HEAD` and `inspect 250bceb80be4cfc9f7c844d888af864fc1d38d25`; `git rev-parse HEAD^` equals base.
- `python3 scripts/verify.py check --scope docs` on final candidate: release version boundary PASS, public-source boundary PASS (5428 files), git diff whitespace PASS.
- `python3 build/experiment-work/snapshot-guide-checks/evidence/temp/check_guides.py`: AST parse of all five Python code blocks, gofmt parse/format of both complete Go blocks, existence of 22 local linked paths, original README deep-link headings, actual Go/Python method source signatures, pytest session scopes/function fixture dependency chain, exact two-file diff boundary.
- Pure source-based development_scope.plan plus live_ci.required check on exact base/candidate: check_scope docs, integration false, run_live false. This is a local selector result, not an observed CI SKIP.
- `git diff 250bceb80be4cfc9f7c844d888af864fc1d38d25 --check`; clean final tracked status.

FAIL:

- Initial experiment runner invocation used a repo-relative script path even though its working directory is task temp, so Python exited 2 (script not found). The original console.log/returncode remain in the cleaned experiment evidence; the preserved script was then run directly from repository root and passed, including after final commit. This was a verification invocation failure, not a product/snippet runtime result.
- The known historical Python3.14.9/OpenSSL4.0.3 Oracle Connector/Python26.7.0 import FAIL remains documented and unchanged. It was not rerun or relabelled PASS here.

SKIP:

- No observed runtime/CI SKIP was produced in this task. Runtime campaigns were deliberately not run under the docs-only scope; the local selector predicts the existing guide-only Live skip path.
- Historical FAIL/SKIP receipts were not edited.

NOT RUN:

- No actual guest build/test, Go test, pytest/xdist database execution, native/Docker/browser campaign, dependency installation/download, or benchmark. No heavy-verification lease was requested or needed.
- No new exact-source CI receipt exists for this candidate.

## Environment and detector limits

Observed host: macOS27.2 arm64 (macOS arm64 is a supported host family). Static checks used CommandLineTools Python3.9.6/LibreSSL2.8.3, not a claimed supported current SDK integration profile; Python syntax parsing does not import the SDK. Current source SDK minimum remains Python3.11. The known Python3.14/OpenSSL4 connector constraint is not covered by this static result or by OpenSSL3 CI; no ssl aliases, driver patches or profile changes were made.

Existing `tests/test_usability_examples.py` splits Python at `## pytest fixtures`. Moving primary fixture usage earlier means that harness now runs the initial disposable-DB example only; it does not cover the manual sequential/parallel blocks following the fixtures. The new Go block contains a TestSnapshotCases entry point and can execute when the existing real-host harness runs. Neither was run here. Existing guide-only CI selectors validate boundaries but do not establish real concurrency behavior. No test file was changed because this candidate is explicitly restricted to two guides.

## Remaining CI inputs and conditions

Coordinator may submit the exact candidate or a separately identified synthesis commit through the normal existing CI gate. A guide-only event must retain only allowed guide paths and a valid known base/candidate diff; the expected scope is docs, integration false and Live runtime skipped, with the always-reported gate still required. Observing that actual skip is an open main post-adoption condition; local selector output is not its substitute. No release approval is involved.

No additional runtime evidence is required for this requested static guide task. If the Human wants executed snippet acceptance, that is separate work: authorize an exclusive lease and an exact-source supported host/SDK profile, with a source-bound built host, PyMySQL, pytest/xdist, MySQL Go driver and bounded runtime budget. The Python harness ordering blind spot must be addressed separately before claiming those new blocks are CI executed. Keep any resulting source/proof identities distinct from this static candidate.

## Retention and cleanup

Prepared task-owned `build/experiment-work/snapshot-guide-checks` with min-free 4 GiB / budget 0.05 GiB. Failed invocation peak usage 12288 bytes and minimum observed free space 83057971200 bytes; no caches/downloads were created. Finalized supervised work, inspected cleanup dry-run, applied scoped cleanup, and confirmed state cleaned with no cleanup debt or retained paths above 1 GiB. Task temp is gone; remaining experiment files are compact validator/console/checksum/receipt evidence (about 20 KiB). `build/public-source-check.json` is the small boundary receipt (about 752 KiB); this report is the durable handoff. The Orca worktree and unpushed commit remain intentionally retained for coordinator review, as requested.
