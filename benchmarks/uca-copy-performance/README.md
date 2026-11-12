# Default UCA private-copy: observer-off Mac comparison

**Conclusion: startup work decreased, but this candidate is not yet supported as
an overall acceleration at P8.** Recommend preserving the candidate and reviewing
the P8 sample-insertion tail before adoption. The decisive objection is that four
of five candidate P8 batches were slower, even though Fork wall/CPU improved in
all six isolated lifecycle pairs. This is a single-host bounded result, not proof
that the UCA change causes the tail or that all workloads regress. No extra runs
or tail removal were performed to obtain a better result.

The Human authorized this comparison after bounded correctness passed on
[Ubuntu](../../docs/reviews/issue154-uca-data/ci-43137408120.json) and
[Mac](../../docs/reviews/issue154-uca-data/ci-43148033625.json). Product adoption,
main integration, Qualification and release remain separate.

## Fixed inputs and observed environment

[Plan](plan.json), [host](host.json) and runner identities bind baseline
`500020e7dc6d702ef059f0e73a4bab738103b774`, experimental guest origin
`f43257225e1fd65c58ea8f5d7b220c3a509c203b`, measurement checkout
`30faae54dd62399095616e9b6996fb2d8ec86132` and immutable harness `d24087ee`.
The product Go/SDK sources are equal before installing the guest and its exact
bindings. Both runners use Go1.26.10, Pipe, Apple M1/macOS27.2 arm64/16GiB,
GOMAXPROCS8/GOGC100, buffer pool16MiB/read1, cap=P+1. Guest diagnostics are off;
host benchmark timing spans remain enabled equally in both arms.

Each lifecycle process starts8 Fresh DBs and16 sequential Fork children. There
are six measured pairs. Each full suite uses50 shared-child read cases and20
private-child write cases (21 children, not70 independent Forks). P4/P8 each have
five measured pairs; arms and parallelism order alternate. Six separate warmup
processes are retained but excluded from measured summaries. No retries.
All38 warmup/measured processes passed SQL and confirmed disposal; mapping counts
returned to zero and owned scratch was empty. Both Go Pipe ANALYZE route checks
also passed before timing. Compilation/downloads are excluded.

## Results

The first two numeric columns are medians of batch summaries. The paired-percent
column is the median of per-pair changes, so it need not equal the percentage
change between the displayed medians. Negative means candidate is faster.

| Metric | Baseline | Candidate | Median paired change | Faster pairs |
| --- | ---: | ---: | ---: | ---: |
| Fresh wall | 18.816ms | 17.717ms | -5.83% | 6/6 |
| Fresh CPU | 28.826ms | 27.807ms | -3.26% | 6/6 |
| Fork wall | 16.685ms | 15.596ms | -6.76% | 6/6 |
| Fork CPU | 28.415ms | 27.077ms | -4.65% | 6/6 |
| P4 full-suite wall | 545.873ms | 521.528ms | -5.04% | 4/5 |
| P8 full-suite wall | 454.041ms | 673.845ms | +36.90% | 1/5 |

P4 suite CPU medians are2126.704→2020.526ms; P8 CPU2406.492→2387.870ms.
The P8 elapsed regression is not accompanied by a comparable CPU increase.
Lifecycle Fork improvement is1.0–1.2ms in every pair; it does not remove the
whole previously traced2.21ms UCA region. We did not trace internal stages here,
so attributing the exact saved milliseconds to individual UCA functions would
exceed this measurement.

## P8 tail attribution, without another experiment

| Arm | Fork p50 / p95 | Sample p50 / p95 | Sample >100ms | Batches with a sample >100ms |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 30.20 / 40.67ms | 71.04 / 92.83ms | 1/105 | 1/5 |
| Candidate | 26.77 / 41.22ms | 68.28 / 98.16ms | 5/105 | 4/5 |

No Fork exceeded100ms in either arm. The four slower candidate P8 batches contain
sample-insertion maxima445–483ms; the one affected baseline batch reaches491ms.
The sample span follows Fork and includes loading each child's sample data. It
is not snapshot copying or server initialization. This observation locates the
long wall interval, but it does not identify its lock owner, SQL statement or
establish causation by this patch. Do not relabel it as the previously observed
UNDO wait without evidence. Faster startup could change overlap/timing; that is
only a hypothesis. [Per-batch tails](p8-tails.json) retain every batch.

## Resources and size

Peak RSS is the **whole process maximum**, measured by `/usr/bin/time -l`; it is
not retained memory per DB and not proof of a leak. Median (maximum of5 runs):

| Parallelism | Baseline peak RSS | Candidate peak RSS |
| --- | ---: | ---: |
| P4 | 428.62 (441.70)MiB | 449.19 (530.83)MiB |
| P8 | 706.33 (711.94)MiB | 715.44 (750.75)MiB |

No RSS reduction is established. Initialized data end grows749632bytes; the
page-aligned static image envelope grows749568bytes. Initial linear-memory
capacity remains256MiB. Runner executable grows759552bytes. [Sizes](sizes.json)
retain the exact values. The change saves construction CPU while keeping ordinary
per-DB allocations/copies; it does not share mutable per-child UCA data.

## Input check interruption and measurement isolation

The initial build-only check stopped because it required complete generated
inventory equality, including `provenance.json`. That file hashes installation
inputs containing local paths. Every other generated file (code/data/layout/tests)
matched Mac CI exactly. The local provenance's own input digest, guest, contract
and listed file hashes were verified separately; the existing installer input
guards remained unchanged. The built host SHA256 also exactly matches Mac CI:
`05ccab0bf7ad40cb07c685392cbe70ec71550c52e7e486cf8c8243d4c662033e`.
The same installed output was reused; no guest rebuild, runtime patch or failed
performance sample was hidden. [Difference record](installation-metadata-difference.json).

Recursive disk scanning during compilation consumed observable host CPU.
Therefore timed processes ran after both builds/guards exited, with disk checks
between processes and150-second per-process watchdogs. No recursive guard scan
ran concurrently with a measured child. Storage stayed within8GiB/free6GiB.

## Reproduce and finite exit

`python3 benchmarks/uca-copy-performance/analyze.py --check` reads only retained
CSV and verifies the summary; no temp directory or evidence mutation is required.
`batches.csv`, `lifecycle.csv`, `stages.csv` retain every observation used by the
summary, including warmups. Full console logs, duplicate generated source, REST
payloads and raw trace JSON are not committed. Checksums bind the compact set.

For execution, use a clean disposable workspace with worktree/temp/evidence,
copy the reproduction scripts into evidence, and obtain the original authenticated
guest/translation ZIPs and Mac installation receipt referenced by the execution
stage. Check out the original guest source at temp/origin using Git. `build.py`
uses existing verified installers and the exact immutable harness; supply
`--reuse-installation` only for the already-verified output from that same source.
Build to completion before running `run-pairs.py`; use between-process disk checks,
not a recursive scan concurrent with timing. `compact.py` and `extend-summary.py`
produce and verify the compact report. Artifact unavailability is a missing input,
not permission to substitute a different guest.

This completes the fixed measurement campaign. Recommend a separate, bounded P8
sample-wait attribution decision before adoption, retaining the demonstrated
startup benefit and the adverse P8/RSS observations together. No additional
performance campaign, product adoption or integration was started here.
