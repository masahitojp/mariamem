# Issue123: bound the cold static-image scan

The pinned constructor's whole-memory scan is avoidable: scan only its complete
write window, including zero-fill and the 4-byte initialization flag. The image
is unchanged (22 ranges, 8,929,280 bytes), while cold image creation falls from
37.20 to12.39ms (medians of20 primary processes per arm). This removes about25ms
of the one-time cost; it does **not** establish faster steady-state Fork or a
universal memory reduction.

**Recommendation: continue toward a minimal candidate, not adoption yet.**
The strongest objection is that this is one Mac, with a pinned generated layout
and experiment-owned global factory; Fresh P4 lifetime RSS increases and CPU
results are mixed. Ubuntu correctness, a regeneration-safe write-range contract,
and product lifetime/error ownership still need explicit treatment before an
adoption review. Do not merge this exploratory history.

## Fixed source and experiment

- Measured source_commit `66e382f89bfaf519b51941ef3a198c8aec82bca6`.
- Prior prototype/report `dc654406f2a4ca2a4d58237156a0421060556cf8`, built on
  product source `279fa530d03cab1bd025df91bf5130bbf845a721`.
- Same binary for both arms; only `MARIAMEM_IMAGE_FULL_SCAN=1` selects the old
  scan. Bounded scanning is this experiment's default. Generated code, guest,
  SQL settings (16MiB/read1), public API and snapshot contents are unchanged.
- Mac arm64, Go1.27.3, GOMAXPROCS8, GOGC100, CGO0, Pipe; host/binary/guest
  identities in inputs.json and host.json. No other Go campaign in preflight;
  an ordinary desktop, not an isolated performance host.
- 1,000-row fixture;48 children; Fresh/Fork × P1/P4;5 rotating paired rounds.
  40 primary processes,8 warmups,4 positive controls,4 expected wrong-seed
  failures:56 total. No extra repetitions or exclusions. All primary SQL spans
  stayed below100ms. This has no undo-owner tracing and makes no queue-cause claim.
- Suite includes first Start/image build and final disposal. Compilation,
  download, process initialization and result JSON are outside the timed suite.
  Full and bounded arms each start a new process/factory. Mapping/constructor
  tests are separate processes and cannot warm the measured image.

## Results

Column medians are independent process medians. Paired percentages are medians
of the five per-round percentages, **not** ratios of the displayed medians.
All units are ms except RSS (MiB). Complete process values, p95 and pairs are in
summary.json; all numeric observations are losslessly compressed.

| Workload | Full suite | Bounded suite | Paired wall | Wins /5 | Paired CPU | Fork/Start p50 full → bounded | Max RSS full → bounded |
|---|---:|---:|---:|---:|---:|---:|---:|
| fresh-p1 | 1789.2 | 1766.3 | -0.49% | 3 | +1.43% | 22.53 → 22.55 | 278.7 → 129.2 |
| fresh-p4 | 724.2 | 704.2 | -2.76% | 5 | -3.24% | 30.69 → 30.08 | 356.6 → 418.8 |
| fork-p1 | 1278.4 | 1276.3 | -2.60% | 4 | -1.67% | 20.11 → 20.41 | 278.5 → 130.2 |
| fork-p4 | 557.3 | 532.5 | -3.85% | 4 | -1.02% | 28.98 → 29.28 | 460.6 → 413.5 |

The scan plus image writes fall from26.15 to3.21ms (20-process medians);
constructor medians within each cell remain roughly2.3–2.7ms. Image build also
includes mapping, file/FD work and disposal; do not subtract separately computed
medians as an exact phase sum. Build ranges are33.26–53.75ms/full and
10.47–13.16ms/bounded.

P1 lifetime high-water RSS drops about149MiB in every pair. That supports the
full-scan transient-peak explanation; it is not retained per-child RSS or PSS.
Fresh P4 RSS instead worsens in4/5 pairs (paired median+9.77%); Fork P4 RSS is
mixed (3/5 improve, paired median−0.87%). Concurrent allocation/GC/overlap can
move the high-water point; this run does not identify its cause. No claim that
all memory overhead is solved.

Per-child Fork is substantially unchanged: the scan is paid once per process,
not once per child. Fork P4 paired suite wall−3.85% is consistent with removing
that initial cost, but CPU only−1.02% with3/5 improvement; Fresh P1 CPU+1.43%.
There are large lifecycle outliers in later pairs (all retained), so don't read
all suite improvement as deterministic scan savings. Previous0.6.2/main figures
remain their own [three-arm cohort](../../issue123baseline/results/README.md);
do not add these percentages to that cohort or claim a fresh pgmem comparison.

## Safety and boundaries

NewWithMemory calls Fn67 for linear initialization. The pinned Fn67 writes
segments at8388608/17370304/18012928, zero-fills18013440..26996016 and writes the
initialization flag at26996016..26996020. Scan page-rounded
[8388608,26996020),17.75MiB on this16KiB-page host, instead of256MiB. InitElemSeg
populates private Go function tables. Only generated globals/data initialization
runs: no MariaDB/InnoDB engine template is captured.

PASS: full256MiB bytes/globals/segment equality; exact full/bounded range equality;
source hash drift guards; initialization-flag omission negative control; child
and runtime-owner isolation; readonly image FD; mapping bounds/Grow/OS protection;
worker join before unmap; concurrent first acquisition/close; injected cleanup
ownership failures. Existing tests ran without skips. All56 real-DB processes
met their expected success/failure and zero-debt cleanup oracles, with no scratch
files left. The four wrong-seed cases failed as required. Real-DB validation is
the established SQL/row-isolation oracle, not a new native MariaDB differential
campaign. Linux runtime validation remains unexecuted.

The hard-coded window is acceptable only for this SHA-pinned spike. Production
must derive or validate complete constructor write ranges, including init flags,
under regeneration. Copying only data-segment ranges or stopping at DataEnd
would be incorrect. This is host-side experiment code; no guest patch/settings
change. Post-measurement changes in this branch are report/replay files only.

## Reproduction and retained evidence

Use the experiment-workspace helper with a clean checkout at the measured SHA,
min-free10GiB/budget10GiB, timeout1500s, running
`python3 <worktree>/benchmarks/issue123scan/campaign.py`. It validates commit
identity before building and uses owned caches/scratch. Retain this compact
report, identities and checksums; remove compiled/source/cache residue afterward.

Read-only verification after cleanup:
`python3 benchmarks/issue123scan/results/analyze.py --check`.
It uses only this directory, validates the exact56-process matrix and all
success/cleanup/image checks, recomputes summary.json byte-for-byte and verifies
SHA256SUMS.json. No temp/source archives or evidence mutation is required.
