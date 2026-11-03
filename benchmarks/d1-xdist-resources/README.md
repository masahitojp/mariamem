# D1 xdist RSS and heavier preparation — 2026-11-03

Decision: choose a worker-count starting point, not change product defaults.
For this workload start with2 workers; use serial for very small/heavy suites
and4 when enough tests and memory headroom justify it. Four workers improved
240-test time2.21x light /1.79x heavy, with observed summed RSS maxima868 /1080MiB.
The prior75MiB×4≈300MiB estimate misses Python/controller and complete host state.

## End-to-end time

Seconds, median of3 measured repetitions. Fresh pytest processes/hosts each
sample; OS caches warm after a separate6-cell pilot. Same8-class workload in all
modes, no sleeps or overlap barriers. Columns include startup, migration/seed,
class/test Forks, assertions and cleanup. Times include RSS observation overhead.

| Preparation | Tests | Serial | 2 workers | 4 workers | 4w vs serial |
| --- | --- | --- | --- | --- | --- |
| light | 16 | 1.80 | 1.71 | 1.69 | 1.06x |
| light | 48 | 3.61 | 2.69 | 2.42 | 1.49x |
| light | 120 | 7.82 | 5.16 | 4.12 | 1.90x |
| light | 240 | 15.15 | 9.23 | 6.87 | 2.21x |
| heavy | 16 | 2.72 | 2.61 | 2.75 | 0.99x |
| heavy | 48 | 4.54 | 3.74 | 3.86 | 1.18x |
| heavy | 120 | 9.10 | 6.39 | 5.64 | 1.61x |
| heavy | 240 | 16.22 | 10.67 | 9.09 | 1.79x |

At16 tests differences are small: heavy serial2.71–2.73s vs4w2.73–2.87s;
light serial1.76–2.09s vs4w1.67–1.82s. Do not infer a precise crossover there.
At48 tests light4w beats2w (2.42 vs2.69s); heavy4w does not (3.86 vs3.74s).
At120 tests heavy4w beats2w (5.64 vs6.39s). Thus the observed4-vs2 worker
advantage shifts to a larger suite under heavy preparation; its interval is
bracketed by48 and120 here, not a universal120-test threshold. Four-vs-serial
and four-vs-two crossovers are different questions.

## Sampled memory

Maximum across all measured test counts/repetitions, MiB summed RSS over the
owned pytest process tree. This is neither per-worker RSS nor unique physical
RAM: shared executable/library pages can be counted repeatedly across processes.
Sampling can miss short peaks. Do not treat it as a portable container limit.

| Preparation | Serial | 2 workers | 4 workers |
| --- | --- | --- | --- |
| light | 203 | 468 | 868 |
| heavy | 258 | 574 | 1080 |

Controller/serial pytest, Python workers and all host processes are included;
other descendants are counted if observed. The per-sample simultaneous-peak
role breakdown is retained in [samples.csv](results/samples.csv). A host owns
multiple run/class/test database states, so a single-child resident estimate
cannot substitute for whole-tree observation. Eight classes and loadscope limit
the active-work distribution in this experiment.

## Preparation and limits

Light uses the original orders migrations/seed. Heavy adds one actual migration:
20 indexed tables,1000 rows each,512-byte payloads (~9.77MiB retained payload).
Every table's row count/payload sum is asserted during migration. This is real
DDL/seed work, not sleep. It also enlarges retained baseline/schema, so it changes
both preparation and potential per-test cost; it is not an isolated fixed-F proof.

Preparation observation spans public host start through first baseline capture,
excluding Python import startup/class setup. Maximum-per-worker medians span
~0.09–0.20s light and~0.92–1.58s heavy. Parallel heavy preparation itself is
slower per worker due to contention. Raw per-sample maxima are in the CSV.

Local Apple M1,8 logical CPUs,16GiB RAM, macOS27.2, Python3.14.10,
Django6.1.2, pytest9.0.2, pytest-django4.12.0, xdist3.8.0 / execnet2.1.2,
mysqlclient2.2.7. This differs from the earlier Python3.11/Django5.2 timing:
do not compare its2.43x directly or attribute the change only to preparation.

`ps` reads PID/PPID/RSS/executable; only the launched test's descendant tree is
retained. Polling waits100ms plus command duration (observed median interval
0.143s). The sampler runs outside the measured tree but can consume CPU;
its wall-time perturbation was not separately calibrated. These are diagnostic
RSS/time observations, not high-precision bare-pytest timing. Background activity,
CPU scheduling, GC and macOS memory behavior are uncontrolled. No Linux physical
footprint, cgroup limit, huge schema, remote worker or other scheduler claim.

## Identity, correctness and reproduction

Benchmark source_commit: `39998ac0fd90c1aea2bff055bb635fdfb685adf5`.
Product base: `954231bf7451f7b45bdbeb453a144204286eea18`.
Reused host source_commit: `d99f07cd16a8a11c1644225206a3d1fcc0a39edd`.
[Inputs](results/inputs.json) and [artifact identity](results/artifact.json) retain
package versions, host/wheel hashes and embedded clean Go VCS evidence. No product
runtime changes or rebuild. No CI submitted. Issue77 tracks this bounded campaign.

72 measured subprocesses/7632 tests passed; all168 observed root hosts and every
sampled descendant exited. The separate pilot passed96 tests/14 root hosts.
Sampler/recipe syntax and6-cell pilot checked before the measured campaign.
Medians/sample counts and saved hashes independently recomputed afterward.
[Summary](results/summary.csv) has24 cells; [samples](results/samples.csv) has72
rows with result/RSS/JUnit hashes. Full RSS/JUnit/stdout stays in local durable
workspace evidence, not a product PR. No noisy log dump is merged into main.

In an isolated Python3.14 environment with the pinned Django lifecycle
requirements installed, from the clean benchmark source:

```sh
python benchmarks/d1-xdist-resources/run.py --host /absolute/verified/mariamem-host --output /absolute/pilot --pilot
python benchmarks/d1-xdist-resources/run.py --host /absolute/verified/mariamem-host --output /absolute/results
```

One sequential campaign; default2h active/30min instrumentation budget,0 heavy
CI submissions. No performance/resource guarantee or worker default is adopted.
For another application measure its preparation/data footprint and memory budget
before increasing worker count. Generated environments and the finished worktree
are discarded after preserving this report, recipe and compact evidence.
