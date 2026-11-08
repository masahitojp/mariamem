# Related settings: source map, no setting change

Current product/guest pins and all25 argv are guarded by the inherited selector.
Pool size8/16MiB is the existing two-arm diagnostic selector; no other argv change
is introduced here. The table distinguishes explicit argv from values not queried.
Only pool size/max were freshly checked through SHOW VARIABLES in these runs.
Simulated AIO is additionally confirmed by observed Fn18241/Fn18242 execution.
Other rows are a source-path map, **not fresh effective-value receipts**.

| Setting | Pinned argv / observation | Relationship to this wait | Priority |
|---|---|---|---|
| innodb_use_native_aio | explicit0; simulated path actually observed | simulated implementation submits I/O and completion as separate tasks on the pool | Direct mechanism |
| innodb_read_io_threads | explicit loose option1 | `os_aio_init` constructs read_slots with this callback/task-group concurrency; simulated initial task and completion share that group | Direct admission candidate; do not equate this with all pool limits |
| innodb_buffer_pool_size / size_max | explicit16M; selector changes both to8M; SHOW verified per run | changes which pages must be read and load volume; does not explain the measured microsecond I/O versus hundreds of milliseconds dispatch by itself | Demand/background context |
| innodb_buffer_pool_load_at_startup | not overridden by pinned argv; no new SHOW value here | `buf_dump_load_func` temporarily sets global pool concurrency to read_io_threads while `buf_load()` runs, then calls `set_concurrency()` to restore automatic selection | Relevant phase to establish, not a permanent read1 global cap |
| innodb_buffer_pool_dump_at_shutdown | not overridden; no new SHOW value | may affect the input for a later startup load; not the already completed read request directly | Baseline/input context |
| innodb_write_io_threads | explicit loose option1 | distinct write task group, using the shared worker infrastructure | Possible competing work; not observed as cause |
| innodb_purge_threads | explicit loose option1 | background work may wait/read pages on the shared execution infrastructure | Possible competing work; no causal owner/pool accounting proof |
| innodb_log_buffer_size | explicit2M | redo/write-side work; no direct evidence for this PREPARE read dispatch delay | Lower priority |
| innodb_flush_log_at_trx_commit / innodb_flush_method | not overridden; no new SHOW values | write/durability path; the captured synchronous read itself took2–3µs | No sweep proposed for this question |

Two distinct concurrency controls must stay separate:

- **Read task group:** `io_slots(max_events, srv_n_read_io_threads)` retains its
  group limit. `simulated_aio::submit_io` assigns `cb->m_group` to the initial
  internal task; the completion resubmission uses the same internal task/group.
- **Global generic pool:** desired concurrency is separately managed. Temporary
  startup/load/recovery calls use the read count and subsequently reset it.
  `maybe_wake_or_create_thread()` considers active minus long minus waiting
  workers. We did not sample these counters or prove which gate rejected work.

Pinned `tpool_generic.cc` also defines a400ms maintenance interval and500ms
long-task threshold. Those constants make the observed quantization a reasonable
hypothesis to test, **not evidence that a timer tick released either request**.
No maintenance timestamp, worker-state counter or active startup-load phase was
captured. `wait_begin()` can return without accounting if TLS is not a pool
worker or is already long-running; seeing the call alone is insufficient.

Source excerpts, line numbers and original file identities are retained in
[source-excerpts.json](source-excerpts.json) and
[upstream-files.json](upstream-files.json), upstream commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`. Current generated function preimages
are pinned separately in [source-functions.json](../source-functions.json).

Recommended order: first distinguish global versus read-group admission with
counters sampled under their existing locks, at the same request boundaries.
Then select one targeted setting experiment if that evidence warrants it.
Do not simultaneously vary read count, load/dump, write flush and pool size.
