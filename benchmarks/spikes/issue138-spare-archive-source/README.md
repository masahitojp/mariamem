# Why the spare-archive marker was absent: source diagnosis

The failed case did not establish the conditions for its marker. A nonzero
request is not synonymous with redo turnover or a disconnected SQL session:
the marker additionally requires the page cleaner to enter its no-LRU, no-sync-
target, idle wait branch before consuming that request. The exact old interleaving
is **unknown**, because the run recorded none of those internal states. Source
supports ordinary alternative paths that consume a request without this marker;
it does not establish an engine regression or an unreachable WASIX feature.

**Recommendation for the next Human decision:** authorize one legacy-only finite
case with the existing engine/hook inputs, changing only `innodb_flush_sync=OFF`
and `innodb_lru_scan_depth=100` relative to the failed supplemental case, with
explicit configuration readback. Keep the old 4MiB/256x64KiB data and single-
capture/restore/isolation checks and the existing five-second positive-marker
requirement. These settings address two concrete bypasses while preserving the
original marker predicate. The strongest objection is that neither bypass was
measured in the failed run: another failure remains possible, and a PASS would
prove the new case's branch coverage, not retrospectively identify the old cause.
For that reason this is a falsifiable one-case proposal, not a parameter campaign
or permission to execute now. No previous FAIL, gate or oracle changes here.

## Inputs and evidence boundaries

This source-only slice starts at e6ce0837e757cbf9075bb5534834df71e34ec182.
[PLAN.md](PLAN.md) fixed active45min/tooling10min/wall60min, scratch2GiB/free6GiB,
and zero guest/host builds, translation, SQL, CI or benchmarks before analysis.
The initial checkout had no tracked, untracked or ignored user state.

| Identity | Exact value |
| --- | --- |
| MariaDB `source_commit` |620a4b5624222048fece7fe1789978ae0675cae2|
| Annotated `tag_object_sha` |308a50778fb4916ddde0d2923feea3d11dcc92c8|
| Official archive SHA256 |f4aee0d043f844d287a9b6b0a1ae9a103d6dda407d807b80358943416da7d37e|
| Actual legacy producer |32c799031f619164d3730b61a0bc9d7ae48dcd9b|
| Actual native producer |4b3954a0faf42986459bc1ee68727be16d67bcbb|
| Failed-case legacy guest |d29caafda1ed32851df856dc7fcba3871c3c7ea75df8f2c5d4976b3eb9132c95|
| Existing native guest |889f21b796c4daaf5244486cce84bfe6a82c758437af400e831d0ed10f0a067e|

The previous actual Git-object verification remains at
[identity.json](../issue137-helper-continuation/evidence/floor6/identity.json).
This slice reacquired the official exact-commit archive, checked its locked full
SHA256, and extracted selected engine files, matching all six previously known
whole-file hashes. No SDK was acquired. Additional files were selectively read
from that same verified archive. The one bootstrap recipe file was independently
checked against its locked full-file hash at recipe24be9371a2f6c71250a2356631ad6feab2280b02.
All coordinates below are **pristine engine** coordinates unless marked patched.
[Coordinates/hashes](evidence/coordinates.json), [selected source text](evidence/source-excerpts.txt),
[cross-file lookup](evidence/cross-reference.json), [acquisition](evidence/acquisition.json).

## Proven source facts

The pending request is a page-cleaner-local `lsn_t`, not an atomic counter or a SQL
configuration flag. An exhaustive name lookup across the archive's InnoDB C++
source/headers finds its declarations, assignments and uses only in `buf0flu.cc`.
The separate local in `buf_flush_sync_for_checkpoint()` returns a value to the
cleaner's local. Atomic flush targets and `need_checkpoint` are different state.
[Complete request-name inventory](evidence/request-inventory.json).

| Stage | Source and conditions | Result |
| --- | --- | --- |
| Buffered archive writer |`log0log.cc:1759-1772`, archive enabled and write offset+length exceeds current file size |Calls `archive_new_write()`|
| Current/next file handoff |`log0log.cc:1224-1279`, then `archive_create(lsn,true)` at1282-1358 |Creates or opens the next file, assigns old `log` to `resize_log`, writes through the new `log`; a delayed checkpoint can grow `resize_target`|
| Sole buffered request production |`buf0flu.cc:1878-1944`, checkpoint `end_lsn >= first_lsn+capacity()` **and** `resize_log.is_opened()` |Advances `first_lsn`, installs the new size, returns next-file LSN through `archive_header_was_reset`; current LSN alone is insufficient|
| Propagation |`buf0flu.cc:2206`, `log_checkpoint_low():2214-2270` |Returns the request after writing/flushing checkpoint data; unchanged/no-progress checkpoints can return0 at2221-2235|
| Sync producer |`buf0flu.cc:2519-2550`, called at2822 |Stores the request from sync/furious checkpoint; can clear `buf_flush_sync_lsn` when target is met|
| Ordinary producer |`buf0flu.cc:2857-2887`, shared `set_almost_idle` tail |Consumes previous request, then may get a new request from `log_checkpoint()`. Fully-unemployed entry first sets idle and clears normal sync target; other entries can bypass that idle assignment|
| Consumption/reset |`buf0flu.cc:2768-2779`, callers2821 and2873 |For nonzero request, takes log read lock and attempts `archive_create(lsn,false)` only if archive still enabled; always returns0. The idle caller assigns0; the sync caller consumes the old request before replacing it with a new checkpoint result|

`archive_create(...,false)` is best-effort preallocation: if a spare already
exists it can return without work; it does not install `resize_log` as the
foreground `ex=true` handoff does. That can make a consumption cheap, but cannot
by itself hide a positive marker: the marker precedes the call and tests only
the pending scalar. Turning archive OFF can discard a stale request at its
consumer, but the failed supplemental source kept it ON until marker success.
The old ON-OFF common case is a different execution and remains a PASS.

`capacity()` is `file_size-START_OFFSET` (`log0log.h:695-696`), not the SQL variable
as a cumulative redo threshold. The checkpoint can change current file size and
advance the archive origin. Two initial log lengths of generated redo do not
prove a particular later checkpoint's boundary or a pending next-file request.

### Configuration, wakeup and wait gates

`ha_innodb.cc:17668-17736` assigns the dirty thresholds and calls
`page_cleaner_wakeup()` under the flush-list mutex. In `buf0flu.cc:161-210`, maximum
dirty percentage0 makes the wake condition permissive, including at zero dirty
percentage; LWM0 means use the maximum threshold rather than disable flushing.
It does not set `create_spare_archive`, open an archive file, or select the idle
checkpoint producer. Adaptive/background flushing still has its own decisions
(`buf0flu.cc:2611-2664,2960-3040`). Thus zero thresholds trigger ordinary flushing,
not the target archive request by definition.

The supported embedded bootstrap fixes a16MiB pool and maximum, with2MiB redo
buffer (`wasm/lite4mariadb.c:323-347`). The actual legacy full prepared recipe
matches reconstructed SHA d2b1a3c65b1f6a0b46de37221507b80150626c58eaa61d6033038ace46c40df9;
the native recipe was reconstructed too and retains those exact arguments.
[Full-file proof](evidence/bootstrap-proof.json). Default LRU scan depth1536,
dynamic minimum100, is registered at `ha_innodb.cc:19569-19572`. `need_LRU_eviction()`
at `buf0flu.cc:2756-2762` is true when `try_LRU_scan` is false, or when LRU>256 and
free pages<scan_depth/2. The failed sixteen-MiB data burst can therefore maintain
LRU pressure in a sixteen-MiB pool. This is a plausible bypass, not measured
proof that it held at the decisive instant; normal LRU flushing can restore free
pages (`buf0flu.cc:1286-1335,1790-1821`).

The positive marker requires all of the following, in this order:

1. Top-of-loop sync-target check does not take the `srv_flush_sync` furious path.
2. Under the flush-list mutex, `need_LRU_eviction()` is false and shutdown is not
   in its final phase.
3. The shared adaptation's fresh `buf_flush_sync_lsn.load()==0` check passes.
4. `page_cleaner_idle()` and (flush list empty or dirty LWM0) are true.
5. The local `create_spare_archive` is nonzero.

Ordinary timed wait also occurs when gate4 fails, without a pending request. A
startup `timed_wait` marker therefore cannot identify any archive event.
`page_cleaner_wakeup()` and `buf_flush_ahead()` can set idle false, and furious
requests can set the atomic sync target and signal the cleaner (`buf0flu.cc:2340-2450`;
`mtr0mtr.cc:1092-1132`). SQL active-connections0/ready/busyfalse reports none of
these internal conditions (`internal/control/shared.go:268-280`).

### Archive and log-size transitions are not an unexplained task queue

The SQL archive callback directly calls `log_sys.set_archive()`
(`ha_innodb.cc:19772-19783`). That function synchronizes with the log latch, can
wait/retry around a pending handoff/checkpoint or reject an active resize, renames
and rewrites the header, and sets `archive` before returning (`log0log.cc:765-981`).
It does not itself create a pending spare request.

Circular-mode size changes start a resize and the SQL callback waits for its
completion, waking the cleaner and, if needed, appending dummy checkpoint records
(`ha_innodb.cc:18857-18929`; `log0log.cc:988-1118`; completion at
`buf0flu.cc:2183-2192`). In archive mode, a size change can instead update the
future `resize_target` without changing the current file immediately
(`log0log.cc:1004-1017`). The failed case used size-before-archiveON, so a generic
claim that the SET merely queued an unconsumed asynchronous command is unsupported.
Actual values were not read back in that supplemental run; the proposal adds them.

## Shared adaptation and detector audit

The original algorithm already diverts a nonzero pending request from indefinite
idle wait to timed wait. The shared adaptation adds one under-mutex sync-target
recheck around **both** original wait choices; it preserves the request variable,
its producer/consumer sites, the nonzero goto, timeout arguments and following
work. If a sync target arrived after the pre-lock read, skipping both waits does
not reset the pending request; normal processing still consumes it. The observer
then adds once-per-engine prints at the nonzero goto and the common timed label.

Both steps were applied with zero fuzz to the exact pristine complete file:
5e14748459968a82a3dcf2b506cf9728ce0d8f3361c66318e992fe930d1db818
-> a3dd5252ad5866f8b486209f65b4e772f39c9a2d3d5a961b07cbf136a29ce123
-> c149bbf197f772aad5b2cdf9790f7e51fd3975ea08860a4cd398972331b44fcc.
The last hash matches **both actual native and legacy prepared inventories**.
[Patch proof](evidence/patch-proof.json), [patched wait with coordinates](evidence/patched-wait.txt).

The print reads no request off a queue, resets no LSN and precedes `goto timed_wait`.
If the intended positive branch executes, its first occurrence should emit the
positive marker; later occurrences are intentionally coalesced. The log endpoint
reads a16KiB tail, not a destructive drain (`internal/control/shared.go:125-139`).
The failed root returned only the27-byte timed-wait line, so routine tail truncation
is not supported as its explanation. Ignored `fprintf` errors, corrupted logging,
or an unseen host fault cannot be disproved by these logs, but there is no evidence
for them. The hook is adequate for **positive branch coverage**, but blind to
request production, origin, consumption outside the idle branch and skipped gates.

[Optional observation-only diff](optional-request-observer.diff) proposes four
bounded diagnostics: first nonzero sync producer, first nonzero ordinary-checkpoint producer,
first nonzero consumer, and first pending-request gate snapshot. Existing branch
markers remain. This is **not applied or compiled and is not a mandatory new
prerequisite** to the recommended case. It is available if the Human instead
requires direct causal discrimination before another negative result. Conditional
braces preserve the original ordinary-checkpoint assignment; no barriers, sleeps or forced branch
are added. Snapshot reads are point-in-time, can race like the original LRU views,
and stderr output can perturb scheduling. The origin label means call site,
not a claim that the ordinary caller is idle. Pre/post hashes are pinned in
[proposal identities](evidence/proposal-identities.json). Applying it would require
a new source pin, full prepared image guards and a fresh exact binding review;
old guest receipts would not qualify that new instrumented artifact.

## What the raw run does and does not show

[Immutable raw observations](evidence/run-observations.json) preserve the original
file/hash reference. Both supplemental observations report ready, not busy,
active_connections0, and only `ISSUE138_BRANCH timed_wait`. The second follows the
single five-second marker wait. Source assertions imply256 successful inserts and
redo advancement>2x4194304. The exact supplemental LSN numbers and internal request,
LRU/free/idle/sync-target/archive flag values were not logged. The common paired
case's LSN36889->16947491/checkpoint16959831 belongs to that separate PASS and is
not substituted for the supplemental case.

One source-valid interleaving is: a sync checkpoint produces a nonzero request;
wakeups leave the cleaner non-idle or LRU pressure bypasses the wait; a subsequent
ordinary-tail/sync pass consumes the request; a no-progress checkpoint returns0;
the cleaner eventually waits with no request. Another is that no qualifying
header reset/request had yet reached the observed idle phase. Both match the
sparse log. There is no basis to rank them as the actual cause. In particular,
client drain is not a page-cleaner scheduling barrier.

## Reachability and proposed finite execution

Saved Release configurations have PMEM OFF and WSREP OFF; the shared WASIX platform
forces PMEM OFF. The **buffered** producer/handoff/checkpoint/request path remains
compiled and uses ordinary files; it needs no PMEM, external fault, exceptional
startup, debug scheduler or manufactured archive. A source-valid positive sequence
is a completed archive handoff, followed by fully-unemployed checkpoint returning a
nonzero request while idle=true/sync-target0/no-LRU, followed by the next wait gate
before a new writer wake. This proves conditional reachability in the configuration,
not that the failed workload realized it. There is no proven unavailable critical
dependency or proof the branch is unreachable. The upstream `log_archive.test`
explicitly skips embedded mode and fabricates recovery files/restarts; it is not
borrowed as embedded live-branch evidence.

[Proposed test diff](proposed-legacy-case.diff), **text only**:

- Use one fresh ordinary root, archive initially OFF, no inherited snapshot flags;
  record buffer pool/page size/adaptive-flushing/IO-capacity, save the four modified
  controls, and retain the existing4MiB resize-before-ON sequence.
- Set dynamic LRU scan depth100 before the dirty-threshold callbacks wake the
  cleaner; set dirty maximum/LWM0 as before, but set flush_sync OFF. Read back
  archive1/log-size4194304/flush_sync0/LRU-depth100/dirty0/LWM0 and reject any mismatch.
  Confirm the positive marker is absent before the workload.
- Keep the exact256 ordered64KiB inserts and redo assertion. Lower LRU depth reduces
  its free-page threshold from768 to50; disabling sync flush bypasses the sync
  producer and lets ordinary page flushing reach the fully-unemployed checkpoint
  producer. The ordinary tail can also be entered while non-idle via
  `goto set_almost_idle` (2953-2955), so this does not ensure that its last
  nonzero return coincides with the fully-unemployed entry. Neither setting
  changes the target `if` or supplies a fake request.
- Disconnect via the existing API and wait once for the **existing positive marker**
  for5s, checking live root as before. Absence is a failed finite case: preserve
  logs/config, stop; do not retry, infer success from checkpoint, or attempt capture.
- On positive evidence, restore settings including LRU depth, switch archive OFF,
  retain exact ordered payload digest, one capture, two restored children and
  sibling-isolation/cleanup. The earlier common paired test and its oracles remain
  unchanged, and a new positive result never relabels the old FAIL.

The diff applies with zero fuzz to the pinned original supplemental Python fixture
and its resulting text passes AST parsing only. The optional observer diff also
applies to the exact C149 postimage in disposable source scratch. No code outside
this new report directory was changed, imported or executed as a runtime test.

### Route, cost and adoption boundary for the next decision

Recommend **legacy first and only one producer initially**. Both paths have the
exact same prepared page-cleaner function, platform gates and buffer-pool arguments;
a positive legacy execution can demonstrate that shared C++ branch. It cannot
claim the native entry executed the new workload. If138 requires a positive
observation on each entry, one later native execution is still required **after**
legacy success and an explicit bounded decision; source equality alone must not
silently discharge that acceptance condition. No checkbox is completed here.

The primary proposal changes only the supplemental SQL fixture, with producer32c799
and guest engine/hook inputs unchanged. The helper compatibility fix does not
justify a producer change. Pin the applied fixture SHA and separate tooling
commit before that future execution; the clean producer checkout remains32c799. Existing exact legacy binding can be reused only if
the fresh guest reproduces d29caafd and the real installer rechecks all complete
bodies/TLS/ABI and manifests; otherwise pin/review a new binding before compilation.
The old native4b3954/889f79 cases/601 named observations and matched legacy archive
PASS retain their exact source/platform/execution context; no old binary exists.

Proposed separate budget: active20-30min/tooling<=5min; one fresh guest<=60min,
translation+binding+host<=30min, original smoke/P1six/P2fifteen plus common and new
finite case<=15min, wall<=2h, CI0/benchmark0/public expansion0. Previous actual guest
was22.5min, translation141s and host196s; these are planning evidence, not a speed
promise. Prior whole-checkout peak6.462GiB and incremental guest growth about6GiB
suggest minimum start availability~12.5GiB at floor6, with~14GiB recommended for
variation. Propose an explicit owned12GiB ceiling/floor6 only if newly authorized;
this source slice's2GiB guard is not heavy-work permission. Count host/container/
TMPDIR/GOTMPDIR/cache/download mounts; remove SDK/source before host as before.
If optional hook changes are selected, pin new full pre/postimages and source,
review the new binding and qualify that artifact; do not borrow old runtime PASS.
No two-route rebuild is launched by habit.

No main/product13.0.2 selection, public C3/bothOS/installed consumer/factory work,
release or performance claim follows.137/138 remain Open. This adds a bounded
source/configuration explanation to the real removed-adapter versus added-profile/
helper/binding costs; overall maintenance burden remains **INCONCLUSIVE**.

## Verification and cleanup

Source-only checks and final disposal are recorded in evidence/verification.json
and evidence/cleanup.json; no unchanged runtime tests were run. The four protected
parent files and all historical evidence are unchanged. Source scratch and guarded
acquisition scripts are disposable after report preservation; no other owner,
workspace, cache or Docker image is in cleanup scope.
