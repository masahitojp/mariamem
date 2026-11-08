# Issue140: natural PREPARE stacks captured with one watcher

**Captured on both8MiB and16MiB.** The two matching foreground stacks stop in
InnoDB's page-read completion path, structurally corresponding to
`buf_page_get_gen → buf_page_t::read_wait → block_lock::s_lock_nospin`, then the
host's untimed AtomicWait branch. The same DB also has background purge waiting
through read_wait. This locates the immediate wait; it does not identify a page
ID, current owner, completion task or the entire cause of≈400ms.

Relation to #68: common buffer/page-wait subsystem, **different immediate gate**
from the old UPDATE's undo-header writer-mutex acquisition. Do not relabel it the
same root cause, or assert the query and purge wait for the same page. #88's8MiB
benefits remain separate; the wait is not exclusive to8MiB. Occurrence/frequency
and the pool setting's causal effect are not established by this diagnostic.

## Fixed protocol and source

[Issue140](https://github.com/masahitojp/mariamem/issues/140), milestonev0.7.0;
related [#68](https://github.com/masahitojp/mariamem/issues/68) and
[#88](https://github.com/masahitojp/mariamem/issues/88).
Measured source_commit `d18a1d86d427e5ee67da3b8d4d9ae8227863a565` is the exact clean pre-build harness. Product:
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; origin guest:
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Tracked runtime/guest/API/release files are unchanged. Same previously validated
experimental16/8MiB argv selector, binary, Go1.27.3, CGO0, GOMAXPROCS8/GOGC100,
M1/16GiB/macOS27.2, Pipe/P8/cap9, unchanged70-case shop SQL and oracles.

One20ms watcher scans atomically published in-flight PREPARE references. There
is no per-PREPARE timer/goroutine. At≥100ms it takes at most one bounded2MiB
profile per process. Exact caller/snapshot times and DB labels are retained.
One actual SQL SLEEP control precedes eight fixed natural suites: two reversed
blocks of16/8MiB×watcher on/off, no extra runs. Profile/timers/labels can still
perturb scheduling; the on/off contrast is not an overhead or frequency bound.
This is not a performance A/B or an8MiB adoption gate.

## Natural results

| Run |Pool MiB|Watcher|Suite ms|PREPARE≥100ms|Usable capture|
|---|---:|---|---:|---|---:|
|1|16|off|584.733|388.932ms|0|
|2|16|on|536.455|none|0|
|3|8|on|757.144|385.950,394.684ms|1|
|4|8|off|952.727|383.359,774.771ms|0|
|5|8|off|585.970|none|0|
|6|8|on|569.580|none|0|
|7|16|on|622.735|400.614ms|1|
|8|16|off|634.222|none|0|

All8 natural suites/560 cases plus1 control suite/70 cases PASS. Every process
ends with active mappings0 and successful Close. Expected sample phase counts
are checked for all189 loaders. All durations/tails and off runs are retained.

Both captured calls are the first PREPARE:
`INSERT INTO orders(user_id, status) VALUES (?, ?) RETURNING id`.

| Captured caller |8MiB|16MiB|
|---|---:|---:|
| Case |CancelOrder/pending|CreateOrder/five_lines|
| DB label (process-local) |issue68-db-10|issue68-db-9|
| Caller duration ms |385.949|400.614|
| Snapshot starts after caller entry ms |115.854|109.507|
| Snapshot duration ms |4.373|2.645|
| Full bounded profile bytes |232,823|128,808|

Microsecond rounding explains the0.001ms difference between the8MiB phase
measurement and its inner capture window. Both profiles are wholly inside the
actual caller window, untruncated, and bound to the exact loader's DB and lane.
Their foreground generated-function sequences are identical:
`Fn16624 → Fn16787 → Fn18164 → … → prepared request` (stack order, inner first).
Both park at base.go1946, the notify/failure branch with no timeout; it is not
proof of a400ms host timer. The snapshot proves where the thread is parked at
that instant, not that all385/401ms was spent in one continuous wait.

## Current-source binding

source_binding.py checks current generated function bodies, call arguments,
initialization base and static literals; source-binding.json preserves hashes.
These are **selected structural C/Go correspondences**, not a complete recovered
C symbol map or reuse of old function numbers.

- p3.Fn18164 reaches p8.Fn16787 at the read-fixed-page branch. The pinned
  upstream buf0buf.cc:2809–2829 branch calls block->page.read_wait(trx).
- Fn16787 calls Fn16624(block+24), with wait/stat calls conditional on its second
  argument, matching buf0rea.cc:206–238. block_lock::s_lock_nospin in
  sux_lock.h:392–397 calls rd_lock_nospin. Fn16624's recorded PC is inside its
  condition wait; current code anchors and hashes are retained.
- In each same-DB profile another stack goes through
  Fn18162→Fn17217→Fn17221→Fn18228. Current Fn17217 references the decoded
  trx0purge.cc filename and assertions at886/887 (`hdr_page_no != FIL_NULL`,
  `tail.trx_no <= last_trx_no`), matching purge_sys_t::choose_next_log and its
  page-fetch path. These literals identify code; no assertion failure occurred.
- That background path uses read_wait too. No runtime page address/ID, trx value,
  lock owner, acquisition history or I/O task identity was recorded. Equal
  functions or DB labels do not prove equal waited objects.

Pinned upstream C commit:
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. Source hashes/immutable URLs and
selected original excerpts are preserved. Line ranges are unpatched upstream;
no claim is made that every generated frame has a C symbol binding. buf0dump.cc
was also inspected but is not assigned as the observed background stack.

A relevant source condition remains: tpool_wait_begin/end in read_wait are
inside `if (trx)`, while the shared-lock wait is outside. buf_page_get_gen gets
that pointer from current_thd/thd_to_trx. **Its actual value in these snapshots
is unknown.** The missing-wait-notification hypothesis must not be promoted to
a cause or fix until that branch and the relevant task/queue are observed.
I/O here includes asynchronous memory-VFS execution/completion; this is not a
measurement of physical disk latency. Metadata/table opening reaches this
InnoDB path; the captured foreground stack is not merely a long parser loop.

## Binding controls

The actual SQL SLEEP control has matching foreground mysql_real_query anchor
and DB label, with a wholly inside-call bounded snapshot. Replay rejects wrong
DB, outside caller window, truncation and removal of the required read-wait
foreground frame. Each natural capture also matches its exact loader's ID,
lane, PREPARE ordinal and retained duration. Source tests guard the current
call/literal layout. No natural profile is borrowed from a control, another DB,
other process or older guest. Full3 bounded profiles are retained once.

## Recommendation and stopping point

The fixed step succeeds: **natural long PREPARE captured and its immediate
path located on both pool sizes**. Keep #140 open for the remaining cause step.
The old #68 UPDATE waited to acquire the page writer mutex; this PREPARE waits
for page read completion through a shared lock. Their common underlying cause
is still unverified, so neither settings nor host/guest code is changed.

The next useful bounded observation, if selected, is the same waited page ID,
actual trx-null/non-null branch and read/completion registration/resume timing.
Only then choose between missing pool wait notification, queued completion,
page-owner work or another reacquisition delay. Do not begin a general parameter
sweep or repeat whole-suite performance measurements to answer that question.
No additional collection follows this fixed8-run exit automatically.

## Recompute / reproduce

```sh
python3 benchmarks/issue140prepare/results/analyze.py --check
python3 benchmarks/issue140prepare/source_binding.py WORKTREE OUTPUT.json
```

The first is read-only and needs no temp/build/network: all nine traces, phase
records, capture windows, effective settings, case/cleanup counts, foreground/
background sequences and four boundary mutations are replayed. Summary compares
byte-for-byte. Source binding reads committed current generated files, not a
new C/Go build; compare OUTPUT.json with source-binding.json.

For a future approved fresh execution, use a clean disposable checkout of this
branch with worktree/,temp/,evidence/, Go1.27.3 and the recorded host conditions:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue140prepare/run.py WORKSPACE
```

The checked-in runner adds an explicit workspace argument to the original
external script (digest in assessment). Identity/runtime equality checks precede
build, and the live control must pass before the fixed8 natural suites. Save
new results separately, reduce, replay and clean owned scratch. The observed
build cost is in inputs.json; reproduction success for a future rare event is
not guaranteed. Initial budgets2h active/30min tooling, heavy CI0. This report
and its checksum-bound profiles do not authorize a product fix, default change,
main adoption, Qualification or release.
