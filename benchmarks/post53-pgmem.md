# Post-#53 repeat of the pgmem P4/P8 comparison

**The measured CPU cost gap remains: mariamem used about3.8× pgmem's batch CPU
in this repeat.** The median batch wall was896ms atP4 /775ms atP8 versus pgmem
270ms /288ms. Occasional long SQL intervals still affect mariamem wall time;
this is not evidence of a universal P4 limit or a single proven cause.

Recommend keeping the existing CPU-cost and SQL-wait questions separate. No
new optimization is proposed from this repeat. The strongest limitation is3
fresh processes per cell on one desktop; source states, engines/drivers and
resource lifecycles differ. This is a declared-path comparison, not engine-only
or TCP-only A/B and not a statistically established regression/speedup.

## Same prior workload and pins

Apple M1,16GiB,macOS27.2 arm64; Go1.27.3,CGO0,GOMAXPROCS8. Both TCP.
Same1,000 integer rows,48 independent children; each checks initial COUNT/SUM,
SELECT1, updates one row, verifies and closes. Root closes before children;
worker limits4/8,3 fresh-process repeats and1 separate warmup per cell, order
alternates as before. Batch CPU/wall exclude root preparation/capture/final
Snapshot close; they include all child startup/use/disposal. RSS sampled20ms
via the same Darwin ABI, checked against ps outside measurement. Sampled peaks
can miss shorter transients; they are not retained-child memory or allocations.

- mariamem: main `6e29c1cd125aa95f564969b905cbff462d4f0e74`.
- pgmem: v1.18.2 source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`,
  tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`.
- Original harness: `d10cfa8fb810b512333bcfa8b9d661493325478e`;
  Go source,go.mod and go.sum bytes are unchanged. The new harness commit only
  imports those files and changes the mariamem source pin. Replacements point
  to clean independently checked product sources; module graph and binary hashes
  are retained. Binary VCS stamps identify the harness, not the replaced library.
- Current default auto capacity permits observed8 active children on this host;
  pgmem retains its original explicit per-pool worker cap. No wait-saturation
  benchmark or new equivalence claim is added.
- Positive/negative seed pilots both pass with complete cleanup. Ordinary cohort:
  12 processes /576 children; separate4 warmup processes /192 children. All SQL,
  isolation, phase/occupancy and cleanup oracles pass. No tail is removed.

## Current cross-product cohort

Wall ms (median with min–max); CPU seconds summed over process threads during
the batch. RSS MiB is the median of observed batch peaks. The last column is
historical v0.6.0/v1.18.2 measurement at5096a0c4, context only, not today's control.

| Product | Workers | Wall ms | CPU s | CPU/child ms | Peak RSS MiB | Historical wall ms / CPU s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| mariamem | 4 | 896.3 (883.6–1067.4) | 4.063 | 84.6 | 372 | 1114.8 / 3.227 |
| mariamem | 8 | 775.3 (721.3–1216.0) | 4.522 | 94.2 | 686 | 599.6 / 3.776 |
| pgmem | 4 | 270.4 (253.4–280.9) | 1.081 | 22.5 | 938 | 269.4 / 1.066 |
| pgmem | 8 | 287.8 (235.0–313.4) | 1.196 | 24.9 | 1001 | 266.0 / 1.230 |

mariamem P4→P8 wall ratios are0.816,0.726,1.357: two runs shorten and one lengthens.
AtP8 round2, batch1216ms includes SQL up to800ms; P4 round1 also has SQL789ms.
These intervals include scheduler/non-execution time and do not identify a DB
internal queue. CPU, wall and memory are distinct observations. Current batch
peak RSS is lower for mariamem than pgmem; it does not overturn earlier retained
per-child RSS observations, which measured a different lifetime/cohort.

## Same-session v0.6.0 A/B control

Historical mariamem CPU was lower, while pgmem changed less. To avoid labelling
that a new-source regression, one bounded control repeats the identical MariaDB
harness with v0.6.0 and main, interleaved3 pairs/P4/P8 after separate warmup.
This later cohort is not mixed into the pgmem comparison above. Only the alternate
modfile changes the library replacement to the checked clean v0.6.0 clone.

| Workers | v0.6.0 wall median / range ms | main wall median / range ms | CPU v0.6.0 / main s | CPU change |
| --- | ---: | ---: | ---: | ---: |
|4|814.4 /785.9–837.8|808.7 /805.0–818.3|3.794 /3.808|+0.3%|
|8|670.9 /670.1–1470.7|729.0 /667.1–1334.5|4.236 /4.216|−0.5%|

CPU is effectively flat within this small control. P8 wall median is+8.7%, with
wide overlapping ranges and long runs in both sources; this does not establish
a repeatable wall regression. It also does not prove equivalence. Historical CPU
versus today's CPU alone cannot attribute a change to #53 or #63. No CPU-frequency,
OS-pressure or per-engine-instruction attribution was measured.

## Evidence and scope

[Compact evidence](forkcompare/post53-results/README.md) retains read-only
regeneration/checksums, per-run summaries, pilot/source/binary/module provenance,
phase maxima and sampled-resource metadata. Same-session control has12 ordinary
processes /576 children and4 warmups /192 children, separately indexed. Original
raw-file hashes are retained, with the compact projection explicitly labelled.
The prior cohort's report/raw refs are unchanged. This measurement branch is not
automatically merged into main; no product, guest, generated runtime, public API,
release or performance gate was changed. No70-case macro/in-process route, cold
setup or cross-platform claim is made.
