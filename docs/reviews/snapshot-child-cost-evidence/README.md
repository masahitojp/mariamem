# Child-cost evidence and replay

Measured source_commit: `30046c949717a0eb95086cfbf0ceeb081f85e5c6`.
Runtime/prototype source_commit: `3341f99000246fc64ae17b4ea39118f55589de1e`.
Reports later added on `experiment/snapshot-child-cost` are not measured source.
The primary report is [snapshot-child-cost-followup.md](../snapshot-child-cost-followup.md).

## Replay boundary

Use the repository experiment-workspace helper to create a new task workspace
with 6 GiB disk budget and 8 GiB free reserve. The helper/guard used here comes
from main `a8137b8b444f86068d3128a291e3a848adfdfd56`. Put a clean **standalone Git
clone** at `temp/source`, checked out at the measured source_commit above.
A worktree build is not a substitute for checking actual embedded VCS identity.
Put the archived scripts at `temp/`, and create the workspace's `evidence/`.

`scripts/guard.py` builds with Go1.26.8, GOMAXPROCS2, task-local build/tmp cache,
then checks the binary using `git_identity.require_commit/verify_go_binary`.
`scripts/build_tools.py` builds cmd/pprof and cmd/trace from that fixed Go source;
the installed toolchain contained compiler/linker but no prebuilt profiling tools.
Wait until both builds have completed before benchmark execution.

`scripts/campaign.py` is the exact original finite runner: two pilots, four off,
four counters, two CPU profiles and two traces. It refuses output overwrite and
stops on the first failed SQL/process result. It contains the original absolute
four-hour UTC deadline; for an independently authorized replay, replace that
single deadline with the new authorized end time and record the changed runner
SHA. Do not silently remove the budget. Go1.26.8, GOMAXPROCS2, normal GC defaults,
one table, 100 MiB and 16 serial CRUD children are fixed. Localhost permission is
required; do not count a sandbox bind failure as a performance sample.

After all scenarios stop, run `scripts/analyze.py`, `scripts/profiles.py` and
`scripts/trace_ranges.py`. CPU/profile reduction should not compete with measured
work. `legacy-reduction.json` comes from the eight previously stored samples at
`b6d371232f613425b066049bb3e6f873cfee4e37`, not new runs.

`analysis.json` preserves per-operation phase sums, exact counter differences and
per-child heap/goal/GC histories. `cost-summary.json` is a selected projection of
its child deltas: cpu-class seconds ×1000, byte counters /1048576; nonidle GC is
GC total minus idle mark CPU. These estimates are not OS CPU and cannot establish
an exact wall-time bound. `verification.json` checks process return codes and
expected completed mutation assertions, plus no extra forced GC in observed runs.

## Archive

`archive-index.json` records original and saved lengths/SHA256. JSON is compacted
without losing keys/numbers; repository/workspace paths become `<REPOSITORY>` and
`<WORKSPACE>`. Empty successful stdout/stderr logs are omitted with their hash and
reason. `.log` names become `.txt`. No unfavorable sample is excluded.

The two traces are retained as lossless gzip (mtime=0); decompress before feeding
to the trace tool. Their decompressed SHA must match the original index entry.
CPU and derived delay profiles are kept as their original binary bytes. The
native paths embedded in profiles are diagnostic source locations, not claims
that the disposable checkout still exists. Complete traces are retained because
they support independently checking the timing/range reductions and attribution
limits; ordinary binaries/build caches are not required for that unique evidence.

`trace-ranges.json` streams the fixed Go trace parser's `-d=parsed` output. Range
pairs are keyed by name and resource scope; boundary/unclosed ranges are exposed.
Main goroutine state intervals come from GoID=1 transitions. Their network wait
is SQL response wait. Other worker wait durations overlap; do not sum them into
product latency. GC mark phase and mark assist durations also overlap.

`profiles.py` preserves commands/return codes for all CPU and trace conversions.
A pprof focus is a sampled-stack selection, not a census of all GC-associated
indirect effects. Trace/CPU diagnostic timing is not pooled with ordinary timing.

## Verification and retention

All 14 scenario processes and 194 child SQL/transaction oracles passed. Core
runtime/guest Git objects are identical to the fixed prototype. Ubuntu/Python
speedup/full qualification were not run. No correctness/release guard was changed.

After saving and verifying this archive in Git, remove task clones, local compiler
cache, profile tools, binaries and completed worktree. Keep the pushed experiment
ref, compact report/evidence and guard/cleanup receipts. Main's pre-existing
uncommitted investment-review draft and other task worktrees remain untouched.
