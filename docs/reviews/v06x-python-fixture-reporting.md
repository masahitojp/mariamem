# P1 pytest reporting characterization

Historical pre-code investigation at 1780db3. The subsequent conditional Human
approval is recorded in [the pre-code decision](../decisions/p1-prepared-entry-implementation.md);
original approval context and probe results below are retained.

Recommendation: implement P1 with the existing pytest reports, narrow preparation
annotations and a worker-local owned-state record. The command entry should be
`PrepareCommand(argv, *, timeout=120, cwd=None, env=None)` as fixed in the
[proposal](v06x-python-fixture-entry-design.md). The decision remains P1's
implementation boundary; the structured contract still authorizes G1 only.

The main concern is cleanup debt: current pytest failure reporting preserves
errors but does not itself stop the next test after a child-finalizer failure.
Add that admission guard inside the entry rather than treating diagnostic notes
as enforcement. Ordinary assertion failure with successful cleanup must continue
to allow the next independent prepared child.

## Measured object and method

Source commit: `1780db3b7ed7a23b538175183a78e979999d0949`, verified with
scripts/git_identity.py and a clean HEAD before each run. The measured tool is
[scripts/probe_p1_pytest_reporting.py](../../scripts/probe_p1_pytest_reporting.py).
It derives controlled fake owners from tests/test_routing_pytest.py and invokes
real pytest in disposable temporary projects with plugin autoload disabled.
No proposed command runner, production SDK/guest patch or actual SQL is executed.
The fake owners' events are control-flow observations, not physical disposal.

Observed host: macOS 27.2 arm64. Profiles: Python 3.11.17 / pytest 7.4.4 and
Python 3.14.9 / pytest 9.1.1. This is not the required macOS15/Ubuntu P1 matrix.
Installed pytest/pluggy/package versions, input hashes, seven raw outputs and
phase/exception reports per profile are in the
[checksum-bound assessment and ZIPs](v06x-python-fixture-reporting-evidence/local-1780db3/assessment.json).
The earlier six-case run at 801b9d7 informed the added annotation control; it is
not relabelled as this seven-case source.

Reproduce after checking out the exact source, using a Python environment with
the recorded pytest profile (controller only needs the standard library):

```sh
python3 scripts/probe_p1_pytest_reporting.py \
  --python /absolute/path/to/profile/bin/python \
  --expected-source-commit 1780db3b7ed7a23b538175183a78e979999d0949 \
  --output build/p1-report-replay
```

| Case | Both observed profiles | Meaning for P1 |
| --- | --- | --- |
| Healthy preparation / ignored callback result | Prepare once; two independent child bodies; owners finalize | Keep the existing callback/return contract |
| Ordinary test failure | Original AssertionError; second child still sees seed | Do not stop admission merely because an assertion fails |
| Test failure plus child cleanup failure | Both original exceptions visible; second body still runs | Current control flow does not satisfy P1's stop-on-cleanup-debt contract |
| Callback failure plus source cleanup failure | Both errors visible in setup/teardown; no child/body | Preserve native reports, add owned-stage/state detail |
| Preparation fixture failure plus source cleanup failure | Both errors visible; no child/body | Do not replace pytest's fixture-resolution exception |
| Capture failure plus source cleanup failure | Both errors visible; no child/body | Preserve separate causes; no inferred capture cleanup success |
| Annotated preparation fixture failure plus source cleanup failure | Original exception types retained; stage/admission/pending note rendered in short traceback | A narrow hook + add_note works in these pytest 7/9 profiles |

The note hook does not annotate callback, capture, ordinary-test or child-cleanup
errors in the other controls: its target is only the failing preparation fixture.
It never calls force_result/force_exception or re-executes the fixture. The
reports retain ValueError and RuntimeError rather than replacing them with an
invented root cause. This demonstrates annotation feasibility, not complete
readable-owned output or cleanup/admission enforcement.

## What remains and how it will be detected

P1 runtime implementation is not performed here. Before its first helper commit,
record the Human decision and update the implementation allowlist. The proposal
now fixes command argument/environment/cwd/timeout semantics and diagnostic
strategy rather than leaving the fixture-report question open.

Implementation must still prove real command exit/stdout/stderr, timeout and
interrupt process-group cleanup; honest final owner state; no new child after
cleanup debt; source capture/consumption; routing/pool cleanup; installed wheel;
and the fixed both-host/minor resource/time campaign. Native pytest does not
detect falsely completed cleanup or prevent another child by itself. Add the
explicit negative controls in the proposal; do not relabel this characterization
as P1 support or acceptance.

Existing fixture/marker/routing compatibility suite: 35 PASS on Python 3.14.9
with PYTHONPATH=python. An initial invocation without that path failed one import
before code execution; the corrected invocation passed, with no code relaxation.
No engine/runtime build, broad integration or release gate was run for this tool.
