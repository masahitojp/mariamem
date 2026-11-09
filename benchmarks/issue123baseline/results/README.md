# v0.6.2 / current main / static-page sharing: common lifecycle baseline

**Conclusion:** current main is substantially faster than v0.6.2 on this fixed
48-case workload. The rebased Issue123 prototype adds a repeatable P4 Fork-suite
benefit, but is not an unconditional improvement: P1 Fork suites usually become
slower and process high-water RSS rises. Recommend retain this cohort as the
current comparison baseline and continue the bounded #123 candidate discussion,
carrying cold creation, RSS and lifecycle ownership into review. Do not adopt it
universally or infer that P4 results apply to every fixture/platform.

The decisive #123 result is P4 Fork suite wall−6.96% and CPU−7.38%, both5/5 paired
improvements, including the first image build. The strongest objection is the
P1 tradeoff: wall+2.47% (only1/5 faster), CPU+2.29%, approximately38–44ms image
creation per new process, and substantially higher lifetime high-water RSS.
The old isolated-wave result is not relabeled or substituted for this result.

## Fixed sources and mechanism

- Baseline source_commit `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`, v0.6.2
  tag_object_sha `cebdb4114187171bd418b0a1b419e1c27368808d`.
- Current product source_commit `279fa530d03cab1bd025df91bf5130bbf845a721`.
  Includes adopted UCA, disconnect notification, CRC32C, prepared lexer and
  normal startup global concurrency. Buffer pool16MiB/read1 remain unchanged.
- Candidate and harness source_commit `89aad11a7ce5fd4848b464b8dcfa9430ea607bbe`.
  Candidate guest bytes are identical to current main:
  `8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df`.
- Prototype ancestry and original harness refs are in plan.json. Current and
  baseline binaries link pristine source archives; candidate uses the same
  workload with only the private experiment entry enabled. Their library source,
  original guest identity and executable hashes are separate fields in inputs.
  All three are freshly compiled with Go1.27.3; this does not time the shipped
  Go1.26.10 baseline binary. No product setting or SQL changes between arms.

The existing static-page prototype was transplanted, not wholesale-merged. Only
newMemoryModule's experimental branch, its private adapter and page mapping helper
change runtime behavior. No change to guest, generated data/CRC/lexer bodies,
public API, converter or release metadata. Metadata pins were updated from the
old guest: globals[8388608,18012928], DataEnd18013433, init flag26996016. TLS accessor
Fn68 still matches the inspected current source. Full byte/state equality, not
these constants alone, checks the new binding.

The image contains only guest-before-Start data initialization, not an initialized
MariaDB engine. New modules keep independent memory, globals, function table,
locks, thread state and host imports. A sparse, unlinked read-only backing file
is mapped MAP_PRIVATE over22 initialized OS-page ranges,8,929,280 bytes
(8.515625MiB on16KiB Mac pages). Remaining memory stays anonymous with the existing
logical Grow/PROT_NONE contract. The init flag after DataEnd is included. No
whole-file mapping arm, no8MiB buffer pool, no CRC or lexer change is introduced.

## Workload and execution

Apple M1/16GiB/macOS27.2, Go1.27.3, CGO0, GOMAXPROCS8/GOGC100, Go Pipe. Same
1,000-row seed, COUNT/SUM, committed update and verification,48 independent
children per suite. Fresh prepares each DB; Fork prepares/captures one root and
uses MaxForks=P. P1/P4 use ordinary mixed worker lifecycles, not synchronized
waves. Both routes retire pools, WaitDisconnected, and fully Close each DB.

Five rounds rotate four mode/P cells and the three arms inside each cell.
All60 primary processes/2,880 children are retained.12 positive/negative control
processes and12 full48-child warmups are separate:84 total processes,3,474 child
records, six deliberate oracle failures. There are no extra repeats, failed
primary retries, outlier exclusions or new internal owner/timing overlays.

Suite time starts before the first Start and ends after all children, root,
Snapshot and candidate image-factory disposal. First image construction occurs
inside each candidate process, never prewarmed by another process or omitted.
Compilation, Go process initialization and JSON output are excluded; external
wall is separately retained. Ordinary desktop VM/services and the workspace disk
guard remained active. Preflight found no unrelated Go build/test campaign;
this is a paired local observation, not an isolated-machine result.

## 0.6.2 to adopted current main

Times are medians of five process metrics. Percentage is median of five paired
changes, not necessarily the ratio of two column medians.

|Route/P|v0.6.2 suite ms|Current suite ms|Paired wall|Paired CPU|Current faster|
|---|---:|---:|---:|---:|---:|
|fresh-p1|2731.046|1844.586|-32.37%|-16.74%|5/5|
|fresh-p4|1013.179|758.213|-27.23%|-20.64%|5/5|
|fork-p1|2587.158|1302.282|-50.33%|-35.50%|5/5|
|fork-p4|1035.856|605.871|-41.51%|-42.62%|5/5|

All20 baseline/current suite pairs improve, with CPU also lower in all20.
Typical Fork startup process-p50 median is40.52→21.35ms/P1 and59.20→32.47ms/P4.
This directly measures the combined adopted result; it does not add percentages
from UCA/CRC/lexer/notification studies or assign exclusive causal contributions.
Current Fork suites are faster than Fresh in this cohort (1302.3 vs1844.6ms/P1;
605.9 vs758.2ms/P4). This ordering remains workload-dependent.

## Current main to Issue123 prototype

|Route/P|Current suite ms|Pages suite ms|Paired wall|Paired CPU|Pages faster|
|---|---:|---:|---:|---:|---:|
|fresh-p1|1844.586|1844.534|+0.78%|-0.44%|2/5|
|fresh-p4|758.213|777.713|+0.06%|+0.04%|2/5|
|fork-p1|1302.282|1337.845|+2.47%|+2.29%|1/5|
|fork-p4|605.871|563.715|-6.96%|-7.38%|5/5|

|Route/P|Current Start/Fork p50 ms|Pages p50 ms|Paired change|Pages faster|
|---|---:|---:|---:|---:|
|fresh-p1|23.950|23.327|-1.68%|5/5|
|fresh-p4|33.803|32.184|-6.58%|5/5|
|fork-p1|21.350|21.181|-0.74%|3/5|
|fork-p4|32.469|29.455|-7.33%|5/5|

P4 Fork suite pair changes:−9.84,−1.99,−0.84,−6.96,−7.23%. P1 Fork suite changes:
+1.28,−1.20,+2.47,+3.36,+3.38%. Fresh suite results are mixed and do not establish
a benefit. Fresh P4's last candidate pair is8.53% slower and remains included.
No primary SQL span exceeds100ms in any arm; this cohort is not dominated by the
old400/800ms SQL tails and does not establish their elimination. Startup/Close
p95/counts and every source-bound child span remain in the compact data.

Image construction process medians are38.4–40.7ms across the four cells. P1 root
Start is35.30→75.32ms and P4 root Start37.85→72.68ms. Initial work therefore remains
a visible cost. The P4 whole-suite benefit already includes it; P1 savings do not
recover it consistently. Do not add independent phase medians to invent totals.

## Resource limits and correctness

|Route/P|Current lifetime high-water RSS MiB|Pages lifetime high-water RSS MiB|
|---|---:|---:|
|fresh-p1|135.312|278.844|
|fresh-p4|395.531|380.359|
|fork-p1|136.938|278.484|
|fork-p4|401.078|442.219|

These are whole-process lifetime maxima, including transient image construction,
not retained-child RSS, PSS or a memory-allocation census. In particular P1's
approximately137→278MiB prevents claiming a general memory reduction from this
campaign. Old held-child RSS savings stay bound to the old source; they were not
repeated here. The exact owner of the high-water change was not instrumented.

- Full initial256MiB bytes hash/equality, mutable globals, DataEnd, dropped segments,
  independent sibling/runtime state, read-only backing and surviving child after
  factory Close pass on current guest. Removed init-flag page is detected.
- Worker TLS, stable-address zero-filled Grow, failed/beyond-max Grow, OS guard
  fault and join-before-free pass. Concurrent first acquisition builds once;
  Close/admission and read-open/writer-close/map/cache-close/metadata failures
  preserve their test ownership checks. Range/alignment/overflow/overlap and
  mid-overlay cleanup debt tests pass. No tests were skipped for page-only mode.
- All78 expected-success runtime processes pass SQL, committed mutation, pristine
  isolation, finite cap and final disposal; all six wrong-seed controls fail as
  expected with cleanup. Every process ends with zero mappings/reserved/RW bytes
  and release failures. Candidate image is built once, closes its owned FDs,
  leaves no scratch path, and primary acquisition counts are48 Fresh/49 Fork.

This is Mac source/constructor/real-guest evidence, not Ubuntu correctness,
native SQL differential coverage or release Qualification. No main merge or
product adoption was performed.

## Recommendation and next boundary

Keep this as the current-main speed baseline. #123 now has ordinary mixed P4
suite evidence on current source, beyond its historical fixed-wave evidence.
Continue toward a bounded candidate review only with the P1/cold/RSS tradeoff
explicit. These results do not justify silent default activation.

Before product adoption, define process/factory lifetime and final disposal,
error ownership and entry selection; move the experiment-only adapter/benchmark
factory into installer-owned minimal product code if chosen, bind generation,
and verify both supported hosts. Current candidate uses a private environment
switch and explicit harness factory Close; it is not already a production-ready
public lifecycle. Do not make arbitrary repeated sampling or zero-tail results
new completion conditions. A decision to defer due to the observed tradeoff is
also a valid end to this finite comparison.

## Evidence, replay and reproduction

`python3 benchmarks/issue123baseline/results/analyze.py --check` reads only this
bundle, recomputes summary and validates SHA256SUMS without writes or deleted
workspace inputs. Four negative replay controls reject a false oracle, a retained
mapping, a missing process and a falsified summary even when transport hashes
are rebound; results are recorded in replay-controls.json. observations.json.gz decompresses byte-for-byte to the original
84-process collection; publication.json binds original/published hashes. It
retains all primary, warmup and negative records and all child spans. Compact CSV
and the standalone HTML are convenience views, not alternative numeric sources.

Reproduce in a disposable worktree at the measured source with Go1.27.3. Use
10GiB free reserve/12GiB owned budget and run:

```
python3 scripts/experiment_workspace.py run --timeout 2400 NAME -- \
  python3 WORKSPACE/worktree/benchmarks/issue123baseline/campaign.py
```

The source/tag identity helper runs before builds; the runner asserts clean source,
allowed runtime delta, current generated-source hash and guest identity. It
archives both reference libraries, runs mapping/constructor controls, builds
three ordinary binaries and executes the fixed84 processes. Runtime environment
and exact order are in plan.json/run.py; build GOGC50/GOMEMLIMIT3GiB differ from
measurement GOGC100/unset GOMEMLIMIT and are excluded from timings. No owner
observer is applied to mismatched guest versions. Build times123.0/119.1/114.5s
are overhead only. Subsequent source changes are report/replay tooling only.

Useful source and the compact report remain on the experiment branch. Full
per-process duplicate files, generated archives, binary/cache/temp and the clean
worktree are disposable after lossless reduction and source preservation. No
benchmark evidence is automatically merged into main.
