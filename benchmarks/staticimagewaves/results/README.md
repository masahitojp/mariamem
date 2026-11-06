# Issue123: fixed four-Fork waves

**Conclusion:** with fixed four-Fork waves, the static-page image shortens both
per-child Fork and four-ready completion at P4. The isolated timing/CPU screen
passes. Proceed toward a reviewed candidate/platform verification, keeping the
previous mixed-lifecycle result and first-Start cost explicit. This is evidence
for an initialization benefit, not a new overall product-adoption PASS.

The decisive evidence is five ordinary alternating pairs: all five improve for
both child Fork p50 and four-ready wave p50, with paired medians−4.31% and−4.59%.
Wave Fork process CPU is effectively unchanged (−0.14%). The strongest objection
remains the workload boundary: this intentionally synchronized schedule does not
show that every ordinary parallel suite becomes faster. Earlier mixed P4
results and root-start overhead are not superseded, and Ubuntu is unverified.

## Exact scope and outcomes

Tested source `007f291ea2ab6a6cdf4b9328379f7bd951bd6292`, unchanged guest SHA256
`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
Mac M1/16GiB, Go1.27.3, Pipe, cap4, GOMAXPROCS8. Same ordinary binary across both
arms; same separate diagnostic binary across both diagnostic arms. The image
loader and guest-input files are byte-identical to the prior tested source
`69181862b141aa71f25b5ecaa16a500301d15dd9` (loader-identity.json).

18 valid processes /688 children. All16 positive processes pass SQL/cleanup;
both corrupt-seed controls fail as expected with cleanup complete. Every valid
process ends with zero active/reserved/RW mapping counters and image-owned FDs.
All172 waves obey start, all-ready-before-connect and full-cleanup-before-next-wave
boundaries. The96 separately instrumented children retain matching stage and
UNDO-owner records, no truncation; their host phases add back to measured Fork.
Retained replay and eight negative controls pass.

There was one earlier harness attempt: four pilot/negative processes,16 children,
no primary measurements. Eager cancellation of peer SQL after an expected oracle
failure made one child Close report unusable/EOF, although all resources were
released. The wave coordinator was corrected to join/dispose all peers before
canceling, and the race test now checks that peer contexts remain live through disposal.
Original failed-attempt reports/logs/identities are preserved separately. Actual
runtime accounting is22 processes/704 children. There are no additional valid
performance repetitions or discarded timing samples. See attempt-summary.json.

## Ordinary fixed-wave results

| Ordinary P4 metric | Anonymous | Static pages | Paired median change | Improving pairs |
|---|---:|---:|---:|---:|
| fork_p50 (ms) | 33.321 | 31.705 | -4.31% | 5/5 |
| fork_p95 (ms) | 39.285 | 36.262 | -7.70% | 5/5 |
| wave_ready_p50 (ms) | 36.522 | 34.530 | -4.59% | 5/5 |
| wave_ready_p95 (ms) | 42.202 | 40.296 | -2.63% | 3/5 |
| wave_cpu_p50 (ms) | 179.935 | 176.674 | -0.14% | 3/5 |
| start_skew_p50 (ms) | 0.053 | 0.054 | +1.02% | 2/5 |

Arm columns are medians of five process metrics; percentages are medians of
matched-pair changes, not ratios of arm medians. Each process has48 children /12
waves. The Fork p50 changes by pair are−4.24,−7.10,−7.39,−0.95,−4.31%; wave-ready
p50 changes are−4.59,−2.33,−7.27,−3.19,−9.60%. Both exceed the predeclared3% /
4-of-5 improvement screen. Wave CPU's−0.14% is a guard pass, not evidence of a
material CPU saving. Child p95 improves5/5; wave-ready p95 improves3/5, so the
p50 result does not establish a uniformly better tail. Percentiles use nearest rank; with12 waves, per-process wave p95 equals its maximum.

Measured Fork starts within a wave are about0.053ms apart (median of process
p50 skews). Both arms therefore exercise approximately simultaneous Fork calls.
The reported four-ready window and actual first-Fork-start→last-Fork-return
window agree closely, and both improve5/5.

No ordinary measured Fork exceeds100ms. There is one ordinary pages COUNT tail
at child47,791.54ms. An anonymous warmup COUNT tail382.75ms and pages diagnostic
COUNT tail791.50ms are retained too. All three have **zero overlap** with any
Fork call in their process. No tail was removed, attributed to another run's
owner log or treated as a fix for #68. Fixed waves only isolate the initialization
question from post-ready SQL timing.

The pages primary run with the COUNT tail takes1405.94ms for the suite, versus
610.59ms for its anonymous pair. That result stays in the report. Thus the
initialization improvement does not itself resolve long full-suite wall times.
Original per-process suite/batch/CPU figures and all timestamps are retained.

## Diagnostic pair and interpretation

The separate diagnostic pair shows Module-init means2.748→0.158ms,
factory-lock wait0→0.447ms, execute-to-ready34.365→31.298ms and total
Fork38.680→33.344ms. This supports the initialization explanation, but it is
one observed pair and does not replace the five ordinary pairs. Tracing changes
scheduling. It does not prove a page-fault/CoW cause or isolate exclusive CPU.
The next implementation should preserve the byte-equality, isolation, guard/grow
and cleanup contracts already established for the unchanged loader.

Prior Mac evidence remains separately source-bound: P1 Fork paired median−4.24%,
RSS−5.41%/−7.95% at hold1/4, and mixed-lifecycle P4 Fork+0.77%(2/5 improving) at
69181862. Those numbers are context, not measurements rerun on this source.
The first-root image build still adds cost, and this study does not repeat RSS,
Fresh, pgmem, Linux or release acceptance. The recommended next boundary is a
minimal reviewed candidate and platform correctness checks, with these limits
carried into the adoption decision, rather than further timing until another PASS.


This bounded study isolates P4 Fork concurrency for the static-page-only image.
The previous mixed-lifecycle screen remains FAIL at its original source; this
study does not replace it. The image loader and guest are unchanged from the
previous candidate. Only the experiment harness adds synchronized waves.

A wave has four workers. They rendezvous before Fork, call Fork concurrently,
rendezvous after all four calls return, then connect/SQL/retire/Close. The next
wave starts only after all four Close calls complete. Reports prove these
boundaries from each child's timestamps; cancellation and failed Fork join all
started children instead of stranding the rendezvous. Race-tested unit controls
cover barrier release, cancellation and partial-Fork failure.

Fixed Mac arm64 campaign: P4/cap4, Pipe,48 children per process (12 waves), five
alternating ordinary pairs (10 processes), two warmups, two4-child semantic
pilots, two4-child expected-failing corrupt-seed controls, and one separate
48-child diagnostic pair with stage/UNDO-owner logs. Total18 processes/688
children. No extra repetitions or tail removal. Same ordinary binary for both
arms, same diagnostic binary for both diagnostic arms. Go1.27.3/CGO0,
GOMAXPROCS8/GOGC100; unchanged guest and image construction/locking/settings.

The isolated screen was fixed before measurement: >=3% paired-median improvement
and >=4/5 pairs improving for both child Fork p50 and four-ready wave p50, with
wave Fork process-CPU paired median <=+5% and no >=4/5 pairs worse by>5%. Child
and wave p95/max/>100ms are retained too. A diagnostic pair does not decide the
ordinary screen. This screen answers an initialization question, not product
adoption, full-suite performance or the prior mixed-schedule gate.

Wave time starts when the start rendezvous releases and ends when all Fork calls
have returned to the ready rendezvous; it includes dispatch and ready handling.
Wave process CPU is sampled at those same boundaries (minor sampling overhead),
includes Go GC and guest background work, and is not exclusive per-child CPU.
Each child's Fork duration excludes its waits at the start and ready barriers.
SQL/cleanup remains in total batch/suite time but cannot overlap any later Fork.
The fixed-wave workload is deliberately different from the normal lifecycle
loop, so its full-suite time must not be compared as if schedules were identical.

Reproduce in a fresh disposable workspace on inputs.json's exact source:
`python3 -B benchmarks/staticimagewaves/build.py`, then
`python3 -B benchmarks/staticimagewaves/run.py`. Storage budget8GiB/minimum free12GiB,
runtime campaign600s, each process at most190s. Source/guest/overlay/binary hashes
are retained; the changed harness is race-tested before building the two binaries.
Image correctness is the earlier full-byte/TLS/grow/isolation/failure proof,
linked by the unchanged image-loader source; current SQL/cleanup is checked again.

Copy the collection scripts from this bundle into evidence and run collect.py
before cleanup. Retained replay: `python3 -B analyze.py . --check` and
`python3 -B check_analysis.py`. They read compact observations and original
identities without build/temp inputs and never overwrite published receipts.
Original reports and96 owner logs are retained locally as checksummed archives;
SHA256SUMS.json covers the compact Git bundle.
