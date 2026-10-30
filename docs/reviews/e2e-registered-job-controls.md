# Registered-job hook controls — independent verification branch

This branch follows successful physical-session CI for PR #28. It adds only
controlled app-hook tests and evidence; PR #28 is left unchanged while another
worker integrates main/CI improvements. Adopted main `b4f318c9` (PR #29) is merged
here; it is also a parent of the already successful CI merge source5147f8ed.

The Go production/SDK inputs are byte-identical to that successful CI source.
At code commit `0f843cb55f3b150eb33e0f2f9d3077836685e5a1`, the only tracked diff
from `5147f8ed5d35c2b62ffed9114e606c0a3146e4b7` is
`mariamemtest/http_jobs_runtime_test.go`. Reports being collected are not runtime
inputs. This local verification is not a new exact-candidate hosted qualification.

## Finite controls

The controlled app owns one explicitly registered job holding a real transaction
and SQL session. Its pause hook rejects new work, waits for that job's actual
completion, retires physical connections and holds the barrier until Resume.
The entry must wait for the hook before Reset. An observed Live wrapper verifies
pause/join state at the Reset call; actual Live still performs Reset/drain.

- Positive: while the job is held, setup cannot complete and generation stays0.
  Release commits the old job, then event order is pause → job_done → join →
  Reset → Resume. The body sees the original seed, without the old job's row.
- Negative: the deliberately broken hook returns nil before joining. The real
  physical drain returns ErrBusy; generation stays0, Resume is absent, and later
  admission is rejected. Registered ownership remains available to StopReap,
  which requests rollback, joins and closes the pool before DB owners close.

These are real DB/transaction/Live controls with a small controlled app, not an
arbitrary scheduler, HTTP application, production job registry or proof that an
unregistered future job can always be detected. The application's own hook must
supply that boundary. The test wrapper's phase observation is an oracle, not an
SDK promise of automatically observing logical job completion.

## Existing both-host proof

[CI40871306020](https://github.com/masahitojp/mariamem/actions/runs/40871306020)
passed both hosts' physical pool/public-admission controls and installed consumers.
Its actual source is `5147f8ed5d35c2b62ffed9114e606c0a3146e4b7`, with parents
main `b4f318c9f29b72c13bf3a529ea973a4e31b41d0c` and PR head
`b6670a1bf53c94a8a3cf25aaa4fee9de56749103`. Do not substitute the PR metadata's
older base62d54c for the actual merge parent. [Selected raw physical logs and
assessment](e2e-physical-ci-40871306020/assessment.json) retain full-artifact ZIP
SHA256 matches against GitHub for macOS15 arm64 / Ubuntu24.04 x86_64.

## Integration boundary

Names use the existing `TestHTTPPhysical` runtime selector, so no additional
workflow changes are introduced here. The normal helper package check skips these
actual runtime controls unless E2E_OWNED_RUNTIME=1. Normal execution of both new
controls passed locally on observed macOS27.2 arm64 / Go1.26.10. Race verification
and its raw logs are recorded below once complete.

Both supported-host results for these new job controls remain required when the
independent branch is integrated. This does not complete #18: remaining compound
cleanup/partial-owner coverage needs evidence mapping, and first/second/repeat
workflow/resource/retained-baseline campaigns remain unfinished. Main adoption
and release remain later decisions. No CI dispatch or PR #28 update is performed
by this independent verification branch.

## Local result at code source0f843cb5

Both normal and race-instrumented execution PASS for the two new controls on
observed macOS27.2 arm64 / Go1.26.10; no data race was reported. The negative
control retains the original ErrBusy condition and verifies no Resume/later
admission. [Raw logs and assessment](e2e-registered-job-evidence/assessment.json)
are checksum-bound. Tracked code matched0f843cb5; only pending report files were
untracked during these development runs, so this is not a clean-candidate or
supported-host qualification claim. New hosted acceptance remains pending.
