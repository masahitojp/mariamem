# MemFS limited allocation attribution — current 12.3.3 guest

2026-10-14. **Requested limited investigation COMPLETE; Human decision pending.**
No storage optimization has been implemented or adopted.

## Human Review

The decision now is whether these results justify an optimization spike.
**I recommend retaining the current MemFS + MAP_PRIVATE implementation and
ending this investigation without starting a growth/sparse prototype.** The
large allocations are now attributable, but their quantities do not translate
into a demonstrated product benefit. Resize takes only about 11.6 ms in a roughly
917 ms measured Fresh suite. Replaying the actual main-table requests at growth
factor 1.5 predicts about 20 MiB less cumulative capacity allocation and 23 MiB
less copying, with about 3.7 MiB more final spare capacity; this is not a physical
memory saving or measured speedup.

The strongest objection is the approximately 143 MiB of still-unwritten logical
reservation after fixture preparation: a sparse representation looks attractive.
However, the process's startup physical footprint is only about 82 MiB despite
150 MiB of MemFS logical capacity, and the existing Snapshot path subsequently
reads/writes the full exported files. The nominal reservation therefore cannot
be counted as removable RAM or whole-suite cost. This does not reject sparse
storage generally; it leaves its product benefit unestablished in these cases.

This recommendation uses the existing investment yardstick: roughly 10% time/CPU
or 20% physical footprint plus 32 MiB/DB, with no persistent adverse tradeoff.
Those are engineering decision thresholds, not user-facing guarantees or a rule
that smaller benefits have no value. If the Human values the modeled cumulative
allocation reduction itself, a one-factor growth spike is still selectable;
it requires a separately agreed lower benefit target. No automatic expansion,
coefficient sweep, VFS replacement or release work follows this report.

## Starting evidence and fixed scope

The [existing Architecture Decision, §7](memfs-architecture-decision.md#7-minimum-next-measurement--これで次の選択を決める)
owns the scope/routing thresholds. Prior allocation profiles and external VFS
reviews are reused as historical context, not counted as independent current
measurements. The old Decision's fd_allocate shrink concern was subsequently
fixed in v0.5 correctness work; current Allocate preserves size/content/position
and the existing contract tests are retained. That old defect is not reopened
or presented as an outstanding performance fix.

The four current questions are initial reserve versus reallocation, written
coverage/lifetime, child-only mapped detach, and significance for time/physical
memory. Minimal (one row/one table) and 10 MiB/8 tables each run Fresh and
Prepare → Snapshot → one Fork → application connections/CRUD → Close, three
trials each, with at most one active DB. Each is paired with the unchanged
control harness: **12 control + 12 observed = 24 primary cases**. One additional
same-case aggregate resize timer and one bounded main-table request capture
make **26 scenarios / 38 DB instance lifecycles** including preparation DBs.
All runs are retained; no outliers are removed.

100 MiB was not added because the small cases expose the growth and no unexplained
detach. Native Ubuntu, candidate parallel remeasurement and actual optimization
comparisons are outside this completed attribution step. Prior
[four-parallel product evidence](../../benchmarks/v050-product-verification.md#resources-and-cleanup)
is context: v0.5 Go parallel-Fresh peak RSS about 789.6 MiB. That historical
candidate had the startup tail and is not a current-main performance baseline.
Its resource behavior does not prove a present memory-budget violation.

The separately paused [Snapshot direct-copy work](https://github.com/masahitojp/mariamem/blob/b6d371232f613425b066049bb3e6f873cfee4e37/docs/reviews/snapshot-direct-copy-recheck.md)
is not enabled here. Its lesson is applied: count whole preparation/use/cleanup
and distinguish reduced allocation from product improvement and changed GC.

## Initial allocation, reallocation and copying

Representative trial 0; repeated runs show essentially the same capacity/copy
quantities. Units are MiB of requested Go byte-slice capacity, not RSS or retained
memory. These numbers exclude linear Wasm memory and host export buffers.

| Case | Initial capacity allocations | Reallocation capacity allocations | Old logical bytes copied | Child mapped detach bytes |
| --- | ---: | ---: | ---: | ---: |
| Minimal Fresh | 150.07 | 0.04 | 0.02 | 0 |
| Minimal prepared + Fork | 300.16 | 0.04 | 0.02 | 0 |
| 10 MiB/8-table Fresh | 150.52 | 86.28 | 64.95 | 0 |
| 10 MiB/8-table prepared + Fork | 319.98 | 86.28 | 64.95 | 0 |

The prepared-suite initial sum includes the source DB, guest-created Snapshot
output and child allocations. It is not 320 MiB of simultaneous source storage.
In the 10 MiB Fresh case, reallocation is about **36.4%** of MemFS capacity
allocation, satisfying B's screening ratio. Almost all of it is one file during
fixture SQL; it is not startup or a Fork-specific penalty.

| Main file | Allocation pattern and role |
| --- | --- |
| `mariadb/data/ib_logfile0` | One 96 MiB initial allocation; redo log. No reallocation in these runs. |
| `mariadb/data/ibdata1` | One 12 MiB initial allocation; shared system tablespace. |
| `mariadb/data/undo001/002/003` | One 10 MiB allocation each; three undo tablespaces. |
| `mariadb/data/ibtmp1` | One 12 MiB initial allocation; temporary tablespace, recreated in the child and omitted from saved files. |
| `mariadb/data/test/characterization.ibd` | 64 KiB initial allocation, 14 reallocations during fixture SQL; 86.24 MiB reallocation capacity and **64.94 MiB old-data copy**. Final logical size 19 MiB, capacity 19.073 MiB. |
| Seven additional `.ibd` files | 64 KiB each, empty tables in this fixture; no comparable growth. |

The main table has 52 successful expanding Allocate calls; only 15 actually
allocate a new buffer, including the initial allocation. Growth within capacity
explicitly clears about 8.86 MiB. Newly allocated slice capacity is implicitly
zero-initialized by Go; its nominal size is not a measurement of pages physically
touched or the cost of memset. Host WriteFile population copies and host export
reads are recorded separately.

See [attribution-summary.json](memfs-attribution-evidence/attribution-summary.json)
for every file/phase, including removed nodes and all trials. The historical
~4.62 GiB resize allocation across 20 DBs was cumulative: this new one-DB capacity
sum of about 237 MiB is consistent in scale, not a claim that 4.62 GiB is live,
removable or unchanged across all guests/workloads.

## Unwritten reservation and lifetime

Four-KiB coverage has conservative lower/upper bounds. Explicit zero writes count
as writes; no content/nonzero scan occurs. Shrink/O_TRUNC advances an epoch and
clips suffix coverage, preserving surviving prefix coverage. The bounded collector
retains scalar metadata/bitmaps, not filesystem/node/data references. Imported
prepared bytes are recorded separately and are not treated as unused reservation
just because a child has not written them.

| Fresh phase, medians of three | Live source logical bytes | Live source capacity | Unwritten logical range | Process physical footprint |
| --- | ---: | ---: | ---: | ---: |
| Minimal ready | 150.01 | 150.01 | 149.97–149.98 | 81.85 |
| Minimal fixture finished | 150.09 | 150.09 | 145.56–145.57 | 86.67 |
| 10 MiB ready | 150.01 | 150.01 | 149.97–149.98 | 81.56 |
| 10 MiB fixture finished | 169.47 | 169.54 | 142.59–142.89 | 191.99 |

About **84%** of 10 MiB fixture logical storage is unwritten, surviving startup
and fixture phases; C's nominal 32 MiB/25% screen is met. Unwritten is not unused
by the guest: valid reads must still return zeros, reserve semantics remain, and
the guest's Snapshot copy reads all exported logical bytes.

Physical footprint is process-wide, including runtime/linear memory/allocator
history; no per-file resident attribution is claimed. Because startup footprint
is smaller than nominal reservation even for the whole process, subtracting
143 MiB from RSS/footprint would be invalid. The physical/time condition needed
to justify a sparse implementation is not established by nominal coverage alone.

## Snapshot and child-only behavior

| 10 MiB prepared-suite phase | Tracked active MemFS heap capacity | Tracked active mapped file bytes | Go HeapAlloc | Process physical footprint |
| --- | ---: | ---: | ---: | ---: |
| Fixture finished | 169.54 | 0 | 243.57 | 191.00 |
| Snapshot returned/source ended | 0 | 0 | 476.98 | 523.88 |
| Fork ready | 12.00 | 157.46 | 489.64 | 586.58 |
| Child Close | 0 | 0 | 491.36 | 513.10 |

These are phase-end samples, not instantaneous memory peaks. Peak process RSS
is separately retained in the ordinary/observed comparison. Tracked capacity zero
means the runtime-owned FS lifetime ended, not that Go already collected its old
buffers or the OS returned all pages. Existing final diagnostic GC remains outside
product wall time; no extra forced GC is inserted into the lifecycle.

The guest creates separate Snapshot MemFS files, then the host reads them for
materialization. Exported logical size is about 138.08 MiB minimal and 157.46 MiB
for the larger fixture; these output files are fully written/read even when the
source reservation is mostly unwritten. Fresh-side sparse storage does not
automatically remove this downstream full-file work or the existing hash checks.

At child ready, saved files use the existing private mappings; the approximately
12 MiB child heap is chiefly new temporary tablespace. **No mapped-to-heap growth
detach occurs in any selected child.** This supports keeping D (prefix + growth
tail) deferred for this workload, not declaring the path unreachable. More
expanding child transactions can behave differently.

After every primary run, existing linear-mapping counters report zero active
mappings and zero release failures. Observer-aware Close/rename/unlink tests
preserve ID and handle accounting. The physical remainder after Close is not
presented as a leak or as guaranteed promptly reusable memory.

## Time attribution and measured-request growth model

One same-case Fresh run with only aggregate resize timing enabled reports
**11.626 ms** across all resize calls; main-table fixture Allocate accounts for
**10.748 ms**, startup Allocate about 0.840 ms. Its product wall is 916.680 ms.
Timers surround original resize/make/copy/clear, excluding observer accounting
and FS-lock acquisition; this is aggregate elapsed call time, not exclusive CPU
or a measured attainable speedup. Indirect allocator/GC effects are not settled
by that ratio. The result does not support a 10% speedup claim from eliminating
these direct costs. No all-I/O timers or broad lock/profile campaign was added;
historical CPU profiles remain identified as historical context.

To apply the existing growth model to real input rather than an assumed append
pattern, one additional same-case run records the main table's **52 expanding
requests**, capped at 128; it records sizes only, not all I/O events or content.
The current-policy arithmetic matches all recorded old/new capacities and totals.
Changing large-buffer growth from 1.25 to 1.5 in the arithmetic gives:

| Main-table model, identical requests | Current 1.25 | Candidate 1.5 |
| --- | ---: | ---: |
| Actual/new allocations | 15 | 12 |
| Cumulative allocated capacity | 86.305 MiB | 66.281 MiB |
| Old logical bytes copied | 64.938 MiB | 41.938 MiB |
| Final capacity | 19.073 MiB | 22.781 MiB |
| Final spare capacity | 0.073 MiB | 3.781 MiB |

Thus approximately **20.024 MiB cumulative allocation** and **23 MiB copying**
are removed in the model, with **3.708 MiB more retained capacity**. Physical
peak, GC, wall/CPU and allocation failure behavior were not simulated or tested
with an optimized backend. This modeled benefit alone does not establish the
existing 32 MiB/20% physical-memory investment target. See
[growth-model.json](memfs-attribution-evidence/growth-model.json) for the full input
sequence and replay, not a fabricated optimization benchmark.

## Observer effect and evidence limits

Control uses the unchanged main harness/binary. Observed uses the same workflow
with phase hooks outside each operation timer and the metadata observer inside
FS operations. All resource runs use the same existing Go sampler and OS helper;
observed adds phase probes and counter work. Alternating trial pair order is
control/observed, observed/control, control/observed. No other benchmark runs
concurrently. Values below are medians of three.

| Case | Control → observed product wall | Change | Control → observed peak RSS | Observed cumulative Go allocation |
| --- | ---: | ---: | ---: | ---: |
| Minimal Fresh | 0.087 → 0.084 s | −3.2% | 121.84 → 122.12 MiB | 151.49 MiB |
| Minimal prepared/Fork | 0.558 → 0.587 s | +5.2% | 543.23 → 544.09 MiB | 442.50 MiB |
| 10 MiB Fresh | 0.896 → 0.909 s | +1.4% | 228.97 → 229.75 MiB | 296.37 MiB |
| 10 MiB prepared/Fork | 1.456 → 1.441 s | −1.0% | 639.56 → 659.86 MiB | 628.39 MiB |

All min/max/CPU/allocation values are in
[comparison-summary.json](memfs-attribution-evidence/comparison-summary.json).
Differences include variation as well as observer cost; negative changes are not
an observer speedup. The larger observed Fork RSS and +5.2% minimal wall difference
prevent treating the observer as free. Primary attribution is quantities/coverage,
not candidate speed. Accounted counter/bitmap storage is at most about 93 KiB,
bitmap at most about 25 KiB; accounting excludes maps/strings/frame slices/JSON
serialization, so it is a lower bound. Complete observed-control TotalAlloc
differences are around 0.26–0.90 MiB, not an exact standalone observer allocation
measurement. Phase boundaries bracket when calls execute; background guest I/O
can cross a boundary, and coverage samples do not freeze the guest atomically.
Coverage-limit overflow was zero in all runs.

## Per-question judgments and routing

| Requested item | Judgment and effect on recommendation |
| --- | --- |
| Initial reserve vs reallocation/copy | CONFIRMED for selected cases: startup initial 150 MiB, main-table fixture reallocation/copy hotspot. B passes Fresh screening, but measured time and exact model do not establish practical benefit. |
| Written coverage and lifetime | CONFIRMED as bounded write coverage: about 143 MiB persists unwritten across main phases. C passes nominal screening; removable physical memory/time is UNESTABLISHED, so sparse complexity is not justified now. |
| Child-only detach | OBSERVED ZERO in all six instrumented Fork children; D stays deferred. No statement about untested expanding children. |
| Time/physical significance | Direct resize about 1.3% of one Fresh suite; process counters contradict equating reserve with RAM. Optimized physical/whole-suite gain remains unmeasured because no PoC was commissioned. Recommend A. |

This is a conclusion to the authorized investigation, not an incomplete task
waiting for universal workloads or a correctness proof. Existing thresholds
permit A/retain as an outcome. Smaller cumulative allocation savings can be a
different product objective, but that would be a new Human choice, not silent
relaxation of the current adoption criteria.

## Source identity, verification and replay

- Control `source_commit`: `a8137b8b444f86068d3128a291e3a848adfdfd56` (main includes
  the previously saved Snapshot stop decision; main was already ahead of origin
  by that one documentation commit).
- Primary observer `source_commit`: `c3a527d26ceaaad74f5480ac1469ed586716366c`.
- Bounded-event observer `source_commit`: `1c639ceb4516ff5e21ec245dfb319e0508698e8f`;
  it adds opt-in request recording only and preserves the storage policy.
- Guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`.
- Native macOS 27.0.1 arm64, Go 1.26.8, GOMAXPROCS=2. All standalone-clone commits
  resolve with `scripts/git_identity.py`; clean HEAD and exact unmodified VCS
  binary stamps are verified before builds/measurement. No tag object is used.

[inputs.json](memfs-attribution-evidence/inputs.json),
[events-inputs.json](memfs-attribution-evidence/events-inputs.json) and
[unchanged-inputs.json](memfs-attribution-evidence/unchanged-inputs.json) own binary,
harness, guest and source identities. Guest, converter provenance and original
growth policy Git objects are identical across both observer versions and control.
The production growth file also matches the old Architecture Decision's baseline.

| Verification | Result |
| --- | --- |
| Observer range bounds, explicit zero writes, shrink/regrow epoch, rename ID, unlink/open handle, double Close and synthetic detach accounting | PASS |
| Existing Allocate contracts/read-only/invalid/concurrent resize, MemFS growth/zero/offset, private-view/prepared-growth ownership and release tests | PASS with focused race detector, primary and event observers; receipts/logs retained. No general guest race claim. |
| 24 paired primary SQL/commit/rollback/Close scenarios | PASS, every result retained |
| One aggregate timer + one request capture with same SQL assertions | PASS |
| Current-policy model vs actual old/new requests | PASS, all 52 transitions and aggregate counts match |
| Independent instrumentation replay from pinned canonical inputs | PASS; all six output hashes match, primary and event versions recorded |
| Native Ubuntu, optimized implementation, full Release Qualification | SKIP, not performed in this local investigation |
| Canonical generated/release inventory | NOT CLAIMED: the observer is intentionally experimental and unqualified; provenance/guards are not refreshed or relaxed to admit it. |

The experiment's generated support edits come only from the committed exact-input
`benchmarks/spikes/memfs-attribution/instrument.py` and templates; generated output
is not hand-edited. The controller now also asserts full pinned preimage bytes;
independent replay produced identical measured output. New observer files would
fail production inclusion/provenance checks; this experiment is not merge-ready.
Public API, minimum Go, guest source/patches and converter pin are unchanged.

The [evidence README](memfs-attribution-evidence/README.md) gives reproduction and
normalization. Reports, scalar/raw JSON and scripts are committed/pushed on
`experiment/memfs-attribution`; disposable clones, compiler cache, binaries and
worktree are cleaned after preservation. No runtime change is integrated into main.

## Stop condition and later reuse

The requested four questions have judgments above. Stop at Human Review now.
Do not start B/C/D, revive Snapshot direct copy, change guest reserve settings,
or broaden to a VFS replacement from this report alone. If future real workload
or memory-budget evidence changes the decision, reuse these file/phase counters,
the 52-request model, existing ownership failure oracles and full-suite boundary.
That future task must state the concrete user benefit, fixed scope, cost and exit
condition before proceeding. This measurement does not promise optimization
benefits or turn performance questions into release blockers.
