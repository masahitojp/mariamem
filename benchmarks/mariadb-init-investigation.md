# MariaDB initialization and memory attribution: Step 1

This completes Step 1 of the [architecture review](fast-architecture-review.md),
using [measurement run 36256194463](https://github.com/masahitojp/mariamem/actions/runs/36256194463).
It records evidence, not an optimization or an architecture choice. Raw artifacts
remain ignored under `benchmarks/results/init-analysis-36256194463/`.

## Evidence and interpretation

**Measured source:** `16a18585be6cc0478cc484a450f944613152ae58`.
Both platforms consumed the same Linux-built WASM, SHA256
`f73ead9ef213a4a47e4e47e534c95e2304d5a20f0c9b8ea7873548bbe0667528`
(18,794,140 bytes), WASIXCC v0.4.7, and Wasmer 7.4.2, with target-specific AOT.
Ubuntu uses the SSE2 + SSSE3 baseline.

| Environment | Recorded configuration |
| --- | --- |
| macOS | 15.7.9, arm64, 3 reported CPUs |
| Ubuntu | 24.04.5, x86_64, kernel 6.17.0-1022-azure, glibc 2.39, 4 reported CPUs |
| Toolchain / guest | Go 1.26.8; report Python 3.14.7; MariaDB 13.1.0-embedded |
| Trials | 2 warmups, 20 measured batches per case; ×1/4/8 gives 20/80/160 per-DB samples |
| Fixtures | One table, 32-character payload, 1,000 or 100,000 rows; first SQL is `COUNT(*)` |

**Verification:** downloaded ZIP SHA256 matched GitHub artifact digests:

- macOS: `b6f78c60798798ced30092f93d462c504afb3e3ab9bb7be9a0216254385329f1`
- Ubuntu: `fcf9c5d4479adcb07826e132ed51be1bf0795c6d2e89f8f4933a1aa3697751f2`
- Common guest: `08dd99e468fa2a1c36ec8a67292cb5e545c8bb804e86c06b9fe5ab64482eccb1`

Extracted files matched ZIP members. All four reports per platform completed,
shared their native identity, and named the same source commit. Recomputed
initialization summaries matched saved summaries. Guest records were monotonic
and complete, with no dropped records. WASM bytes and recorded prepared-source,
toolchain and provenance hashes were verified; AOT provenance and native
manifest identities matched across records. Reapplying the existing hooks to
pinned engine source reproduced the recorded modified-file hashes. The AOT
binary itself is not included in the measurement artifact: its recorded hash
was cross-checked, not independently rehashed from these downloads.

Unless specified otherwise, tables show **p50 / p95 milliseconds**, for the
1,000-row diagnostic condition. Nested scopes and percentile values are not
additive. Per-DB observations within a batch are correlated. These hosted
machines are different: absolute cross-platform latency is not a hardware-
controlled comparison.

## What is inside `mysql_server_init()`?

**Source fact:** `libmysqld/lib_sql.cc` enters `init_embedded_server()`, which
includes `sql/mysqld.cc` and calls `init_server_components()` / `plugin_init()`.
InnoDB's `innodb_init()` calls `srv_start()`. Hooks in
[`guest_init_hooks.py`](../scripts/guest_init_hooks.py) mark real source
boundaries; [`init_diagnostics.inc`](../guest/init_diagnostics.inc) records clocks,
allocation balances and direct file calls.

**Important correction:** `innodb_start_complete` means `srv_start()` returned,
not that all InnoDB/plugin initialization finished. The interval from that
marker to `plugins_complete` includes remaining `innodb_init()` work **and other
plugin initialization**. Deriving this interval from adjacent recorded markers
reveals the dominant cost. Calling the entire old embedded-init bucket
“InnoDB startup” would incorrectly attribute it.

### macOS: measured subdivisions

| Stage | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| InnoDB options | 0.04 / 0.06 | 0.04 / 0.11 | 0.05 / 0.17 |
| InnoDB runtime before buffer pool | 0.51 / 0.78 | 0.58 / 4.70 | 0.73 / 24.28 |
| all plugins | 684.93 / 1490.48 | 971.19 / 1838.20 | 1726.77 / 3310.44 |
| buffer pool creation | 1.86 / 2.58 | 2.73 / 33.16 | 13.59 / 76.64 |
| complete embedded initialization | 695.37 / 1501.60 | 1012.95 / 1937.56 | 1845.44 / 3458.76 |
| doublewrite/undo/transaction setup | 3.74 / 5.45 | 3.96 / 10.41 | 7.40 / 34.50 |
| embedded options | 6.32 / 8.64 | 14.79 / 59.54 | 80.64 / 221.83 |
| global components before plugins | 5.22 / 7.34 | 6.22 / 25.93 | 9.98 / 76.96 |
| log/lock/page-cleaner setup | 3.69 / 5.07 | 3.70 / 7.41 | 4.31 / 23.04 |
| metadata/temp tablespace/background setup | 18.77 / 21.89 | 44.99 / 98.13 | 91.37 / 221.21 |
| post-plugin components/DDL | 0.21 / 0.25 | 0.21 / 0.51 | 0.26 / 0.57 |
| remaining InnoDB startup | 3.40 / 26.32 | 18.29 / 32.80 | 18.04 / 39.61 |
| remaining embedded setup | 0.41 / 0.56 | 0.41 / 1.06 | 0.52 / 4.38 |
| tablespaces/log/recovery/dictionary | 5.19 / 7.27 | 9.76 / 39.13 | 29.35 / 103.36 |

### Ubuntu: measured subdivisions

| Stage | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| InnoDB options | 0.02 / 0.02 | 0.03 / 0.10 | 0.04 / 0.29 |
| InnoDB runtime before buffer pool | 1.42 / 1.49 | 1.91 / 4.02 | 2.29 / 7.77 |
| all plugins | 683.31 / 1142.19 | 1234.28 / 2029.16 | 2267.78 / 3675.32 |
| buffer pool creation | 3.11 / 3.29 | 4.25 / 8.82 | 9.20 / 17.54 |
| complete embedded initialization | 704.92 / 1164.70 | 1267.77 / 2069.33 | 2344.41 / 3746.80 |
| doublewrite/undo/transaction setup | 5.18 / 5.40 | 10.43 / 18.45 | 20.43 / 33.82 |
| embedded options | 14.21 / 16.15 | 22.15 / 38.23 | 44.14 / 60.33 |
| global components before plugins | 6.95 / 7.37 | 12.16 / 20.83 | 23.80 / 35.67 |
| log/lock/page-cleaner setup | 5.22 / 5.40 | 9.77 / 19.25 | 20.04 / 30.15 |
| metadata/temp tablespace/background setup | 11.50 / 15.77 | 28.83 / 48.91 | 50.95 / 79.39 |
| post-plugin components/DDL | 0.22 / 0.27 | 0.26 / 0.38 | 0.35 / 3.32 |
| remaining InnoDB startup | 20.04 / 30.79 | 9.82 / 55.44 | 0.07 / 77.29 |
| remaining embedded setup | 0.43 / 0.50 | 0.49 / 0.58 | 0.50 / 0.65 |
| tablespaces/log/recovery/dictionary | 5.24 / 6.41 | 9.28 / 16.13 | 17.16 / 25.84 |

### Dominant interval and CPU

The following interval is a **derived calculation from recorded markers**,
not an extra timer or a subtraction of separately aggregated medians.

| Platform / scope | ×1 wall | ×4 wall | ×8 wall |
| --- | ---: | ---: | ---: |
| macOS: embedded init | 695.4 / 1501.6 | 1012.9 / 1937.6 | 1845.4 / 3458.8 |
| macOS: post-`srv_start` → plugins complete | 650.4 / 1454.1 | 880.4 / 1749.9 | 1543.7 / 3065.9 |
| Ubuntu: embedded init | 704.9 / 1164.7 | 1267.8 / 2069.3 | 2344.4 / 3746.8 |
| Ubuntu: post-`srv_start` → plugins complete | 635.5 / 1098.3 | 1144.8 / 1895.9 | 2139.8 / 3549.9 |

Median **per-sample** fraction of embedded init in that interval:
macOS 92.35%, 87.40%, 83.68%; Ubuntu 89.61%, 90.24%, 90.71%.
Measured InnoDB options through `srv_start` is only 38 / 96 / 212 ms p50 on
macOS and 52 / 79 / 137 ms on Ubuntu. Buffer creation and recovery/open are
small at ×1; the largest observed InnoDB sub-scope is metadata/temp/background
setup. The post-`srv_start` interval dominates ×1 and grows most in absolute
milliseconds at ×8.

| Platform / interval | ×1 process / current-thread CPU p50 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS embedded init | 706.9 / 673.4 | 716.1 / 672.9 | 693.7 / 646.9 |
| macOS dominant interval | 661.1 / 643.5 | 644.2 / 632.7 | 615.7 / 606.6 |
| Ubuntu embedded init | 718.5 / 661.4 | 1169.9 / 1086.1 | 1210.4 / 1126.2 |
| Ubuntu dominant interval | 647.8 / 628.1 | 1057.9 / 1041.4 | 1106.7 / 1078.6 |

**Measured fact:** ×1 dominant-interval wall and CPU are nearly equal; direct
I/O call time is much smaller. At ×8 wall grows substantially more than CPU,
particularly on macOS. Ubuntu also spends more CPU per DB at higher concurrency.
Process CPU includes all runtime threads; current-thread CPU has no persistent
engine role identifier. CPU can exceed wall. These clocks do not distinguish
zeroing, allocator work, page faults, cache misses or engine computation.

**Inference:** ×1 is primarily observed CPU execution in this plugin interval,
rather than measured file-call waiting. ×8 combines repeated CPU work with
scheduling/resource pressure. Wall-minus-CPU is not a synchronization timer;
there is no direct proof of a particular lock or wait dominating startup.

**Source-supported hypothesis:** MyISAM key cache and Aria page cache default
to the server `KEY_CACHE_SIZE` (128 MiB); current guest options set InnoDB's
16 MiB buffer pool and 2 MiB log buffer but do not override those caches.
`ha_init_key_cache` runs before plugins; Aria's `ha_maria_init()` initializes
page caches, log and recovery. Page-cache code allocates/initializes large
buffers and metadata. This is a concrete candidate for CPU/memory attribution,
not proof that all post-`srv_start` time belongs to Aria.

## File activity

Counters observe successful direct guest POSIX calls through ready preparation,
before first public SQL. This is **logical I/O into Wasmer's memory filesystem**,
not physical disk throughput. Libc-internal buffered I/O, mmap access, failed
calls and exclusive filesystem waiting are not completely captured.

| Platform / per-DB p50 through ready | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS read MiB | 11.363 | 11.098 | 11.098 |
| macOS write MiB | 2.031 | 1.406 | 1.813 |
| macOS summed I/O call ms | 1.893 | 2.413 | 3.672 |
| Ubuntu read MiB | 11.113 | 11.098 | 11.098 |
| Ubuntu write MiB | 2.031 | 2.047 | 2.047 |
| Ubuntu summed I/O call ms | 5.912 | 6.834 | 10.433 |

The tables above retain stage timing; the raw stage counters place roughly
8.5 MiB of reads in tablespaces/log/recovery/dictionary work, and another
roughly 2.6 MiB in the post-`srv_start` plugin interval. Writes of roughly
1–2 MiB can span startup markers as background work proceeds; marker-window
attribution is not exclusive function ownership.

| Major file, ×1 | macOS read MiB | Ubuntu read MiB | Writes / other observations |
| --- | ---: | ---: | --- |
| `ib_logfile0` | 4.012 | 4.012 | No observed writes |
| `ibdata1` | 2.734 | 2.625 | Read-heavy |
| `undo001` | 1.555 | 1.469 | Read-heavy |
| `undo002` | 1.492 | 1.438 | Read-heavy |
| `undo003` | 1.406 | 1.406 | Read-heavy |
| `benchmark_rows.ibd` | 0.156 | 0.156 | Initialization does not scan the whole large fixture |
| `ibtmp1` | 0 | 0 | 2.031 MiB writes |
| `aria_log*` | ~0.008 | ~0.008 | Small observed reads |
| `ddl_recovery.log` | negligible | negligible | One open, one truncate, nine-byte write |

There is one observed truncate per DB. **Unknown:** truncate/open timing by
stage; only final per-file counts exist. Large-fixture read totals stay about
10.6–12.2 MiB and writes about 1.4–2.0 MiB. Observed I/O bytes do not grow with
100× row count or ×8 concurrency in proportion to initialization latency.
This argues against the measured direct file traffic explaining the dominant
interval, but does not rule out memory-filesystem allocation/copy work.

## Memory attribution and ready threads

**Measured fact:** first guest marker reports 256.0625 MiB linear capacity.
Ready capacity is much larger, commonly 626–658 MiB, sometimes 674 MiB.
Capacity is not resident memory. The 16 MiB buffer pool cannot explain either
this capacity or observed RSS alone.

| Guest observation, per-DB p50 | macOS ×1 / ×4 / ×8 | Ubuntu ×1 / ×4 / ×8 |
| --- | --- | --- |
| Ready linear capacity MiB | 625.94 / 658 / 658 | 642 / 625.94 / 625.94 |
| Wrapped C allocation balance MiB | 107.49 / 139.53 / 139.53 | 123.52 / 107.49 / 107.49 |
| Wrapped mapping balance MiB | 242.24 / 242.24 / 242.24 | 242.24 / 242.24 / 242.24 |
| Successful guest pthread creates | 7 / 11 / 11 | 9 / 7 / 7 |
| Sampled runtime group peak RSS MiB | 338.9 / 1368.7 / 2462.0 | 403.1 / 1602.8 / 3208.6 |

**Derived allocation deltas:** buffer-pool creation adds about 17.79 MiB of
wrapped C balance while taking only 2–4 ms at ×1. Wrapped mapping balance is
112.08 MiB before plugins, 116.08 MiB after InnoDB startup, then rises by
126.16 MiB in the dominant plugin interval to 242.24 MiB. These are observed
allocation/mapping lengths, not disjoint physical-memory owners. WASIX guest
mappings can live inside linear memory; do not add them to linear capacity/RSS.
Unwrapped allocation, fragmentation and Rust VFS buffers remain outside this
C balance. The cache hypothesis is consistent with these deltas but not proven.

OS captures are **one ready batch per case**, not 20-trial memory distributions.
They happen after first SQL, a hold and sampling; macOS capture costs about
1.2 seconds per DB, versus roughly 8–10 ms on Ubuntu. Later DBs can have older
background state. Capture affects lifecycle duration and retained runner memory,
not measured first-SQL latency. Keep this distinct from sampled peak RSS.

| Ubuntu ready per-DB median, first batch, MiB | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| RSS | 402.0 | 398.9 | 399.4 |
| PSS | 399.2 | 337.0 | 327.6 |
| Private dirty | 301.5 | 298.8 | 299.5 |
| Private clean | 97.5 | 18.0 | 18.0 |
| Anonymous PSS | 319.5 | 316.8 | 317.5 |
| File PSS | 79.7 | 20.1 | 10.1 |

AOT file mapping is 65.79 MiB resident; its per-DB PSS falls from 65.79 to
16.45 to 8.22 MiB as DBs share it. RSS therefore overcounts shared pages.
An anonymous executable mapping is about 21.11 MiB; ownership is not fully
resolved. A 128 MiB anonymous reservation has about 96 MiB resident; a separate
~626–643 MiB anonymous mapping has ~82–90 MiB resident. **Hypotheses:** the first
may reflect the 96 MiB redo file's runtime storage, the second linear memory.
Without address/owner correlation these are not established allocations.

macOS ×1 `vmmap` reports physical footprint 239.6 MiB, total category resident
543.8 MiB and dirty 239.7 MiB. Those accounting categories are not the sampled
339 MiB RSS. Malloc categories include large 86.2 MiB, reusable-large 26.3 MiB,
medium 50.2 MiB; `VM_ALLOCATE` has 96.5 MiB resident in 7.9 GiB virtual space.
Stack residency is only about 0.6 MiB despite 40.5 MiB virtual reservation.
At ×8 captured swapped totals are 5.5–133.4 MiB per DB and footprint remains
242.6–266.0 MiB. This supports a memory-pressure hypothesis, not attribution of
particular startup delays to paging: captures occur after readiness.

| Ready OS threads, first 1,000-row batch | ×1 | ×4 range | ×8 range |
| --- | ---: | ---: | ---: |
| macOS (`ps -M`, header excluded) | 17 | 20–21 | 18–21 |
| Ubuntu (`/proc`) | 21 | 19–23 | 19–25 |

Ubuntu ×1 has 11 `TokioTaskManage`, eight `tokio-rt-worker`, two
`wasmer-headless` names; 18 threads wait in futex, two in epoll and one in pipe
read at capture. Runtime names do not identify live MariaDB thread roles, and
ready waits do not prove initialization waits. Guest creation counts range
7–13 and differ from OS thread counts. Source roles include timer, InnoDB
AIO/thread pool, page cleaner, monitor/master, dictionary statistics/buffer-load,
FTS where started, and lazily created SQL slot workers.

**Continuation implication:** initialized state includes multiple guest and
runtime threads, locks/conditions, timers, scheduler state and file handles.
An idle SQL endpoint is not a quiescence proof. Copying linear memory alone
cannot be presumed sufficient; these observations neither prove nor disprove
safe initialized-state continuation.

## Fixture-size sensitivity

Snapshot inventory grows from 138.17 to 152.02 MiB; the table file grows from
0.156 to 14 MiB. Fixed files include 96 MiB redo, 12 MiB `ibdata1`, and three
10 MiB undo files. Thus 100× rows means only ~10% more total prepared bytes.

| Platform / p50: 1,000 → 100,000 rows | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS per-DB Fork → SQL ms | 1081.9 → 1390.7 | 1619.5 → 1807.4 | 3196.8 → 3972.8 |
| macOS embedded init ms | 695.4 → 747.2 | 1012.9 → 1049.2 | 1845.4 → 2274.1 |
| macOS dominant plugin interval ms | 650.4 → 679.4 | 880.4 → 892.5 | 1543.7 → 1881.9 |
| macOS restore ms | 108.3 → 187.8 | 146.1 → 198.4 | 293.0 → 562.5 |
| Ubuntu per-DB Fork → SQL ms | 1258.4 → 1160.1 | 1895.4 → 1971.5 | 3632.4 → 4138.1 |
| Ubuntu embedded init ms | 704.9 → 546.4 | 1267.8 → 1199.5 | 2344.4 → 2574.5 |
| Ubuntu dominant plugin interval ms | 635.5 → 475.5 | 1144.8 → 1090.8 | 2139.8 → 2399.6 |
| Ubuntu restore ms | 234.4 → 250.9 | 291.4 → 321.4 | 490.1 → 562.1 |

**Inference:** there is no consistent monotonic fixture effect on the dominant
initialization interval; fixed work and run variance remain important. Restore
increases, particularly on macOS. First `COUNT(*)` is also data-sensitive and
must not be attributed to init. This experiment does not test many-table metadata.
Snapshot p50 rises 690 → 938 ms on macOS and 678 → 749 ms on Ubuntu.

Large-fixture group peak RSS is 359 / 1443 / 2779 MiB on macOS and
437 / 1755 / 3507 MiB on Ubuntu. Ubuntu ready private dirty rises ~38 MiB per
DB (to ~336–338 MiB), more than the ~14 MiB file increment. **Hypothesis:**
runtime storage capacity/copies and query buffers contribute; there is no
allocation-stack proof. Large-fixture ready OS threads are 20–22 on macOS and
25–32 on Ubuntu. Background state/capture age confounds direct fixture ownership.

## Instrumentation perturbation

Conditions ran in blocks: control, diagnostics 1,000, diagnostics 100,000,
validation reuse. They were not interleaved or randomized.

| Batch Fork wall p50/p95 ms: control → diagnostics | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS | 1438.5/2632.0 → 1081.9/1868.3 | 2143.7/3254.2 → 2096.4/2910.3 | 4588.2/5485.4 → 4097.2/5302.8 |
| Ubuntu | 1137.8/1851.3 → 1258.4/1709.3 | 2432.7/2961.2 → 2413.2/3630.7 | 4183.8/5414.9 → 4452.6/5671.4 |

Observed p50 differences are macOS −24.8%, −2.2%, −10.7%; Ubuntu +10.6%,
−0.8%, +6.4%. **Unknown:** causal instrumentation overhead. Negative differences
cannot demonstrate speedup or negligible overhead; macOS control restore is
~329 ms versus diagnostic ~108 ms at ×1, while init is ~689 versus ~695 ms.
Ubuntu init is ~588 versus ~705 ms. Warm filesystem/cache, scheduling and order
confound the comparison. Counter wrappers themselves contribute measured CPU;
post-ready OS diagnostics add separate capture cost. An interleaved control is
needed to bound true perturbation if decisions depend on small differences.

## Within-call validation reuse

The probe changes only a disposable source copy and verified private read-only
bundle. It carries an already verified AOT digest through sidecar and host
startup in the same call, skipping **two redundant AOT hashes**. Initial
artifact/runtime/sidecar validation and snapshot inventory checks remain.
No production optimization, path cache or integrity weakening was shipped.

| Host metadata/snapshot validation p50/p95 ms: control → reuse | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS | 164.7/337.2 → 100.7/117.9 | 201.0/359.9 → 154.9/240.1 | 464.0/843.6 → 350.4/727.2 |
| Ubuntu | 153.8/154.5 → 104.3/104.7 | 172.2/191.5 → 117.0/129.3 | 355.2/447.5 → 244.7/334.4 |

Public preparation outside the host startup timer also decreases. Combining
that interval with host validation **per sample before aggregating** gives:

| Combined preparation p50/p95 ms: control → reuse | ×1 | ×4 | ×8 |
| --- | ---: | ---: | ---: |
| macOS | 303.3/528.1 → 171.6/203.4 | 386.4/574.2 → 271.2/412.3 | 775.1/1233.2 → 575.0/1046.0 |
| Ubuntu | 267.7/268.9 → 169.4/169.8 | 301.3/323.4 → 189.8/201.4 | 605.0/720.3 → 385.6/493.2 |

**Derived observed reduction:** 132/115/200 ms on macOS and 98/112/219 ms on
Ubuntu at ×1/4/8; about 43/30/26% and 37/37/36% of combined preparation.
This quantifies a removable repeated-read candidate, not all validation.
Residual ×1 host validation is ~100 ms, still including snapshot identity work.
The timer is not fine enough to assign every remaining millisecond to hashing.

Whole batch p50 with reuse is macOS 1639/2561/4603 ms and Ubuntu
1067/2230/4104 ms. There is no reliable whole-lifecycle speedup claim: macOS
becomes slower despite reduced validation, and private bundle path/cache plus
blocked execution remain confounders. Reuse is evidence for identity plumbing,
not a production decision or an estimate of caching all snapshot validation.

## Answers and remaining blind spots

1. **Dominant cause:** observed CPU-heavy plugin initialization after
   `srv_start`, with substantial allocation/mapping growth. Allocation versus
   other plugin computation is still unresolved; measured file-call waiting is
   too small to explain ×1. InnoDB buffer/recovery is not the dominant bucket.
2. **Fixture size:** dominant init does not increase consistently; restore and
   private memory do. This fixture varies bytes/rows, not metadata complexity.
3. **×1 → ×8:** dominant plugin wall growth accounts for the largest measured
   increase; constrained CPUs and memory pressure are supported explanations,
   but lock waits, page faults and bandwidth are not directly attributed.
4. **Validation:** two repeated AOT reads account for the observed ~98–132 ms
   combined-preparation difference at ×1 and ~200–219 ms at ×8. Required snapshot
   checks and other work remain; exact causal end-to-end savings are unknown.
5. **Memory:** initial 256 MiB is capacity, not an RSS explanation. Capacity
   grows past 600 MiB; large C/mapping balances, anonymous/private pages and
   shared AOT pages are distinct. Runtime VFS versus linear heap ownership
   needs address correlation; neither buffer pool nor stacks explains all RSS.
6. **Continuation:** ready state has active runtime/engine thread machinery.
   A continuation probe must first establish a bounded quiescent point and
   inventory resumable synchronization/resources, not assume a heap copy works.

Remaining blind spots: individual plugins inside the dominant interval;
allocation stacks and memory addresses; physical/page-fault activity; exclusive
wait/lock time; unwrapped I/O; stage-local open/truncate timing; ready capture
age and single-batch sampling; causal control/reuse overhead. Sampled process
CPU is coarse on Ubuntu (whole-second `ps` values can be zero); guest clock
observations are the stronger stage CPU evidence. RSS is not unique memory.

## Implications for the next probes

- Split only the dominant post-`srv_start` plugin interval, particularly Aria
  cache allocation/initialization versus recovery and remaining InnoDB work.
  Record allocation growth and current-thread CPU at those boundaries. This
  distinguishes cold-cache/memory work from other engine work before a broad
  initialization or continuation experiment.
- Correlate guest linear-memory address ranges with OS maps and runtime VFS
  backing allocations, especially the 96 MiB redo file. Establish private versus
  shareable memory ownership before choosing storage/runtime sharing.
- If quantifying a small improvement, interleave diagnostics-off/on and reuse
  controls on the same platform with unchanged private-bundle handling. Keep
  required integrity checks intact and measure validation separately from init.
- Before initialized-state continuation, inventory quiescence obligations for
  guest threads, Rust scheduler, timers, locks and handles. A narrowly bounded
  feasibility probe is justified; selecting checkpointing, CoW, VFS or an
  embedded runtime is not yet justified by this evidence.
