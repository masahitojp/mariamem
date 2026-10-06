# v0.4.3 first-use / Snapshot attribution

Baseline main: `a23e450af19fd2086a008cc85ed35173f0103801`. Independent Track B,
investigation only. Reuses `cc24747` characterization tooling/opt-in timing,
rebased as `b73c19b`; adds query pairs, existing OS counters, two export timing
marks, and small CPU profiles. No guest regeneration, SQL policy, Snapshot,
Fork, integrity or memory optimization. macOS arm64 / Go1.26.8, kernel Darwin27.0.

## Result

The earlier ~290ms first COUNT is predominantly a **recurring size-dependent
InnoDB broad-read workload through the generated runtime**, not query-independent
first-use initialization or a Fork-specific deferred operation. Attribution is
mixed: InnoDB's small buffer pool drives repeated backend reads; generated/WASIX
read copying and Go thread synchronization/scheduling add cost. The evidence does
not establish a safely removable optimization or prove every part unavoidable.

Snapshot and COUNT share the general fact of moving substantial data. Their
dominant measured mechanisms differ: Snapshot copies/allocates/materializes and
repeatedly inventories/hashes full prepared state; COUNT repeatedly reads table
pages and executes/synchronizes the scan. Similar historical magnitudes were not
proof of one mechanism. Snapshot has ~138MiB fixed system/redo/undo state even
for the minimal fixture, while COUNT depends on the selected user table.

Recommendation: **no v0.4.4; document behavior and proceed toward v0.5**, subject
to Human Review. No concrete performance regression, unexpected deferred task,
or proven removable overhead requiring a separate release was identified. This
is not a claim that scans or publication cannot be improved.

## Query evidence

Three fresh-process replicas for each deterministic payload. One newly forked
child per query type, so PK/range cannot warm COUNT. Each connection is explicitly
Pinged before the timed query; first/second use the same connection immediately.
Table: `id INT PRIMARY KEY, payload VARBINARY(1024)`, no secondary index;
1 / 10,240 / 102,400 rows with deterministic 1KiB payloads. Range reads up to8
rows. Broad scan computes SUM(CRC32(payload)); all counts and checksums agree.
Medians in ms, first / immediate second:

| Payload MiB | Prepared MiB | SELECT1 | PK lookup | <=8-row range | COUNT | Full payload CRC scan | Fresh COUNT |
| --- | --- | --- | --- | --- | --- | --- | --- |
| minimal | 138.08 | 0.55 / 0.50 | 1.06 / 0.79 | 1.01 / 0.81 | 1.24 / 0.74 | 0.91 / 0.74 | 0.58 / 0.58 |
| 10 | 157.02 | 0.51 / 0.49 | 1.95 / 0.78 | 1.79 / 0.88 | 33.90 / 33.29 | 43.29 / 40.69 | 32.02 / 33.20 |
| 100 | 262.02 | 0.63 / 0.74 | 2.02 / 0.83 | 2.48 / 0.92 | 337.84 / 357.12 | 455.85 / 411.13 | 351.61 / 353.88 |

Connections are ~1ms. Small first table reads have ~1ms excess; this cannot
explain hundreds of ms. Fresh is Start+equivalent insertion, with hot fixture
history, not an independently cold OS-disk control. It nevertheless reproduces
the recurring broad-read cost without prepared mappings or Fork.

One separate 100MiB STATUS/EXPLAIN control: COUNT plan is `ALL`, no selected key,
~99,675 estimated rows. InnoDB buffer pool16MiB, page16KiB, read IO threads1,
write IO threads2. First COUNT increases buffer_pool_reads by7,501 and
Innodb_data_read by122,912,768B (~117.2MiB); second increases by7,357 and
120,537,088B (~115.0MiB). These are **InnoDB backend reads**, not physical disk
reads. A table larger than the16MiB buffer pool rereads substantial pages even
on the immediate second execution. This control's timings (~509/503ms) are
separate diagnostic observations and are excluded from the median table.

Fork COUNT median minor faults first/second: minimal250/226, 10MiB1608/646,
100MiB9252/2189; major faults0 throughout. At100MiB first COUNT RSS increases
~113MiB while physical footprint increases only a few MiB. Prepared hashing and
preparation warm the OS page cache; initial mapping page touches exist but are
not the dominant explanation for repeated ~350ms COUNT. Page faults/footprints
include the pre-query resource-helper and ReadMemStats overhead; wall/CPU timed
operation intervals exclude those checkpoints. Do not infer universally cold
disk performance or private-copy bytes from these counters.

Separate 100MiB first COUNT CPU profile:600ms sampled over503ms duration;
300ms pthread_cond_signal,170ms pthread_cond_wait,60ms runtime.usleep,50ms
memmove reached through memFile.ReadAt/Fd_pread. Synchronization/scheduling is
prominent. The profile includes all process threads and the resource watchdog;
short samples and cumulative overlap forbid treating percentages as precise
causal speedup estimates. It shows the generated runtime participates in the
recurring scan; it does not prove a removable scheduling defect.

## Snapshot evidence

Same fixture sizes, three replicas. Stage medians are independent and not
necessarily additive. Export transfer is nested within shutdown/copy/export.

| Payload MiB | Public Snapshot ms | Shutdown + guest copy + export ms | Export transfer nested ms | Publish ms | Outside host scope ms |
| --- | --- | --- | --- | --- | --- |
| minimal | 359.84 | 94.68 | 60.73 | 199.14 | 63.27 |
| 10 | 395.33 | 105.69 | 68.40 | 214.82 | 74.29 |
| 100 | 830.23 | 224.92 | 155.08 | 461.45 | 136.76 |

Source: guest resident closes MariaDB/joins sessions, snapshot_copy walks and
copies MemFS into snapshot-out; exportTransfer enumerates, allocates one full
file buffer, reads MemFS, writes transfer disk files. Publish inventories/hashes
source, copies to destination, inventories/hashes destination, writes manifest.
Public Database.Snapshot then independently Validate-hashes the result.
The outside-host column includes this validation and public cleanup/trace
recording; it is not an isolated hashing timer. Session draining and destination
preconditions are sub-ms in these cells. Enumeration visits the same small set
of files; bulk data work scales strongly with bytes.

Separate100MiB Snapshot CPU profile:760ms sampled over1.01s;470ms (~62%) in
DigestTimed/inventory file reads,150ms (~20%) in Publish copying,70ms in
exportTransfer,50ms executeGuest (including preallocation/guest copying).
Cumulative stacks overlap: do not sum arbitrary parent and child entries.
Allocation clearing also appears (~60ms flat). File reads/writes/materialization
and integrity work dominate, rather than the COUNT synchronization stacks.

Data-size sensitivity is shared; a single dominant shared mechanism is **not
demonstrated**. Snapshot's cold-state creation and InnoDB scan/cache policy are
structural requirements; number of copies, inventories, generated read/scheduling
implementation and ownership contracts are mariamem-controlled design choices.
Equivalent correctness must survive any future changes. In particular Fork
currently spends ~53–62% of ready latency validating prepared-state integrity
(existing evidence). This task changes no hashing. Future optimization must
preserve equivalent corruption/change detection or establish a stronger
ownership/immutability contract.

## Reproduction, checks and retention

[Harness](snapshotcharacterization/main.go),
[runner](snapshotcharacterization/firstuse_run.py),
[compact evidence](v043-first-use-evidence/inputs.json),
[CSV](v043-first-use-evidence/summary.csv), per-cell JSON (including traces),
STATUS JSON, two small pprof files and profile tops are committed. Historical
characterization report/measurements are retained; historical raw local scratch
is not a required live runtime or workspace.

```sh
python3 scripts/experiment_workspace.py prepare NAME --branch experiment/NAME --min-free-gib 8 --budget-gib 4
# In that worktree, set an owned GOCACHE path and build:
GOTOOLCHAIN=go1.26.8 go build -p 1 -o ../temp/characterize ./benchmarks/snapshotcharacterization
cc -O2 -o ../temp/process_cost benchmarks/tools/process_cost.c
# In the repository owning the workspace:
python3 scripts/experiment_workspace.py run --timeout 900 NAME -- python3 benchmarks/snapshotcharacterization/firstuse_run.py
```

The runner supplies evidence/temp paths. Optional control uses the same binary
with `-mode status -payload-mib 100 -helper PATH -out PATH` under
experiment_disk.py; original cells use `-mode firstuse`.
Profile generation is enabled only for replica0's100MiB equivalent preparation.

Focused verification: timing race tests; generatedgo initialization/partial
initialization tests and guest startup/opt-in transport tests; scoped vet;
Python compilation and diff checks. The changed dependency is bounded opt-in
observation at generated startup/export and private diagnostic copying, so these
checks plus successful Snapshot/Fork/query/Close cells exercise it. No broad
runtime/ORM/release suite or final canonical benchmark is justified or run.

Budget:8GiB minimum free,4GiB owned disk,4GiB RSS/physical sampled ceiling;
9 matrix cells plus1 STATUS control. No guard violation. Recreated binaries,
owned build cache/temp, completed worktree are disposable after pushed evidence.
Exact branch final SHA and cleanup receipt are recorded in the final review
handoff; no retained owned path >1GiB is required.
