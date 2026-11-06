# Issue117: fixed four callers, MaxForks1/2/4 CPU comparison

**Conclusion:** the notification CPU difference does not grow monotonically
with simultaneous admitted DB count. Its paired CPU-change medians are+1.99%,
+3.16%,+2.54% at caps1/2/4. The matched-round cap4-minus-cap1 contrast is not
resolved from zero. Multiple child DBs overlapping is therefore not established
as the main explanation of the notification CPU cost.

A small typical difference remains at cap1, which still has internal guest
threads and four caller goroutines. It is not a one-thread test. Mean CPU
increment at cap1 has an interval including zero, so do not overstate that result
as a precisely established fixed overhead. Notification allocation/wakeup cost,
earlier shutdown, intra-DB/background/GC work and execution efficiency remain
unattributed. Moving work from one elapsed-time interval to another alone does
not explain a larger whole-batch CPU total; the old wait interval also counted
background CPU.

**Practical result:** cap1 and cap2 have no primary SQL>100ms in either arm and
show whole-batch elapsed improvement. At cap1 all20 pairs are shorter. This
supports a useful latency candidate rather than a blanket rejection. Recommend
retaining the notification candidate with explicit workload-dependent CPU costs;
a separate Human decision and relevant platform correctness precede production
adoption. This does not choose a product default cap or promise a universal
throughput speedup.

## Why the harness changed

The previous benchmark coupled worker count to Snapshot.MaxForks. A new
measurement-only -max-forks option separates them; four caller workers are
fixed while actual Snapshot.MaxForks is1/2/4. The immutable resolved cap is read
back and asserted in every process. Ready-to-disposed child intervals have
observed peaks1/2/4 respectively. Caller lifecycle intervals may peak4 even at
cap1 because they include queued Fork calls. They are not occupied-DB counts.
Ready intervals exclude startup; the unchanged limiter governs admission.

Fork elapsed now includes capacity waiting at smaller caps. Cross-cap Fork
medians must not be interpreted as engine startup speed. No notification,
product host, guest, public API or setting change accompanies this experiment.
The new harness adds readback and ready/disposed markers; cap4 is remeasured in
the same new binary, not imported from the old cohort.

## Source, protocol and verification reuse

- Product `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Measured harness `d05cd878e77828b8c8b6025f4026a335b14912ce`.
- Runtime/overlay parent `c37d578e68b3068173a6734b38f00e11782cb123`.
- Guest `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Apple M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,GOGC100,
  Pipe,1,000 rows,48 children per positive process,product defaults.
- 20 pairs per cap,60 primary pairs/120 processes;20 rounds rotate cap order
  and balance poll/notify-first within each cap. Each arm/cap has960 primary
  children. Six warmups,six separate48-child diagnostic processes and two
  wrong-seed1-child processes give134 measurement processes total.
- Source identity and clean checkout verified before build. Every runtime file
  outside benchmarks/ and all logical overlay hashes equal the prior runtime;
  the binary differs because the measurement harness changed. All arms/caps use
  the same new binary, bound in inputs.json.
- New cap-resolver and existing actual-Exec observer unit tests pass. Prior host
  correctness/race evidence remains reused at original source/report6f780e5a,
  with its original generated-code race exclusion, not a new execution claim.
  All134 expected SQL/seed/update/value/isolation/cap/cleanup outcomes pass;
  both wrong-seed controls fail as intended. No owned DB scratch remains.

### Controller correction and retained data

The first controller stopped in progress printing because its loop variable
round shadowed Python's round(). Nine process records (controls/warmups plus
notify cap1 repetition0) had already passed validation and been saved. The
fixed controller verifies the exact expected prefix and preserves all completed
combinations; none is rerun, replaced or dropped. Original9 result/log hashes
were rechecked unchanged after completion. cap1 pair1 is nonadjacent: its poll
counterpart ran after the correction pause. It is labelled below and retained
in all primary statistics. This limits the adjacent-pair assumption for that
one pair; no favorable subset is used for acceptance.

controller-correction.json and original-run.py retain the original failure scope;
fixed-run.py is the actual resumed controller, hash-bound before resumption.
The final report commit also corrects the canonical loop name; measured source
and binary remain bound to d05cd878. Reproduction uses the fixed controller.
No product/runtime error was hidden and no extra measurement process was added.

## CPU effect by cap

CPU is batch user+system/48, including Fork, SQL, cleanup and background work;
it is not CPU usage percentage or Fork-only CPU. Positive change is more CPU.
The change column is the median of paired percentages, not the ratio of the two mean CPU columns.
Intervals are seed117 whole-round percentile bootstrap10,000 resamples,95%.
Children are never independent bootstrap replicates. Single-host/time-adjacent
and one interrupted-pair limitations remain.

| MaxForks | Poll mean CPU/child ms | Notify mean CPU/child ms | Pair-median change % [95%] | Notify uses more CPU /20 |
|---|---:|---:|---|---:|
|1|51.158|51.946|+1.99 [+0.53,+2.48]|15|
|2|57.067|59.617|+3.16 [+1.58,+3.88]|19|
|4|64.248|65.169|+2.54 [-0.12,+4.90]|14|

Matched-round cap4-minus-cap1 CPU percentage-change contrast: mean+0.24 percentage points,95% interval[-2.94,+3.19]. This does not establish a larger notification penalty at cap4.

Both strategies' absolute CPU/child rises as the cap rises; that is a different
observation from the incremental cost of notification. It does not identify
whether CPU sharing, memory/cache contention, spins or other work causes the
increase. Old cap4 estimates (including the prior20-pair+5.35%) remain at their
original harness/cohort. This fresh cap4 estimate is smaller and less resolved;
there is no fixed universal5% notification tax established across cohorts.

## Whole-batch elapsed and cleanup

All SQL tails included. Batch is Fork+connection+SQL+retirement+DB Close for48
children; root preparation/capture/final Snapshot.Close are outside the timer.
Cleanup columns are means of per-process child medians, not pooled means.

| Cap | Mean batch poll/notify ms | Paired mean difference ms [95%] | Notify shorter /20 | Cleanup poll/notify ms |
|---|---|---|---:|---|
|1|1854.2 /1668.5|-185.7 [-217.4,-162.1]|20|8.473 /4.465|
|2|1014.9 /947.8|-67.1 [-84.2,-47.4]|17|8.427 /4.778|
|4|890.1 /676.3|-213.9 [-365.6,-51.0]|17|9.014 /5.216|

At cap1, mean batch1854.2->1668.5ms (-10.0%), with all20 pairs shorter;
cap2 means1014.9->947.8ms (-6.6%),17/20 shorter. Neither cap has a primary
SQL>100ms. Thus local cleanup savings can appear in suite elapsed, especially
when child DBs are admitted serially. cap1 is still slower in absolute throughput
than cap2/4; this is a diagnostic cap comparison, not a default-cap recommendation.

cap4's larger elapsed gain includes a different long-SQL realization: primary
SQL>100ms counts are11 poll /6 notify, UPDATE>100ms2 /0. The previous20-pair
cap4 cohort had the opposite tail imbalance. Do not generalize this cell's large
wall improvement or infer a causal change in tail frequency. No long sample
was removed or attributed to an owner from another run. CPU uncertainty and
wall uncertainty refer only to this finite cohort.

## All pairs

Positive changes mean notification is slower/more CPU. Asterisk marks the one
nonadjacent cap1 pair retained after the print correction.

| Cap | Pair | First | Poll wall ms | Notify wall ms | Wall change % | CPU change % |
|---|---:|---|---:|---:|---:|---:|
|1|1*|notify|1820.670|1605.725|-11.81|-0.10|
|1|2|poll|1812.443|1618.988|-10.67|+0.59|
|1|3|notify|1846.867|1634.209|-11.51|-0.18|
|1|4|poll|1810.971|1623.798|-10.34|+2.59|
|1|5|notify|1835.653|1623.353|-11.57|-0.05|
|1|6|poll|1830.373|1619.445|-11.52|-0.27|
|1|7|notify|2041.007|1615.197|-20.86|-10.27|
|1|8|poll|1849.456|1681.361|-9.09|+1.79|
|1|9|notify|1812.636|1638.250|-9.62|+1.50|
|1|10|poll|1818.361|1634.040|-10.14|+2.20|
|1|11|notify|1846.694|1666.328|-9.77|+2.28|
|1|12|poll|1824.855|1654.885|-9.31|+1.62|
|1|13|notify|1824.827|1663.608|-8.83|+2.30|
|1|14|poll|1855.584|1675.840|-9.69|+2.37|
|1|15|notify|1863.946|1661.592|-10.86|+0.47|
|1|16|poll|1847.082|1714.570|-7.17|+3.72|
|1|17|notify|1855.548|1721.090|-7.25|+3.15|
|1|18|poll|1931.370|1834.285|-5.03|+9.20|
|1|19|notify|1879.019|1736.378|-7.59|+4.22|
|1|20|poll|1876.104|1746.801|-6.89|+4.10|
|2|1|poll|939.034|889.129|-5.31|+3.98|
|2|2|notify|969.912|898.068|-7.41|+1.47|
|2|3|poll|951.938|889.783|-6.53|+3.88|
|2|4|notify|982.563|880.238|-10.41|+0.42|
|2|5|poll|1000.818|904.990|-9.57|-0.33|
|2|6|notify|967.803|886.098|-8.44|+3.88|
|2|7|poll|985.530|902.448|-8.43|+0.87|
|2|8|notify|1004.370|887.319|-11.65|+1.87|
|2|9|poll|1011.887|926.685|-8.42|+1.35|
|2|10|notify|993.202|911.661|-8.21|+3.33|
|2|11|poll|1043.006|927.888|-11.04|+1.62|
|2|12|notify|1025.918|926.474|-9.69|+1.55|
|2|13|poll|1031.205|962.473|-6.67|+2.83|
|2|14|notify|1030.180|959.029|-6.91|+2.99|
|2|15|poll|1043.822|959.074|-8.12|+3.80|
|2|16|notify|1049.119|976.410|-6.93|+3.72|
|2|17|poll|1035.571|1072.392|+3.56|+13.51|
|2|18|notify|1069.812|1097.581|+2.60|+17.02|
|2|19|poll|1067.109|992.807|-6.96|+5.44|
|2|20|notify|1094.643|1104.898|+0.94|+13.41|
|4|1|notify|898.355|597.084|-33.54|+10.14|
|4|2|poll|1043.371|563.717|-45.97|+6.74|
|4|3|notify|903.778|645.982|-28.52|+0.65|
|4|4|poll|602.879|579.683|-3.85|+10.69|
|4|5|notify|1139.920|568.608|-50.12|+4.82|
|4|6|poll|1017.378|559.403|-45.02|+2.48|
|4|7|notify|610.054|606.086|-0.65|+1.24|
|4|8|poll|610.748|807.430|+32.20|-7.63|
|4|9|notify|636.804|572.829|-10.05|+7.32|
|4|10|poll|1280.195|576.181|-54.99|-0.88|
|4|11|notify|1189.726|595.090|-49.98|+2.02|
|4|12|poll|642.509|1376.235|+114.20|-0.93|
|4|13|notify|1185.059|694.466|-41.40|+2.59|
|4|14|poll|650.275|607.388|-6.60|+4.97|
|4|15|notify|795.786|690.337|-13.25|-7.90|
|4|16|poll|628.141|615.861|-1.95|-1.76|
|4|17|notify|1441.136|678.872|-52.89|+7.90|
|4|18|poll|641.805|634.014|-1.21|+4.51|
|4|19|notify|777.524|933.368|+20.04|-13.91|
|4|20|poll|1107.506|623.187|-43.73|+3.01|

## Requested UNDO diagnostics

The six separate diagnostic processes retain288 complete untruncated child
traces:74,240 completed purge scopes,zero aborts,three query rseg waits,one
background header-page wait,no matched UPDATE/purge/page relay. Maximum2,465
events/child against8,192. holders.csv is the readable subset; raw traces and
all unmatched scopes are in undo-traces.tar.gz with per-member hashes.

The background page wait is notify cap4 diagnostic child7: purge holds
rseg17881408 and waits for space1/page3,0.113167ms registration->resume.
The entry owner sample is FOR_IO/WRITE_FIX. Eleven IO snapshots in selected
logs are not eleven independent waits or proof of continuous ownership. Thread
values are guest TLS, not OS PIDs; owner identifiers are a distinct domain.
No diagnostic UPDATE>100ms occurred. Poll cap4 diagnostic has one long SQL
block with a short UPDATE, outside this UPDATE-specific attribution. Primary
holder logging is disabled; its tails receive no retrospective owner assignment.
Issue68 remains stopped. No extra diagnostics seek another long event.

## Reproduction and storage

`PYTHONDONTWRITEBYTECODE=1 python3 analyze.py --check` recomputes all tables,
intervals,children.csv and holders.csv read-only from the two archives. Run
test_analysis.py and test_undo.py for bad cap/readback/worker/lifetime/oracle and
identity/overlap join controls. SHA256SUMS.json binds the bundle; raw and UNDO
archive member hashes are separate. Python tooling here is3.9.6.

For fresh execution, prepare a disposable workspace at exact measured d05cd878
source. Copy build.py,plan.json,prior-inputs.json,original-run.py,fixed-run.py and
controller-correction.json into evidence/. Run build.py then fixed-run.py; an
empty records file set starts the fixed protocol from zero, while a verified
completed prefix can resume without repeated combinations. Do not copy saved
records.json for a fresh run. Controller verifies source/binary/plan and its
own correction hash. It does not claim new results equal old timings.

The finite matrix is complete with no notification/guest setting change, heavy
CI, main integration, qualification or release. Exact further CPU attribution
would need a separately chosen bounded observation; it is not an additional
completion condition for this comparison. Build caches/binary/overlays and
redundant uncompressed raw data are disposable after verified preservation.
