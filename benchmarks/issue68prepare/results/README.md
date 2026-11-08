# Issue68 and current PREPARE waits: source link and bounded capture

**Result: PARTIAL. #68 is the relevant existing issue, but the current PREPARE
wait has not been bound to its older UPDATE/page-latch mechanism.** The source
walk establishes that INSERT preparation opens tables and touches metadata;
it is not merely tokenization and does not execute the INSERT. A current-binary
DB-bound stack collector passes its live SQL control. The four fixed natural
suites have no PREPARE≥100ms and yield no natural stack. The control suite later
observes375/403ms PREPARE calls after its dedicated capture slot is used, so
"the phenomenon disappeared" would also be inaccurate.

Recommendation: keep this as a distinct reproducible entry under
[#68](https://github.com/masahitojp/mariamem/issues/68), cross-linked with
[#88](https://github.com/masahitojp/mariamem/issues/88), and preserve the collector
for a selected future measurement. Do not rename the old cause as proven, port
old function IDs blindly, change pool/defaults, or repeat batches automatically.
This finite step is complete with the missing evidence stated below.

## Related issues: what matches and what does not

| Issue/evidence | Confirmed | Still missing for this PREPARE case |
|---|---|---|
| #68 old UPDATE capture |355ms UPDATE, a snapshot inside its Exec window, structural undo-header page writer-latch path |That event's exact owner/full duration mechanism; any equivalence to PREPARE |
| #68 later owner/relay work |Short waits bind query rseg latch → purge-held latch → header page wait; observed IO/WRITE_FIX owner at registration |Natural long-wait attribution; not a cure or proof every delay uses that path |
| #88 current shop phases |Natural PREPARE≈400/800ms; mostly orders INSERT, sometimes item INSERT; both settings have observations across primary/warmup/control |Inside-call guest/host stack and waited object/owner |
| #93/#94/#95 |Closed prepared packet, input pipelining and last-statement-ID compatibility boundaries |They do not establish this successful-call latency mechanism |

Old owner/relay reports retain their1862f4a8/guest6d744220 source/settings/workload.
Current product isa3b2b645/guest14b41cea and a shop fixture. Old owner runs also
used explicit both-load/dump-OFF settings, unlike this unchanged product recipe.
Do not pool their counts or import old owner/page IDs into current calls.

- [Old captured UPDATE](https://github.com/masahitojp/mariamem/blob/697cbf8622c6561c27352804d4475b5b054587bc/benchmarks/updatecapture/results/README.md)
- [Prior caller phase report](https://github.com/masahitojp/mariamem/blob/eb85cc5c8632a5f4871ca3583b2510acd790373a/benchmarks/issue88samplephases/results/README.md)
- The source comparison retains exact old/current function-body digests. Current
  Fn5853 equals the prior named mysql_real_query body, supporting the control
  anchor. Several older undo-path bodies differ (16806/16621/18164); none of
  those IDs is used as a new owner-hook/symbol binding. Equal Fn17227 body alone
  also does not prove that a new PREPARE entered it. A full current C symbol map
  or new natural prepared stack is not claimed.

## Source walk

Pinned MariaDB source_commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e;
source-inputs.json binds three upstream files and immutable URLs. source-excerpts
retains the relevant original ranges. These line numbers are **unpatched
upstream**, not a full regenerated-source map. The project's12.3.3 prepared patch
has descriptor/metadata fixes but does not replace the table-opening block shown.
Current product guest/prepared_api.inc has the resident C API call atps_prepare.

| Edge | Source finding |
|---|---|
| Resident prepared route |guest/prepared_api.inc:ps_prepare calls mysql_stmt_prepare |
| Embedded client |libmysqld/libmysql.c:1599/1651 sends COM_STMT_PREPARE through stmt_command |
| Embedded dispatch |libmysqld/lib_sql.cc:108–173 advanced command calls dispatch_command |
| Server preparation |sql/sql_prepare.cc:2669/2698 creates Prepared_statement and calls prepare |
| Analysis |Prepared_statement::prepare parses SQL then invokes check_prepared_statement |
| INSERT validation |check_prepared_statement selects mysql_test_insert/mysql_test_insert_common |
| Open/metadata |mysql_test_insert_common:1446 invokes open_normal_and_derived_tables with MYSQL_OPEN_FORCE_SHARED_MDL |
| End of preparation |close_thread_tables_for_query and metadata-lock rollback-to-savepoint; statement transaction is asserted empty |

This makes table/metadata/engine opening a concrete candidate location. MDL
access is visible in source, not a measured MDL wait. The older undo allocation
happened on an execution path; ordinary successful PREPARE here does not start
the requested data-changing statement. A shared lower-level page/I/O/notification
problem remains possible, as does a distinct opening/cache/metadata path. Static
reachability does not choose among them or identify a missing host syscall.

## Current source and collection protocol

2026-11-08, measured source_commit
`2ef12c4a455d8e759325c277827355bd35d27ec6`; product baseline
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Source identity and clean status checked before building; tracked runtime,
guest, release and API files remain equal to product. The already-validated
experimental two-argv16/8MiB selector is reused, with origin and overlay hashes
recorded separately. This is a diagnostic, not a canonical guest/default change.

Same shop70 cases/Pipe/P8/cap9; M1/16GiB/macOS27.2, Go1.27.3/CGO0,
GOMAXPROCS8/GOGC100. One positive control, then exactly16/8/8/16 natural suites.
No old48-child UPDATE-only batch, extra repeats or parameter sweeps. Original
business SQL/order/oracles and sample phase census remain unchanged. Five
processes/350 cases pass and end with active mappings0 and successful Close.

Root Start and each Fork execute in pprof.Do with a unique per-process db_id;
guest goroutines spawned by StartInstance/ThreadLaunch inherit that label.
The measured handle carries the same ID into the loader's caller record.
At100ms inside PrepareContext, at most one stack snapshot per process is taken,
maximum2MiB. Actual caller entry/return and profile begin/end are recorded.
A usable profile must be wholly within that caller window, untruncated and
contain generated guest frames under the exact DB label. A point snapshot does
not measure the complete duration continuously blocked or identify an owner.
Captures are serialized after suite timing/cleanup; timers/labels/profiling can
perturb scheduling. This is not an uninstrumented performance comparison.

## Controls and finite results

The separate positive control executes actual SQL `SELECT SLEEP(0.25)` on the
labeled root before Snapshot; it is not a sleep inserted before the API call.
Its caller window is252.389ms; profile starts101.048ms after entry, lasts2.117ms,
28,368bytes, untruncated.12 label-matched blocks include8 generated-guest blocks;
the foreground query chain contains current p7.Fn5853 (mysql_real_query anchor
validated by exact body equality). Background timed futex stacks are not claimed
as the natural PREPARE mechanism. Wrong DB, outside caller window, truncated
profile and missing guest frames are rejected by deterministic replay mutations.

| Natural suite |Pool MiB|PREPARE calls|Max PREPARE ms|≥100ms|Captures|
|---|---:|---:|---:|---:|---:|
|0|16|63|14.506|0|0|
|1|8|63|16.743|0|0|
|2|8|63|22.877|0|0|
|3|16|63|7.923|0|0|

Thus these252 natural PREPARE calls provide no long-call stack and no
SAME_PATH/DIFFERENT_PATH finding. They do not invalidate the earlier observed
tails or establish a frequency/cure. During the control suite's later normal
cases,16MiB had PREPARE375.465ms and403.384ms (ApplyDiscount music/games).
The control-only slot was already used for SQL SLEEP, so neither has an internal
snapshot. Do not move the earlier control snapshot into either PREPARE window.
The control intervention, timer activation policy and profiling differ from
natural runs; no claim is made that the observer caused or removed delays.

## Stopping point and missing evidence

The missing item is a natural long PREPARE's **same-DB foreground stack**, followed
only if necessary by a currently bound wait/owner sample. Without it, choosing
undo/page I/O versus table/metadata/host transport would be speculation. The
collector is now reusable; prefer attaching it to a separately selected next
measurement rather than spending another default batch here. A clean build took
124.56s on this host. Runtime overhead and successful future reproduction cost
remain uncertain; more repeats cannot be promised to yield the needed sample.
No repair,8MiB adoption, main integration, Qualification or release follows.

## Recompute and reproduce

```sh
python3 benchmarks/issue68prepare/results/analyze.py --check
```

Read-only replay checks the bounded real control profile, foreground binding,
clock window, metadata, cleanup/counts and four negative mutations, then compares
summary byte-for-byte. observations.json retains all five suite traces, all
sample operation durations and capture metadata; the full bounded28KiB control
profile is retained once. Source hashes/excerpts and prior-function comparison
preserve the source reasoning without a complete source/build tree. SHA256SUMS
covers the result bundle. No opaque archive or routine CI payload is introduced.

To rerun after a new Human selection, use a clean disposable checkout of this
branch and a workspace with worktree/,temp/,evidence/:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 900 -- python3 WORKTREE/benchmarks/issue68prepare/run.py WORKSPACE
```

The checked-in runner adds an explicit workspace argument to the original
external execution script (original digest in assessment). Source/runtime
identity checks precede build; one live control must pass before four natural
suites. Preserve new observations/profiles, reduce and replay, then finalize
and clean all owned cache/build/source state. Initial budgets2h active/30min
tooling, zero heavy CI submissions; no automatic continuation is authorized.
