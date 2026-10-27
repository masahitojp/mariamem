# Live review correction evidence

The local-assessment pins the tested worktree parent and exact tested file hashes.
The product Python Session is byte-identical to tested candidate6edcd29. Final
focused runs pass99 cases on each Python version, with unhandled thread warnings
treated as errors. Initial harness warnings are preserved separately: the final
fault seam interrupts only the calling thread, not background disposal workers.

focused-logs.zip.base64 losslessly retains original outputs and mutation results.
Verify SHA256SUMS.json, decode the ZIP, check local-assessment.archive_sha256,
then each uncompressed member against log-members.json. Missing interrupt cleanup
and duplicate late close each produce6 intended failures on each interpreter.
They are rejection evidence, not successful raw test runs. Reproduce against a
copy of python/mariamem: remove request's wait interruption handler for the first
mutation; duplicate db_close and snapshot_close requests in Session._late for the
second. Run test_interrupt_existing_requests_reclaims_once_and_preserves_sibling
for start/fork/snapshot in both before_reply and reply_ready phases.

protection-applied.json and protection-readback.json preserve authenticated API
responses. The previously unprotected main now requires GitHub Actions app15368's
check/integration with strict base freshness and admin enforcement. No existing
review requirement was removed (there was no prior protection/ruleset).
protection-with-live.json is the concrete later payload, not an applied setting.
Add Live required gate at Human-approved main adoption after fresh CI proves the
new always-reported gate. Re-read settings before applying it to preserve any
intervening policy changes. Ordinary CI does not audit repository policy drift.

The Live workflow now always reports on main pushes/PRs. Only the six explicitly
listed guide paths may skip expensive jobs; any other/unknown/empty diff or
missing base runs the full existing matrix. The final job rejects failure,
cancellation, unexpected skips and undefined scope. Unit state coverage is not
an observed GitHub guide-only skip receipt. Fresh candidate CI remains required.
