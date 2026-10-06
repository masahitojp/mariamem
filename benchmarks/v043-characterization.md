# v0.4.3 Snapshot/Fork characterization

Investigation source: `2715c44df0f567930a1d6ef272a18bcffd401a29`.
[Complete first-use report and compact evidence](https://github.com/masahitojp/mariamem/blob/2715c44df0f567930a1d6ef272a18bcffd401a29/benchmarks/v043-first-use-attribution.md).
This release imports conclusions, not experimental instrumentation or optimization.

Snapshot is cold prepared file state; Fork validates the inventory/hashes and
starts fresh execution. Production `prepared_files.go` maps the same files with
`MAP_PRIVATE`, so the OS can share clean pages and privately copy written pages.
No running heap, threads, TLS, locks or stacks are cloned. No custom CoW
filesystem or Unix process fork is used. Nodes/metadata and runtime state are
independent; growing files can materialize a Go copy. OS sharing is not a public
resource promise.

## Ready latency and first query are different boundaries

Existing measured Fork cases attribute roughly 53–62% of ready latency to
prepared inventory/hash verification, around 1 ms to mapping and around 35 ms to
minimal server initialization. Nested InnoDB/plugin/open timings overlap; do not
sum them independently. Hashing provides integrity validation, not disposable
work that these percentages alone justify removing.

Three macOS fresh-process replicas per deterministic payload measured first /
immediate second queries (medians, ms):

| Payload | SELECT 1 | PK | <=8 rows | COUNT | Fresh COUNT |
| --- | --- | --- | --- | --- | --- |
| minimal | 0.55 / 0.50 | 1.06 / 0.78 | 1.01 / 0.81 | 1.24 / 0.74 | 0.58 / 0.58 |
| 10 MiB | 0.51 / 0.49 | 1.94 / 0.78 | 1.79 / 0.88 | 33.90 / 33.29 | 32.02 / 33.20 |
| 100 MiB | 0.63 / 0.74 | 2.02 / 0.83 | 2.48 / 0.92 | 337.84 / 357.12 | 351.61 / 353.88 |

The previously suspicious 290–350 ms COUNT was not generic Fork first-use work.
The 100 MiB fixture exceeds the 16 MiB InnoDB buffer pool; a separate STATUS
control records ~117.2 MiB and ~115.0 MiB backend reads on successive COUNTs.
Major faults were zero in this measured warm-OS-cache setting. Backend reads
are not physical-disk reads. Fresh reproduces recurring COUNT cost. Profiles
show generated-runtime reads/copies and thread synchronization participate;
short overlapping profiles do not establish a safely removable defect.

Snapshot and COUNT both touch large data, with different dominant mechanisms:
Snapshot exports/materializes/copies/inventories/hashes; COUNT scans/rereads
InnoDB pages and synchronizes through the generated runtime. They are not one
shared 300–400 ms mystery or a Fork-only hidden initialization penalty.

## Conservative workload guidance

- Small schema/light setup: Fresh is often sufficient or preferable.
- Expensive migrations/business fixtures: Snapshot/Fork can amortize setup.
- Large prepared state/parallel tests: independent mutable children and OS
  sharing of prepared clean pages help, but query read cost still matters.

Crossover depends on setup, query, child count and resource boundary. Historical
measurements are not permanent promises. New ownership/API, integrity-check,
CoW or Fork optimization proposals are not accepted v0.4.3 architecture.
