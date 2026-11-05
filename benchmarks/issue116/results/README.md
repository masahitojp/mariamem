# Issue116: bounded rootRead clear prototype

**Recommendation: stop this round; do not recommend adoption on the fixed criteria.** Correctness and the redundant-write mechanism pass, but the predeclared P4 Fork/CPU criteria and batch-wall guard do not. No extra repeats, post-hoc filtering, threshold changes or automatic platform campaign were added. This does not prove the local source change is unsafe or that no smaller benefit exists.

[Graph](report.html) · [Process CSV](processes.csv) · [Machine-readable gates](summary.json) · [Input/overlay identities](inputs.json) · [Pre-run criteria](issue116-pre-run-spec.md)

## Primary results — no timing or byte counters

Five alternating fresh-process pairs per P,48 children/process, Go Pipe, explicit cap=P; one separate warmup per cell. Improvements below are **medians of paired changes**, not ratios or differences of independent medians. Positive means candidate lower/faster. All trials and SQL tails retained.

| Metric | P4 | P8 |
|---|---:|---:|
| Fork p50 saved, paired median | 0.308 ms (0.80%) | -0.168 ms (-0.28%) |
| Fork-winning pairs | 5/5 | 2/5 |
| Batch CPU/child reduction | 2.79% | 0.34% |
| CPU-winning pairs | 3/5 | 3/5 |
| Batch wall reduction | 29.57% | -14.56% |

P4 Fork gate required ≥1ms AND≥3% with≥4/5 wins: **FAIL**, despite5/5 direction. P4 CPU required≥3% with≥4/5 wins: **FAIL** (2.79%,3/5). P8 Fork/CPU≤5% regression guard: PASS. Batch wall≤5% regression guard: **FAIL** at P8 (paired median14.56% slower, all five pairs slower). These are the fixed exploratory decision criteria, not a statistical significance test.

Independent cell medians are provided for orientation only; do not use their subtraction as the paired effect:

| P | Variant | Fork p50 ms | Batch CPU/child ms | Batch wall ms | SQL>100ms /240 children |
|---|---|---:|---:|---:|---:|
| 4 | baseline | 38.652 | 67.582 | 1050.2 | 3 |
| 4 | candidate | 36.795 | 67.004 | 673.0 | 0 |
| 8 | baseline | 60.269 | 72.827 | 584.1 | 3 |
| 8 | candidate | 59.131 | 72.611 | 938.8 | 5 |

P4 baseline has three>100ms SQL spans and candidate zero; P8 baseline three and candidate five. Thus P4 batch-wall improvement alone is not evidence of Fork acceleration. P8 wall worsens in this finite cohort, but it is not established that avoiding clear causes SQL stalls. Neither tails nor entire processes are removed to rescue the gate. CPU/child is whole batch process CPU divided by48, not exclusive Fork CPU.

## Mechanism and server_init prediction

Concurrent8-child candidate pilot: avoided prefix clear52,127,544bytes total,6,515,943bytes/child (6.21MiB), exceeding1MiB gate. All are inherited block bytes; mapped fallback0. This counter is candidate batch read work divided by children, not an exclusive Fork-only/RSS measurement. Baseline counters count potential removable prefix bytes; candidate counters count bytes actually not cleared. Different background read sequences mean totals need not be equal across processes.

Source inspection corrected the original hot-path explanation before measurement: FrozenFile.Fork inherits sealed heap blocks, so normal reads reach Block.ReadAt via rootRead. The candidate changes rootRead callers only: copies valid prefix and clears suffix for inherited blocks and mapped fallback. General Block.ReadAt and other callers are unchanged. Holes, invalid suffixes and EOF semantics remain required. No clear is skipped merely because a destination is presumed zero.

Separate stage diagnostics: three alternating pairs/P with the same observer and byte counters enabled in both variants; never used to pass primary timing gates. Each process value is mean server_init duration over48 children. Paired median savings:

| P | Prediction fixed before measurement | Observed paired median | Per-pair savings ms |
|---|---|---:|---|
| 4 | 1–3ms | 2.178 ms | -0.047 / 3.382 / 2.178 |
| 8 | 2–5ms | 2.840 ms | 2.840 / 2.936 / -16.907 |

The predeclared P4 attribution criterion (≥0.5ms paired median and≥2/3 improving) passes:2.18ms,2/3. This is consistent with the location hypothesis under diagnostics, not proof of the same saving in ordinary operation. P8 has one large opposite-direction result (−16.91ms); preserve it and avoid calling the prediction stable. Memory reserve/construct paired median savings are0.045ms P4 /0.090ms P8, consistent with no targeted constructor change.

## Correctness and source binding

Both baseline and candidate run the entire focused internal/prepared unit package. New dirty-destination oracles cover mapped/partial mapped/hole/inherited/partial block/dirty block, unaligned and cross-block offsets, negative offset, zero length, short read and EOF with untouched output tails. A mapped truncate→grow→Seal→two-child case checks zero suffix and sibling independence. Existing reference-storage/capture/corruption/ownership tests run in both modes.

All positive runtime SQL/pristine-seed/update/independence/cleanup checks pass. Two intentionally wrong-seed controls fail the intended oracle and clean up.40 fresh processes:20 primary,12 diagnostic,4 warmups,2 concurrent positive pilots,2 negative controls. No failed primary or extra favorable repeat is hidden. Active-child interval census matches cap.

Product source_commit1862f4a89397bddfa1820d835106d3437a438cf7; guest6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe. Measured harness source_commitd77a51193901de44f28e284f870530d270faf64b; clean commit-object identity checked with git_identity before build. Source diff from product is benchmark tooling only. Runtime observer and rootRead change are named, hashed build overlays. One exact binary runs both variants, selected at process startup by experiment-only host variable; no switch is forwarded to guest. Only additional atomic counters are disabled for ordinary timing; the same selection branch exists in both variants. Normal runtime flags/config/SQL and public API are unchanged.

Apple M1 /16GiB/macOS27.2, Go1.27.3, CGO0, GOMAXPROCS8, GOGC100; one local host only. Guest is the adopted prepared-UCA candidate, not published0.6.2. Pipe avoids TCP for SQL; ordinary listener creation remains. Root prep/capture/final Snapshot close are outside batch; child connection retirement/WaitDisconnected/Close are inside. No retained-child RSS was measured.

## Reproduction and retention

All unique observations and build/unit logs plus build.py/run.py/analyze.py are compacted into receipts.zip; input and overlay hashes are in inputs.json. Extract ZIP into an empty directory and run `python3 analyze.py --check` to verify exact matrix, summaries/CSV and gates read-only, with missing-cell/variant rejection controls. To rerun, use measured harness d77a5119, generate benchmarks/issue116/overlay.py and follow archived build.py/run.py in their recorded disposable layout. Source guards reject a later report commit intentionally. New timings are new observations. Pre-run fixed thresholds are in measured plan.json and the saved Issue text; the text was copied to evidence after measurement from the specification submitted before execution.

No guest rebuild, canonical product edit, public API change, integration, CI submission, Qualification or release. The bounded result is complete; any adoption of a smaller mechanical benefit would require a separately explicit Human decision rather than relabelling this failed criterion as PASS.
