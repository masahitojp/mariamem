# Actual C prepared lexer maps: bounded measurement

The actual C candidate improves serial Fork and reduces batch CPU in this
single-Mac campaign. **Ordinary Fork p50 is21.15→19.35ms atP1 (-8.5%) and
28.97→28.21ms atP4 (-2.7%).** P1 improves in all three paired runs; P4 Fork p50
improves in two pairs and regresses in one. P4 whole-batch wall improvement is
not established: a candidate COUNT/SUM tail makes one ordinary batch77.97% longer.
All samples remain included.

Recommendation: take the candidate and this bounded result to adoption review.
The decisive evidence is full both-host actual-guest correctness, repeatable P1
startup savings and lower batch CPU in every paired Fork cell. The strongest
objection is the weak P4 elapsed result and candidate-only SQL tails in this
campaign. Their cause is unobserved; this report neither attributes them to the
lexer change nor clears the change of causality. Do not promise stable P4
end-to-end acceleration or RSS savings. Product integration and release remain
separate Human decisions; independent two-C-build reproducibility is still absent.

[Standalone graph/report](report.html) · [summary](summary.json) · [all primary children](children.csv)

## Ordinary execution (no Go experiment overlay)

| Measure | Baseline | Actual C candidate | Change |
|---|---:|---:|---:|
| Fork P1, per-child p50 |21.15ms|19.35ms|-8.5%|
| Fork P4, per-child p50 |28.97ms|28.21ms|-2.7%|
| Fresh P1, Start p50 |23.24ms|21.27ms|-8.5%|
| Fresh P4, Start p50 |30.45ms|29.44ms|-3.3%|
| Fork P1,48-child batch wall p50 |1249.17ms|1140.93ms|-8.7%|
| Fork P4,48-child batch wall p50 |489.66ms|484.85ms|-1.0%|
| Fork P1, batch CPU p50 |1804.65ms|1705.06ms|-5.5%|
| Fork P4, batch CPU p50 |2424.13ms|2262.18ms|-6.7%|

Per-child p50 pools144 children/cell. Batch wall/CPU p50 uses three processes;
CPU includes SQL and cleanup, not isolated Fork CPU. P1 Fork p50 paired changes
are -9.1/-8.4/-8.8%; P4 changes are -8.9/+5.0/-6.5%. P4 batch-wall changes are
+78.0/-1.0/-7.7%, despite batch CPU falling in all three pairs. Do not interpret
the three-batch median as absence of a slow batch.

Fresh P1 batch wall p50 falls1829.08→1710.19ms; P4 falls695.52→658.21ms.
Fresh Start p50 improves in all three pairs at both parallelisms; complete Fresh
batch time improves in two of three pairs at each. These cases rebuild the seed
per child, whereas Fork cases restore prepared seed, so their total workloads
differ intentionally.

Ordinary process peak-RSS p50 is135.0→135.6MiB atFork P1 and421.1→436.2MiB atP4.
P4 ranges are406.5–559.4MiB baseline and365.9–482.8MiB candidate. Paired signs are
mixed; no RSS reduction is established. These are lifetime process peaks, not
per-child retained RSS or available memory.

## What dominates now?

These are **diagnostic-on elapsed** medians; their sums are not an additive total.

| Stage | P1 baseline → candidate | P4 baseline → candidate |
|---|---:|---:|
| Observed Fork |22.11→20.38ms|32.17→30.44ms|
| Memory preparation |1.83→1.84ms|2.75→2.87ms|
| Server initialization |17.66→16.03ms|24.79→22.08ms|
| Routine schema |0.88→0.90ms|1.01→0.97ms|
| Host outside startup |0.92→0.81ms|1.26→1.35ms|

Server initialization remains dominant. Candidate representative children closest
to each cell's p50 spend16.27/20.38ms (P1) and24.65/30.42ms (P4) there: around80%
of their observed Fork. These are actual single-child ratios, not ratios of
unrelated medians. P4 expands server initialization and memory preparation.
This observer cannot separate common initialization, InnoDB or Aria inside
server_init, and cannot assign stage CPU. Earlier Go-prototype fine-grained
attribution stays under its historical identity.

Observer overhead in Fork p50 is+4.5/+11.0% for baseline P1/P4 and+5.4/+7.9%
for candidate. The observed stage times are not assigned to ordinary off totals.
The existing generic observer has identical before/after hashes in both arms;
all child stages sum to that same child's Fork elapsed time during replay.

## Tails and fixed exit

52 planned processes completed: four correctness/negative controls,12 warmups,
36 primary batches with1728 primary children. Both invalid-seed controls fail as
expected; SQL, child isolation and cleanup pass for all successful processes.
No extra sampling or threshold exclusion was performed.

- Candidate P4 ordinary rep0, child7: COUNT/SUM790.19ms; batch869.04ms versus
  baseline488.31ms. This is the +78.0% wall pair above.
- Candidate P4 diagnostic rep1, child27: COUNT/SUM797.90ms; batch1084.34ms versus
  baseline543.48ms. It is not an UPDATE observation, and no UNDO-owner logging
  was installed in this coarse observer.
- No primary Fork start exceeds100ms. P4 ordinary Fork p95 is36.54→39.46ms.
- Fresh P1 has two >100ms first-child starts in each arm; all are retained.
- No UPDATE exceeds100ms in this campaign. This does not resolve the historical
  SQL-wait investigation or prove that other workloads cannot reproduce it.

## Exact identities and reproduction

AppleM1/16GiB, macOS27.2 arm64; Go1.27.3, CGO0,GOMAXPROCS8,GOGC100, Pipe,
1000 seed rows,48 independent children, explicit cap=P for Fork. Three paired
repetitions rotate cells and alternate arm order. Desktop host, no isolated
performance-runner claim.

- Measured harness source_commit `ac31af58f94b5b732375f4be177d5c8a12e27fc3`.
- Adopted product baseline `3d8b2201c1f36fa5b7264e0450104055f3822272`; its runtime
  bytes equal the canonical baseline in host binding source
  `6134274a268155379329d9bd1ae394897e1f7e8e`.
- C origin `b1a265cc30a8603ced743c8aeb59c752751ff9d6`, reused guest
  `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
- Baseline guest `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- All108 installed C runtime files excluding provenance match successful
  [CI42437059943](../../lexerbinding/ci-42437059943/README.md). The regenerated
  Go1.26.10 dev-smoke host passes locally; measured binaries both use Go1.27.3.
- `inputs.json` retains all four measured binary hashes, build information,
  exact plan and installed/overlay inventories. `binding-validation.json` also
  checks actual module replacement paths and the identical observer code.

`observations.json` is losslessly compressed JSON using the bounded existing
`benchmarks/lexercandidate/codec.py`, with decoded length/hash. It contains all52
reports and all diagnostic child traces. `supplemental-traces.json` preserves96
additional root/capture traces;2304 duplicate child trace files were matched to
the compact records before deletion. The independent CSV is for inspection;
summary/CSV/HTML are reproducible after workspace cleanup:

```sh
python3 benchmarks/lexercmeasure/analyze.py \
  --input benchmarks/lexercmeasure/results/observations.json \
  --output benchmarks/lexercmeasure/results --check
python3 benchmarks/lexercmeasure/report.py --check
python3 -m unittest discover -s benchmarks/lexercmeasure -p test_analysis.py -v
```

Replay rejects missing/duplicated trials, missing children/traces, wrong labels,
cleanup debt, wrongly successful negative controls and inconsistent phase
accounting. Per-repetition pairing has a separate regression control. The
post-measurement build helper adds an assertion equivalent to the independently
recorded module-path preflight; it does not change or relabel measured binaries.
The initial sandbox sysctl denial occurred before any guest process. See
`preflight.json`. Runner/workspace paths in logs are normalized with
original/published hashes. Recreated source, binaries and caches are disposable.
