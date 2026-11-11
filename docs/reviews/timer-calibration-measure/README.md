# Timer probe omission: startup improves, suite benefit not established

**The bounded prototype reduces Fresh/Fork startup in this Mac cohort. It does
not yet establish faster complete test execution.** Keep it as a startup candidate
for a separate adoption review; subsequent platform confirmation is recorded
below. The strongest concern
is that P8's five-run suite median is higher despite three of five paired suites
being faster; sample-loading tails remain in both arms. Do not call this uniformly
faster or regression-free, and do not silently discard the slow runs.

The original question was whether the roughly1ms timer characterization region
could be shortened without breaking timekeeping. The generated code contains the
intended bypass; actual SQL timing remains valid; sequential API startup falls
about1.8–1.9ms in every paired batch. No exclusive timer-stage measurement ran in
these binaries, so that delta is an API-level observation, not a claimed exact
partition of the earlier instrumented1ms estimate.

## Human decision, 2026-11-11

The Human accepted the recommendation to **retain this startup-improvement
candidate**, on the basis of record `37e08920ccd8fcdb478821f8302280fde2ae438e`.
[Decision record](human-decision.json). This accepts preserving the bounded
prototype and evidence; it does not authorize main integration, product adoption,
Qualification or release. The complete-suite limitation and all source-bound
receipts remain unchanged. Ubuntu runtime/platform confirmation and native SQL
comparison precede a separate adoption review. No new runtime or benchmark result
is claimed by this documentation-only decision update.

## Subsequent Ubuntu/native confirmation, 2026-11-11

[CI42940198738](https://github.com/masahitojp/mariamem/actions/runs/42940198738)
passed at orchestration commit `6c654011`, host source `f225968c` and guest
source `1731c394`. The [checksum-verified receipt](ci-42940198738/README.md)
closes the bounded Ubuntu runtime and native SQL comparison tasks for this
combined clock-correction/probe-omission candidate. It does not relabel earlier
clock-only receipts, establish Ubuntu performance or approve product adoption.
The historical Mac result and limitations below are unchanged.

## Result

Same Apple M1/16GiB, macOS27.2 arm64, Go1.26.10, GOMAXPROCS8/GOGC100. Corrected
SQL clock in **both** arms; candidate adds only the bounded millisecond-resolution
probe omission. Real clock reads, frequencies, native/fallback paths,16MiB buffer
pool and read1 are unchanged. The two arms ran alternately with reversed order. This was not a dedicated or
CPU-affinity/frequency/thermal-isolated host; alternation does not remove every
scheduling or temperature effect.

| Sequential API metric | Probe retained | Probe skipped | Change | Faster paired batches |
| --- | ---: | ---: | ---: | ---: |
| Fresh wall |20.794ms|18.847ms|−9.37%|6/6|
| Fork wall |18.555ms|16.776ms|−9.58%|6/6|
| Fresh CPU |31.507ms|29.492ms|−6.40%|5/6|
| Fork CPU |31.549ms|30.124ms|−4.52%|4/6|

These are medians of six batch medians. Each batch has8 Fresh and16 sequential
Forks;48 Fresh and96 Forks per measured arm. One separate warmup process per arm is
excluded explicitly. The first Fresh in each process includes lazy static-image
setup; subsequent calls reuse it. This table is not a cold-install metric.
All observations, including those first calls, survive in the retained data.
Pooled Fork wall p95 is21.312→17.726ms. CPU is process CPU across threads and can
exceed elapsed time. Pair ordering and individual deltas are in `summary.json`.

| Go Pipe shop70 | Probe retained | Probe skipped | Change of medians | Faster paired suites |
| --- | ---: | ---: | ---: | ---: |
| P4 complete wall |570.689ms|577.152ms|+1.13%|2/5|
| P8 complete wall |572.549ms|666.411ms|+16.39%|3/5|
| P4 complete CPU |2182.538ms|2236.935ms|+2.49%|—|
| P8 complete CPU |2459.850ms|2408.929ms|−2.07%|—|

Five paired suites per parallelism/arm, plus one warmup. Shop70 means50 reads on
one shared child and20 private write children (21 Forks), with schema/master seed
in the Snapshot and per-child sample data. Admission cap=P+1. Whole wall includes
Fresh/import/Snapshot/tests/cleanup. It is **not a48-child batch**. Workload SQL is
the prior pinned harness; no internal timing/guest diagnostic observers are on.

P4 child Fork pooled p50 is24.241→23.928ms; P8 is31.132→28.714ms. Thus the
sequential gain is not a promise of an equal per-child gain under concurrent SQL.
AtP8, sample-load p50 is73.293→73.175ms, while **both arms have7/105 sample spans
above100ms**. Maxima are477.951/444.134ms. These delays occur outside the measured
Fork span; their causes were not instrumented here. Similar counts do not imply
identical impact on the suite's critical path. P4 has no sample spans above100ms.
All tails remain. Five pairs cannot resolve a small end-to-end effect against
these variations; neither uniform acceleration nor a proven P8 regression is
established. No follow-up repetitions were selected after seeing the outcome.

## Correctness and exact sources

- Guest CI [42928025946](https://github.com/masahitojp/mariamem/actions/runs/42928025946)
  passed at `1731c394031b781ff813190bf9c42bee63516044`. Its two archive digests,
  job identity and UNQUALIFIED scope are in [ci-receipt.json](ci-receipt.json).
- Candidate guest SHA256:
  `a64b581154d7d1ca2ca8aae9a552c9433f7f1354b7c7f5a36d600b62a32d2c18`.
  Baseline corrected-clock guest:
  `b68fce3a4785f5a9dd858c96572ed0a765ee4352715b416cdf168784054b4fc6`,
  originally CI42916730601 / source9a3e91b7, archive13810237295 /
  SHA256`2b4e877949d18deb84e89f19cce46e96724efdc152d7aeef319de1cc87df057e`.
- Host source: baseline `7383940e8bd3fbaf4b0a2ff49d28f669ba92e6b2`, candidate and
  identical comparison harness `f225968c332a692f5bce189b31aed1fab26e642a`.
  Original Go workload source80903680 is pinned in
  [harness-origin.json](../../../tests/timer_calibration/harness-origin.json).
- Full initial data, CRC body/table and three thread-lifetime bodies match the
  old strict bindings. [Compiled branch](compiled-path.json) checks routine11,
  runtime cycles0 and nominal resolution1; the fallback loop remains present for
  other runtime conditions. [Binding](binding.json) changes identity selection
  only; complete-body/data/ownership checks remain active. Ten binding unit tests
  pass for the original and new exact guest identities.
- [Host comparison](host-source-comparison.json) confirms157 host/SDK files and
  all handwritten generated-runtime glue identical; runtimekind changes only its
  exact guest SHA. Per-arm host/runner receipts include actual binary hashes,
  generated inventory hashes, identical harness inventories and Go build info.
  The baseline host rebuilt to the exact prior binary hash.
- Both arms passed the existing transaction/Snapshot/three-child smoke and the
  separate PyMySQL/TCP Fresh/two-child timing oracle. Eighteen following SELECTs
  per arm, child isolation, host exit0, pipe/reader/reference/directory cleanup
  pass. Both Go Pipe binaries then passed three delayed/ordinary ANALYZE pairs,
  following SELECT, zero active mappings and empty owned scratch **before** timing.
- All38 warmup/measurement processes pass: lifecycle baseline isolation, shop
  counts/settings, zero active mappings and empty scratch. No runtime retries.
  The earlier CI/local receipts retain their original source identities.

The only intended metadata difference is **nominal1ms resolution**, not a measured
host/scheduler guarantee, in the WASI/no-PFS/monotonic/no-cycles profile. Native SQL
comparison and Ubuntu runtime were separate at this measurement checkpoint;
the subsequent confirmation above closes those two bounded correctness tasks.
Ubuntu performance and product adoption remain separate.
No main integration, Qualification or release was performed.

## Reproduction and retention

`python3 docs/reviews/timer-calibration-measure/analyze.py --check` replays the
retained minified JSON without temp directories and without overwriting evidence. The
summary and all compact files are checksummed. `assessment.json` states scope
and the two pre-execution setup corrections; neither was a runtime retry.

For a new authorized run: prepare two budgeted workspaces, baseline at7383940e and
candidate atf225968c, named `timer-measure-baseline` and
`timer-calibration-measure` under one owned parent. Copy `reproduction/*.py` into
the candidate workspace's `evidence/`; their relative paths then resolve to that
workspace. Acquire and validate both exact artifacts (`acquire.py`), use Python3.14
with pytest9.1.1/PyMySQL1.2.0, inspect candidate translation with `translate.py` and
`inspect-binding.py`, and run the two guarded development builds. Compile both
runners with `compile-runner.py baseline|candidate`, then `run-pairs.py`.
`collect.py` reduces identities. Losslessly decompress the runner's gzip into
`observations.json` for the public-source evidence set; `observations-storage.json`
records original/published hashes. Then run the retained `analyze.py`. Use the existing workspace/disk guard with the
[recorded budget](plan.json); no build runs during measurement. Source identity
must be clean and verified before compilation; do not hand-edit generated code.

The runner records all38 processes plus two separate Pipe correctness processes;
comparison analysis reports6 warmup and32 measured processes. Preserve raw compact
observations, scripts, receipts and checksums; dispose of Wasm archives, generated
source, binaries, venv, compiler caches and worktrees. Experimental history is not
a production candidate to merge wholesale.
