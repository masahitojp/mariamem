# Issue156: dictionary-contention notification prototype

Question: does wait notification around the **actual eviction dictionary lock
slow path** restore queue progress in the previously controlled pending-clear
ordering, while preserving exclusion and balanced accounting?

Product bytes/source: 8df45792a927e440972266ee799d6f7223713e14;
source-path report: 4a7f99353c0dd7358875276d7f9a4cbd045cdbef.
This is a generated-code overlay experiment, not a canonical C patch, natural
PREPARE reproduction, performance measurement, or adoption decision.

## Boundary / caller audit before execution

Pinned C dict0dict.cc:1320 calls lock(); dict0dict.h:1437-1441 performs try-lock
then lock_wait. The proposal is the equivalent of:

```cpp
if (!latch.wr_lock_try()) {
  tpool::tpool_wait_begin();
  lock_wait(SRW_LOCK_CALL);
  tpool::tpool_wait_end();
}
```

Only inside evict_table_LRU, not the common dict_sys_t::lock implementation.
For this prototype the corresponding generated Fn17744 slow branch calls the
real TLS-aware Fn16583/Fn16584 around its unchanged Fn17733. A test callback
selects one TLS/candidate arm; all ordinary background calls remain unchanged.
This selection and callback are instrumentation, not a proposed product API.

Known master callers: srv_master_do_active_tasks and srv_master_do_idle_tasks
(srv0srv.cc:1247-1280). Neither brackets eviction with wait notification.
The master callback's earlier functions return before reaching eviction; no
lexical begin/end scope spans that call. wait_begin is **not nesting-safe**:
tpool_generic.cc:856 asserts !is_waiting, and release code would increment twice.
The prototype asserts selected caller WAITING/LONG bits are clear before entry.
LONG-task notification is a no-op upstream, but LONG behavior is not a tested
arm here. This is not an exhaustive transitive audit of every engine caller.

Non-pool notification checks TLS and does nothing. Uncontended acquisition
must never call notification. Purge's shared dictionary wait is explicitly
outside this first prototype; a master-only result cannot cover that other wait.
No process-wide WAITING wrapper, timer period, read count or pool policy change.

## Fixed matrix and oracle

- pending/unreported, pending/reported, late-submit, uncontended: concurrency
  1 and16, three repeats each (24).
- non-pool contended caller: concurrency1, three repeats (3).
- Total27 cases, one local Go overlay build; no C build, CI or natural sampling.

Use the existing controlled pool factory/init barrier/manual maintenance. A
calls real eviction. A harness owner holds the real initialized dictionary latch;
B stands for work needed by that owner. No SQL or page content is synthesized.
Unreported A must keep B queued for an imposed50ms, with active1/waiting0/
long0/pending0/queued1; explicit maintenance then advances B. Reported A and
late-submit B must progress without maintenance. The reported arm must show
waiting1 while owner still holds the latch, returning to0 after acquisition.
The fast path must emit no slow-path/notification/futex event.

Non-pool control: a pool task owns the dictionary latch; the root guest thread
runs eviction. A host-only channel releases the owner after root enters the
real dictionary futex. TLS must be null and notification accounting stay0.
Owner release/wait control is harness code. No claim is made to run a full
master callback or an actual PREPARE/read request generation.

Every contended case must enter actual WASIX Futex_wait at the bound dictionary
address and must not acquire until owner release. Eviction retains its original
release code; the harness owner uses the same CAS/wake semantics. The small
initialized dictionary must remain below its configured eviction threshold, and
removed table count must be0. All task refs0, workers retire (1 fast/nonpool,
2 other arms), pool destructor returns, ordinary guest shutdown/WaitThreads and
mapping disposal complete. Changed lock/array/TLS bindings fail rather than guess.

## Cost / stop / preservation

Tooling budget30min, one build expected~100s; test deadline120s, per-barrier2s,
whole task execution guard15min, disk5GiB/free6GiB. >250ms scheduling delay in the
forced50ms window invalidates the observation. No result-driven rerolls. On
construction/binding failure preserve INVALID and identify a bounded repair;
do not launch a broader campaign. Keep all27 compact rows/events/source hashes,
replay/checksum and this plan, delete downloads/excerpts/cache/binary/worktree.
Success establishes a localized remedy for the controlled mechanism only.
Original natural PREPARE attribution and product acceptance remain open.
