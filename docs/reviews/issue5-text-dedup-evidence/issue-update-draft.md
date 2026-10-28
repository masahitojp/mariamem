Root cause established on macOS arm64 at source_commit
`cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`:

The internal Aria temporary-table scan requests `HA_EXTRA_MMAP` →
`maria_extra` → `_ma_dynmap_file` → WASIX libc mapping → `Fd_dup`.
mariamem overrides this import with `panic("unimplemented WASIX: Fd_dup")`,
despite an existing implementation in `base.WasiStubs`.

This is a worker trap followed by a missing reply, not SQL spinning or a blocked
VFS call. Another session answers `SELECT 1` until the timeout terminates the DB.
`ThreadLaunch` retains the panic until `WaitThreads`, so no error is delivered
while the resident root still runs.

Correction: `SQL_BIG_RESULT` uses filesort with zero temporary-table counters
in the bounded probe; it does not demonstrate success through a disk temp table.

All 28 type/shape cases were rerun against native12.3.3. The baseline has19
differences. A diagnostic Go-only delegation to existing `WasiStubs.Fd_dup`
matches all28 outcomes/rows/affected counts. The new wire regression fails3/3
on the baseline and passes3/3 with that diagnostic delegation.

No production/guest change or CI submission is included. Diagnostic live edits
were reverted; patches, binary identities, raw JSON and stacks are archived in
`docs/reviews/issue5-text-dedup-evidence/`, with the report at
`docs/reviews/issue5-text-dedup.md`, branch `experiment/issue5-text-dedup`.
The branch retains a deliberately failing regression and is not merge-ready.

Next: a bounded host-import fix with descriptor/mapping lifetime tests and
macOS+Ubuntu canonical/runtime acceptance. Decide separately whether timely
worker-trap notification belongs in that change. Ubuntu, full acceptance,
resource/lifecycle coverage and dbt replay have not run.

This file is a draft; no comment has been posted to GitHub.
