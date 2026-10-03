# v0.4 Snapshot / Fork memory ownership and lifetime

Historical reference preserved. The accepted FD/cold-copy integration and new
canonical comparison are in [v04-integrated-candidate.md](v04-integrated-candidate.md).
Original observations and the OS-accounting attribution below are unchanged.


Source: `d94934a2d6fb79730297c0bbb80af79ffd04d0d4` (canonical baseline HEAD), `v0.4/generated-go-integration`. Production runtime is unchanged. Diagnostic tooling is isolated in [memorylifetime](memorylifetime/README.md).

Apple M1, 16 GiB, macOS 27.0.1 (26A434), arm64, Go 1.26.8. Canonical compiled guest SHA-256: `5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`. [Checkpoint values / raw evidence hashes](v04-snapshot-memory-lifetime-values.json).

## Conclusions

- **A — prepared G(0):** the Snapshot handle owns an approximately 138.18 MiB filesystem snapshot on disk, not a 1.1 GiB live Go representation. GC with that handle retained reduces HeapAlloc from 3121.3 MiB to 0.37 MiB. MemFS copying/growth and export create allocation churn; stale anonymous pages remain OS-accounted after collection.
- **B — Fork Close:** in the two ×16 controls without vmmap, GC with every closed Database handle still explicitly retained reduces HeapAlloc from approximately 32969 MiB to 0.6 MiB. No large guest/FS backing survives as a reachable Go object in these runs. `FreeOSMemory` increases HeapReleased to approximately 33851–33855 MiB, but physical footprint remains approximately 7993–8098 MiB.
- The canonical ~4 GiB post-Close number is a real process-footprint observation, **not a demonstrated 4 GiB live guest leak**. The diagnostic runs are deliberately different scheduling/profile boundaries and produce larger footprints; they do not replace the canonical numbers.
- There is a separate small concrete retention: a held closed Database owns one remaining host pipe FD. Its object path is documented below. It does not explain the GiB-scale memory.

## Experiment and checkpoint definitions

Every trial starts a fresh OS process. Controls run sequentially, not concurrently with another trial. Default Go GC policy, normal MariaDB configuration, public Options{}, the same 1,000-row `benchmark_rows` InnoDB fixture and COUNT assertion are used. GC/FreeOSMemory exist only in the diagnostic harness. No production behavior or architecture is changed.

Two primary trials each: fresh-2/3, snapshot-2/3, and forks{1,4,8,16}-2/3, without vmmap. Extra mapping/profile runs are explicitly separate: early fresh-1/snapshot-1/forks1-1, snapshot-4-map, forks16-4-map, fresh-4-map. Two pure-Go heap controls contain no MariaDB/WASIX. `runtime.MemProfileRate=64 KiB` is diagnostic and affects GC scheduling. `-live-gc` is used only in separate fresh5-live and extra ×16 runs, to make the live profile current while children remain alive.

Fresh: baseline → ready → first SQL/disconnect ack → Close with handle retained → GC → FreeOSMemory → release handle → GC → FreeOSMemory.
Snapshot: baseline → base ready → fixture/disconnect ack → Snapshot API returned → source Close → release source (G(0), only Snapshot handle) → GC → FreeOSMemory → Snapshot.Close plus nil handle → GC → FreeOSMemory.
Fork/scaling: same preparation → G(0) → simultaneous children and fixture COUNT/disconnect ack → sequential normal Close of all children → GC/FreeOSMemory with closed handles retained → release child handles → GC/FreeOSMemory → release Snapshot → GC/FreeOSMemory.

**Combined internal boundary:** the public Snapshot call returns after guest export, worker join, transfer export, publication, validation and consuming source shutdown. Separate live checkpoints inside those private phases are not available without a hook. `snapshot_published_source_handle_retained` means all those phases completed; `source_close` is then the idempotent public Close. No invented export-only/publish-only live checkpoint is reported. Existing timing traces still mark those phases.

Numeric counters are sampled in order: MemStats → existing canonical process_cost helper → lsof. Profiles and optional VM views follow; these are not simultaneous samples. FD counts include two short-lived lsof capture pipes consistently. Goroutines exclude the external helpers. Large object reachability is judged from forced-GC HeapAlloc plus current inuse profiles, not footprint or a pre-GC profile.

## Checkpoint tables

All byte columns below are MiB. Representative primary trial 2 is shown in full for fresh/Snapshot/×16. All checkpoints, HeapObjects, StackInuse, GC/scavenger counters and raw hashes for every trial are preserved in the JSON. Sys/HeapReleased are runtime span/accounting counters, not resident-byte measurements.

### fresh-2

| Checkpoint | physical | RSS | HeapAlloc | HeapInuse | HeapIdle | HeapReleased | Sys | goroutines | FDs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 5.08 | 12.03 | 0.26 | 0.98 | 2.73 | 2.70 | 8.02 | 1 | 6 |
| ready | 91.25 | 117.20 | 2198.88 | 2200.18 | 11.16 | 10.36 | 2219.91 | 23 | 11 |
| first_sql_disconnected | 91.97 | 119.81 | 2200.44 | 2201.87 | 9.45 | 8.88 | 2219.91 | 24 | 11 |
| closed_handle_retained | 92.89 | 121.52 | 2201.96 | 2203.38 | 8.18 | 7.37 | 2219.91 | 1 | 7 |
| closed_handle_retained_gc | 93.63 | 122.27 | 0.35 | 1.36 | 2210.20 | 6.26 | 2220.23 | 1 | 7 |
| closed_handle_retained_free | 91.39 | 123.16 | 0.33 | 1.30 | 2210.27 | 2209.93 | 2220.25 | 1 | 7 |
| handle_released_gc | 92.99 | 123.61 | 0.33 | 1.25 | 2210.25 | 2208.14 | 2220.25 | 1 | 6 |
| handle_released_free | 91.69 | 123.72 | 0.33 | 1.24 | 2210.26 | 2209.93 | 2220.25 | 1 | 6 |

### snapshot-2

| Checkpoint | physical | RSS | HeapAlloc | HeapInuse | HeapIdle | HeapReleased | Sys | goroutines | FDs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 4.73 | 11.72 | 0.26 | 0.77 | 2.98 | 2.95 | 7.77 | 1 | 6 |
| base_ready | 90.83 | 116.94 | 2198.82 | 2199.89 | 11.52 | 10.48 | 2220.19 | 21 | 11 |
| fixture_disconnected | 92.86 | 123.09 | 2201.53 | 2202.98 | 8.36 | 7.86 | 2220.19 | 22 | 11 |
| snapshot_published_source_handle_retained | 1116.64 | 1017.16 | 3117.92 | 3119.56 | 4.03 | 3.45 | 3133.12 | 1 | 7 |
| source_close | 1117.41 | 1017.98 | 3119.62 | 3121.02 | 2.57 | 2.14 | 3133.12 | 1 | 7 |
| G0_only_snapshot | 1118.28 | 1018.86 | 3121.32 | 3122.63 | 4.96 | 4.50 | 3137.12 | 1 | 7 |
| snapshot_retained_gc | 1119.27 | 1020.02 | 0.37 | 1.29 | 3126.27 | 2.74 | 3137.19 | 1 | 6 |
| snapshot_retained_free | 1089.95 | 1021.17 | 0.33 | 1.16 | 3126.38 | 3126.02 | 3137.21 | 1 | 6 |
| snapshot_released | 1090.67 | 1021.27 | 2.07 | 3.06 | 3124.44 | 3124.16 | 3137.21 | 1 | 6 |
| released_gc | 1091.78 | 1022.50 | 0.33 | 1.14 | 3126.36 | 3122.58 | 3137.21 | 1 | 6 |
| released_free | 1091.16 | 1022.53 | 0.34 | 1.15 | 3126.32 | 3125.95 | 3137.21 | 1 | 6 |

### forks16-2

| Checkpoint | physical | RSS | HeapAlloc | HeapInuse | HeapIdle | HeapReleased | Sys | goroutines | FDs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 4.75 | 11.70 | 0.26 | 0.77 | 2.98 | 2.95 | 7.77 | 1 | 6 |
| base_ready | 90.78 | 117.00 | 2198.81 | 2199.77 | 11.73 | 10.46 | 2219.59 | 19 | 11 |
| fixture_disconnected | 93.31 | 123.75 | 2201.53 | 2202.85 | 8.52 | 7.59 | 2219.84 | 20 | 11 |
| snapshot_published_source_handle_retained | 1125.99 | 1156.80 | 3117.90 | 3119.23 | 4.36 | 3.58 | 3132.77 | 1 | 7 |
| source_close | 1126.72 | 1157.56 | 3119.62 | 3120.92 | 6.67 | 6.06 | 3137.02 | 1 | 7 |
| G0_only_snapshot | 1127.31 | 1158.16 | 3121.33 | 3122.61 | 4.98 | 4.70 | 3137.02 | 1 | 7 |
| all_ready | 8243.09 | 2263.95 | 32967.09 | 32969.61 | 883.80 | 2.45 | 33898.76 | 225 | 86 |
| all_closed_handles_retained | 8243.16 | 2136.94 | 32969.29 | 32971.87 | 882.70 | 2.45 | 33898.76 | 1 | 22 |
| closed_handles_retained_gc | 8243.35 | 2124.08 | 0.60 | 2.41 | 33852.18 | 2.45 | 33898.76 | 1 | 22 |
| closed_handles_retained_free | 7992.65 | 2124.86 | 0.57 | 2.23 | 33852.34 | 33850.74 | 33898.76 | 1 | 22 |
| closed_handles_released_gc | 7992.90 | 2103.69 | 0.54 | 1.70 | 33852.89 | 33848.95 | 33898.76 | 1 | 6 |
| closed_handles_released_free | 7991.60 | 2103.69 | 0.54 | 1.62 | 33852.94 | 33852.08 | 33898.76 | 1 | 6 |
| snapshot_released | 7992.31 | 2103.80 | 2.53 | 3.92 | 33850.64 | 33849.92 | 33898.76 | 1 | 6 |
| released_gc | 7993.06 | 2104.58 | 0.53 | 1.61 | 33852.98 | 33849.36 | 33898.76 | 1 | 6 |
| released_free | 7992.32 | 2104.59 | 0.54 | 1.62 | 33852.95 | 33851.95 | 33898.76 | 1 | 6 |

### Scaling replication — physical footprint ranges across primary trials 2/3

| Children | G(0) | ready | all Close | after GC | after FreeOSMemory | Snapshot released + GC/Free | HeapAlloc after GC |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 1127.3–1127.3 | 1214.9–1215.0 | 1215.2–1215.3 | 1214.2–1215.6 | 1205.2–1209.7 | 1205.0–1209.9 | 0.34–0.35 |
| 4 | 1127.2–1127.3 | 5413.4–7271.6 | 5415.3–7272.0 | 5406.2–7272.6 | 5333.3–7162.5 | 5332.5–7161.9 | 0.39–0.40 |
| 8 | 1126.8–1127.4 | 5627.9–5784.4 | 5628.4–5786.5 | 5626.4–5788.0 | 5513.8–5655.7 | 5513.8–5656.6 | 0.46–0.47 |
| 16 | 1126.8–1127.3 | 8243.0–8243.1 | 8243.0–8243.2 | 8243.1–8243.4 | 7992.6–8098.1 | 7992.3–8097.9 | 0.60–0.63 |

## Heap and allocation ownership

Forced-GC fresh/Snapshot/closed ×16 profiles contain only sub-MiB runtime, encoding/json, environment, SQL-driver and harness bookkeeping. No sampled 2 GiB module backing or large MemFS allocation survives. Alloc/inuse profiles before GC can lag the current GC epoch; they are not reliable standalone proofs of reachability. An extra fresh-ready GC profile shows 2048 MiB constructor backing plus approximately 150 MiB live MemFS storage. An extra GC with live children produces the current ×16 profile: **32 GiB NewWithWASIReserve (99.42%) + ~0.19 GiB resizeMemData (0.58%)**. After Close + GC that same guest backing disappears.

| Owner / allocation path | Evidence / approximate size | Lifetime |
| --- | --- | --- |
| `generated.NewWithWASIReserve → Module.Memory` | `make([]byte, 2147483648)` per DB, 2 GiB; shared-memory maximum reserved upfront, initial logical size 256 MiB | Fresh/child instance until execution goroutine and workers finish; collected after normal Close + GC |
| `MemFS.root → memNode.data → resizeMemData` | Snapshot alloc_space: ~0.90 GiB cumulative (source tree and successive export-tree capacities); live 16 children: ~0.19 GiB total private heap files beyond prepared mappings | MemFS owned only by instance host/WASI; old growth buffers become garbage; whole tree collectible on execution completion |
| `exportTransfer.walk → make([]byte, st.Size())` | ~138.18 MiB cumulative full-file temporary reads | Local recursive walk only; not stored in Snapshot or host |
| `snapshot.Publish` | filesystem copy via `io.Copy` between OS files, streamed Inventory hashing; small manifest/maps | Published snapshot is disk storage; no large serialized representation retained |
| `MapPreparedFiles → PreparedFiles.mappings` | ~138.18 MiB virtual file mappings per child, MAP_PRIVATE; logical FD/tree/offset state private | Descriptors closed and mapping slices munmapped after guest worker join; not Go heap file contents unless grown into private heap storage |
| tables / ThreadPool / TLS / host / benchmark | Small relative to backing buffers; post-GC total heap <1 MiB | Per-module/thread objects; no global instance registry discovered |

No consumer option in these controls captures a source DB. Snapshot options can retain user-supplied writer objects in general, but Options{} does not create that cycle.

Code evidence: [Snapshot handle](../snapshot.go), [instance ownership](../internal/generatedgo/runtime_instance.go), [host Close/export](../internal/host/server.go), [linked completion](../internal/guest/linked.go), [guest stop/pipe lifetime](../internal/guest/guest.go), [MemFS growth](../internal/generatedgo/code/base/memfs_growth.go), [prepared mappings](../internal/generatedgo/code/base/prepared_files.go), [cold-copy loop](../guest/snapshot_fs.inc), [publication](../internal/snapshot/snapshot.go).

## Snapshot ownership audit / G(0)

`Snapshot{path, temporary, opts, mutex, close state}` has no source Database, Server, MemFS, module, thread or callback field. Fork reads path/options; no parent→child retained registry. On successful Snapshot the consumed Database still holds its Server while the caller retains it, but the execution goroutine has finished; that Server has no Module/Memory field.

Cold guest `snapshot_copy` keeps original `/mariadb` files and separately creates `/snapshot-out/data` in the same private MemFS after MariaDB shutdown. It copies through a 64 KiB guest buffer. Successive `memFile.Write → resizeMemData` allocations copy old byte arrays and retire them. Export then allocates one additional whole-file buffer to write the transfer tree. Publication copies that disk tree to the final snapshot and removes transfer storage. Thus files are copied more than once during preparation, but these memory copies are **not retained by the published Snapshot**.

Published logical files total **138.18 MiB**: redo `ib_logfile0` 96 MiB, `ibdata1` 12 MiB, three undo files 10 MiB each, fixture `.ibd` ~160 KiB and small metadata. Manifest is 2173 bytes. Releasing Snapshot removes owned disk files; it does not materially lower the already-collected process heap or OS footprint.

Large monotonically growing MemFS files use 25% growth after 1 MiB; truncate can retain a larger capacity. A static replay of the actual 64 KiB export-copy sequence and current growth rule for these logical sizes gives ~158.16 MiB final export-tree capacity but ~774.63 MiB cumulative allocations. Redo alone is ~108.42 MiB final capacity / ~539.04 MiB cumulative. This is a size/growth model, not a direct live-tree capacity census; stdio batching, truncation and allocator rounding can differ. The independent alloc profile confirms ~0.90 GiB total resize allocations including source state.

G(0) has no live execution, but before explicit collection the runtime still accounts for dead backing and growth/export buffers (~3121 MiB HeapAlloc). After GC with Snapshot retained that is ~0.36 MiB. The 1.1 GiB physical history is therefore not an immutable 1.1 GiB prepared object graph.

## Fork Close / shortest retained references

`StartInstance` creates local WASI, MemFS, host and module; `ThreadLaunch` child modules share only that instance memory/ThreadPool. `SpikeWait` joins worker goroutines; deferred `CloseDescriptors` clears fdTable and `PreparedFiles.Close` munmaps prepared views. The completion channel carries an error, not a module. The linked completion goroutine exits after joining reader and closing child pipes. Module/FS state is not saved in Process or Snapshot.

Normal Close brings goroutines from >200 at ×16 ready to **1**, even while closed handles are retained. GC with those handles alive reduces HeapAlloc by >99.99%; holding them does not retain linear memory. No public instance/ThreadPool count API exists; the per-module bookkeeping is private. Goroutine counts are not presented as an exact registry census. No large retained registry, worker queue, timer, context callback or MemFS path is supported by the profiles/audit in this scope.

**Small FD finding:** `Database.server → host.Server.Guest → guest.Process.out → *os.File` remains reachable when the caller retains a closed Database. Normal `Process.stop` closes `in`, not `out`; `Abort` closes both. Source/child execution closes the opposite child pipe endpoints, not this reader. lsof identifies an additional pipe; fresh baseline/held closed/released+GC counts are **6 / 7 / 6**. ×16 held/released counts are **22 / 6**. This depends on os.File collection for that reader after handle release; it is a concrete bounded descriptor-lifetime issue, not the GiB footprint explanation. No production fix was applied.

## OS accounting, GC and allocator controls

Case 4 is confirmed: Go live heap disappears while anonymous-page footprint largely remains. HeapIdle rises after GC; FreeOSMemory moves almost all idle spans into HeapReleased, while Sys remains a virtual reservation high-water mark. This is not proof that the kernel actually discarded every dirty/compressed page or that those bytes are physically resident.

Go heap arenas themselves are anonymous mmap allocations; this control does not introduce any separate application mapping. Go 1.26.8 Darwin `sysUnusedOS` calls `madvise(MADV_FREE_REUSABLE)`; `sysUsedOS` calls `MADV_FREE_REUSE`. The local runtime ignores the madvise return value. The runtime counter is not an independent kernel residency/reclaimability test. [Go runtime source](https://go.dev/src/runtime/mem_darwin.go). An upstream report describes incomplete Darwin reclaimability after this advice ([Go #47656](https://github.com/golang/go/issues/47656)); this is context, **not proof of the identical kernel cause or a proposed workaround**.

Extra mapping run after ×16 Close + GC + FreeOSMemory: ~9.9 GiB physical, ~1.3 GiB writable resident, ~8.6 GiB swapped/compressed; `Untagged` dominates (~19.3 GiB virtual, 1.3 GiB resident, 8.6 GiB swapped). File-backed prepared mappings are absent after Close. The large anonymous regions belong to the Go heap address-space history; code/regular-file mappings and C malloc zones do not explain the bulk. macOS swapped in vmmap includes compressed accounting, not an equal amount of physical RAM or disk swap. No compression ratio is inferred.

Extra fresh footprint view after FreeOSMemory shows ~90 MiB Untagged dirty with only ~1.4 MiB reclaimable, despite sub-MiB live Go heap. This is more than a benign RSS-only page-cache effect; kernel-accounted dirty/compressed anonymous memory remains. We do not claim it is harmless, immediately reclaimable under pressure, or a resolved kernel defect.

### Pure Go control: no MariaDB/WASIX/FS or application mmap

Two independent controls allocate a 2 GiB Go byte slice, touch only 128 MiB, release it, GC/FreeOSMemory, then allocate the same size again and release it. Representative heap-2:

| Checkpoint | physical MiB | HeapAlloc MiB | HeapReleased MiB |
| --- | ---: | ---: | ---: |
| baseline | 4.8 | 0.26 | 2.9 |
| heap_touched | 136.8 | 2048.27 | 5.4 |
| heap_dead_gc | 138.3 | 0.28 | 4.6 |
| heap_dead_free | 138.7 | 0.28 | 2054.7 |
| heap_reused | 2060.1 | 2048.29 | 5.0 |
| heap_reused_dead_gc | 2059.0 | 0.29 | 4.7 |
| heap_reused_dead_free | 2059.2 | 0.29 | 2054.6 |

Untouched reserved bytes initially cost little physical memory. The second allocation must present zeroed memory and allocator reuse can dirty a much larger range than the guest actually touches. Both controls jump to ~2060–2187 MiB physical on the second allocation and retain it after collection. The experiment proves the effect exists without a database or MemFS; it does not isolate every madvise/kernel decision. Large reused linear-memory allocations plus dirty-buffer churn plausibly amplify prepared-child footprint; exact per-span causality was not traced and is not overstated.

## Active per-DB measurement and timing

Current canonical G(n)−G(0) is valid as **whole-process incremental footprint under that exact history**, not an exclusive active DB memory measurement. GC-cleared live heap identifies owned allocations (2 GiB address-stable backing plus small heap files per child), but cannot determine touched physical bytes. RSS omits compressed pages; physical includes dead anonymous-page history. The diagnostic ×16 ready footprint ~8243 MiB (two primary controls) versus canonical ~4283 MiB demonstrates sensitivity to sampling, GC timing, allocator reuse and pressure. No revised canonical metric or claimed per-DB active-byte target is substituted.

Keep historical Snapshot phase medians unchanged: export/shutdown 182.5 ms, publication 255.1 ms, total 528.0 ms; Fork validation 65.8 ms, linked-ready 27.3 ms. Large resize/copy allocations belong to guest cold export and transfer export **before publication**. Publication streams OS files and hashes, so its wall time is not evidence that it retains the large heap. Separate internal live checkpoint hooks and a new timing investigation were not added.

## Exactly one next implementation experiment

Prototype **known-length pre-sizing for the cold filesystem copy destination**, before its 64 KiB copy loop, as an isolated experiment in the guest snapshot helper/FS copy boundary. Preserve the existing cold-copy format, hashes, file contents, isolation and error behavior; compare growth alloc_space and G(0) footprint. The demonstrated export-tree growth history (~775 MiB for ~138 MiB logical data) makes this the smallest allocation-churn target. It is not a promise to fix Darwin reclamation or all per-child zeroing effects. No such implementation is included here; human decision comes before implementation.

Production GC/FreeOSMemory, finalizers, mmap migration, CoW, API/format changes, race work, buffer tuning, canonical benchmark reruns and execution-architecture changes are out of scope. All 22 independent processes / 260 checkpoints completed (including two pure-Go controls); OS/FD counters were available at every checkpoint. Diagnostic SQL/fixture checks succeeded in every DB trial; harness build/scoped vet and diff checks are recorded with the tooling. Raw profiles/mappings are disposable external work; compact observations and hashes remain in the repository.

## Primary verdict

**OS PHYSICAL ACCOUNTING DOMINATES**
