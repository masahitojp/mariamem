# D1 local xdist implementation checkpoint

The Human approved continuing the worker-local spike into a product candidate.
Implementation and local verification are complete. Main adoption remains
conditional on fresh macOS15/Ubuntu24.04 × Python3.11/3.14 installed-wheel
acceptance in the existing Release Django job. No release is requested here.

## Source and scope

Executable source_commit: `cc38d14cb16abf47983c7c0979edd6cf2f9a2814`.
All four retained campaign inputs record that exact clean checkout. Subsequent
checkpoint/evidence changes are documentation only.

Explicit local `-n N` supports `load` and `loadscope`, pinned to pytest-xdist3.8.0
and execnet2.1.2. Each DB-using worker acquires its own host and migration/seed
baseline. The controller, idle workers and DB-free suites acquire none. Serial
remains the default. Remote/manual gateways, automatic/logical counts,
loop-on-fail, other schedulers and Django `--parallel` are refused.
No SDK owner is transmitted between processes. Existing routing exclusions and
lifecycle guards remain active. DB-enabled ordinary Django SimpleTestCase
subclasses are also rejected unless they use the prepared lifecycle.

Class data setup is per class activation in a worker: scheduling can re-enter a
class and run setup again, including within the same worker. A crashed test
remains failed; a replacement worker creates a fresh baseline. This is not a
claim of class-wide atomic compatibility with ordinary Django TestCase.

## Confirmed local evidence

Local platform: macOS27.2 arm64. Python3.11.18 and3.14.10; Django5.2.8,
pytest9.0.2, pytest-django4.12.0, mysqlclient2.2.7, Connector/C3.4.11.

| Boundary | Python3.11 | Python3.14 |
| --- | --- | --- |
| Parallel campaign expected assessments | 15/15 PASS | 15/15 PASS |
| Existing serial campaign expected assessments | 20/20 PASS | 20/20 PASS |

The parallel matrix covers 2/4 workers, both schedulers, reversed collection,
body/preparation failures, a deliberately broken restoration negative control,
idle/DB-free/collection-only cases, real SIGKILL with restart disabled/enabled,
worker-local cleanup debt and pre-acquisition refusal. All90 distinct observed
host PIDs across these four campaigns exited. Expected failure subprocesses
retain their nonzero exit and original error/failure in JUnit; parent PASS
means the oracle detected the specified outcome, not that raw tests all passed.

Cleanup failure is an owned-layer injection before SDK close, not an actual
engine I/O fault. Hard worker death proves host control-EOF exit. It cannot run
Python TemporaryDirectory finalizers: the parent harness removes its own case
TMPDIR after verifying host exit. Enclosing job scratch cleanup remains distinct
from production host lifetime. No performance or resource improvement is claimed.

The canonical Python check on this clean executable source passed:
`python scripts/verify.py check --scope python`:1832 passed,80 skipped,7 warnings,
plus public-source and diff checks. Its environment lacks optional Django, so
those skips are not framework acceptance. Focused framework/API/policy/workflow
checks passed106 on Python3.11; Python3.14 passed105 before the final class guard,
then all58 affected policy/owner/API checks after it. Final real-SDK campaigns
above include that guard commit on both minors.

## Reproduction and provenance

Use each interpreter with `tests/django_lifecycle/requirements.txt` installed:

```sh
python tests/django_prepared/run.py --host HOST --host-source-commit HOST_COMMIT --output OUTPUT_SERIAL
python tests/django_prepared/xdist/run.py --host HOST --host-source-commit HOST_COMMIT --output OUTPUT_PARALLEL
```

Local runs use the candidate Python source entry and a reused published0.6.0
host, not an installed candidate wheel. Host source_commit is
`b3b3b46a8807482ad3f96725af86e031fe369b01`, Go1.26.10, vcs.modified=false;
host SHA256 `b467baece270d6d3cb0770781695c1960de2c0d9c4bd536d6aac2c14f37c1e2a`.
The source wheel SHA256 is
`0c49fcd9f571851d8d37c6ec0fd089fad45609b281dc4fb0e8479819752e1519`.
No Go/guest source change or rebuild was needed for these local checks.

[Saved evidence](d1-xdist-implementation-evidence/) retains inputs, assessments,
worker events, JUnit and selected failure output for both campaigns/minors,
and canonical output. `checksums.json` records original raw bytes and saved
normalized-byte hashes. Worktree/home prefixes and trailing whitespace are
normalized. Barrier markers and routine successful stdout are omitted.

## Remaining integration condition

The existing Release Django job adds parallel installed-entry acceptance using
its existing shared wheel and host, alongside the serial campaign. No new job,
workflow or build is introduced. Submit one `operation=verify`, `mode=auto` for
the exact pushed candidate; prior serial READY receipts cannot qualify this
changed parallel boundary. Fresh four-cell PASS and normal protected review
are still required before adoption. Release notes staging and usage limitations
are included; version metadata and published0.6.0 remain unchanged.
