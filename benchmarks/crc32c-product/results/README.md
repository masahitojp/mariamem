# CRC32C product candidate: local verification and finite comparison

The product-only candidate improves Fork startup p50 in all six P1/P4 pairs.
It does **not** establish a universal speedup: Fresh P4 batches are slower in all
three pairs, by 18.442/51.944/78.646ms. Keep that counter-result for the main
adoption decision. Do not carry the prior experiment's approximately 1% Fresh
cost forward as a bound on this product candidate.

The original Human approval was to implement the equivalent CRC calculation,
retain the Fresh concern, verify reproducible generation and supported
platforms, then review main adoption separately. This receipt supplies local
verification and the finite product comparison. Supported-platform CI is still
separate; no main merge, qualification READY or publication is claimed here.

## Identities and changed boundary

- Product baseline: `66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4`.
- Measured/locally tested candidate: `1057adf8fb430f5540f9d4f420f6b3f6f2012aa9`.
- Go1.26.10, Apple M1/16GiB, macOS27.2 arm64. `host.json` records the host.
- Guest remains `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- No guest/converter changes, static-image experiment, owner logging, startup
  timing overlays, CRC environment switch or asynchronous disposal change.

The canonical installer validates the whole original validator and CRC table,
then replaces only computation blocks with a bounded standard-library CRC32C
call. Comparisons, LSN checks, other branches and failure returns survive.
The old validator is preserved as generated **test-only** code. Large source
fixture additions are an exact original validator/reference, not new runtime
logic. No exploratory history is in the product branch.

Two external benchmark executables use the same `probe.go` bytes and Go version,
with an explicit module replacement to the clean candidate or a Git archive of
the exact baseline. `-buildvcs=false` applies to this external harness: build-info
is not presented as a VCS identity for the library. Library source commits,
probe hash, replacements and binary hashes are recorded separately in
`measurement-plan.json` and `measurement-builds.json`. Downloads/compilation are
outside the timings; builds took approximately157/156 seconds.

## Verification

- Source/installer/inventory/license tests: **78 PASS** at the measured candidate.
  An additional28 unchanged worker/thread-binding tests passed at the earlier
  implementation checkpoint; their original source is named in the receipt.
- CRC: **832** length/alignment cases against an independent bitwise reference,
  known vector, empty boundary, four rejected out-of-range spans, unchanged input.
- Actual generated validator: **80** old-vs-new cases, page sizes4/8/16/32/64KiB,
  offsets0/1/7/15, valid/payload/checksum/LSN variants. Exact status matches;
  valid succeeds and each corruption variant fails. These are synthetic pages,
  not all encrypted/compressed formats or injected running-DB corruption.
- Real guest: independent Snapshot/Fork, repeated/concurrent lifecycle, Pipe
  connection lifetime and capacity/Close contracts pass (`lifecycle.txt`).
- Independent guest translation, memory32 fixture, source adaptation and
  installation pass; every installed source and provenance byte matches.

Generation ran at `9548803f4b51d7d89ecbcb95caa9078d9ece9de9`. The only mismatch
was JSON key order in the initially hand-staged provenance; dictionary contents
and every code byte already matched. Candidate1057adf8 adopts the installer's
exact JSON bytes and corresponding license hashes. `verification.json` records
this reuse and the allowed metadata-only diff; it does not relabel an older
runtime run. Actual CRC/runtime tests then ran at1057adf8.

Two pre-measurement tooling failures are retained: the initial system Python3.9
lacked tarfile's `filter` argument (corrected to the task venv's Python3.14), and
an external probe go.mod had a closing-parenthesis syntax error. Neither started
a measured child. No runtime samples were retried or removed. License continuity
keeps historical audit source/host/symbol-map identities unchanged.

## Fixed product comparison

48 children per normal measured process, fixed waves of P1/P4, MaxForks=P,
GOMAXPROCS8, GOGC100, Go Pipe. Prepare the same two-row InnoDB fixture and capture
one baseline in **both** routes. Fork restores it; Fresh performs schema/seed for
each child. Each child asserts count2/sum30, updates one row and asserts sum119,
runs subsequent SELECT1, closes its pool, waits for connection retirement and
closes the DB. The next child must again see the pristine state. Each process
finally closes the snapshot and asserts zero active mappings/reservations/RW
bytes and zero mapping release/grow failures.

8 pilots×4 +4 deliberate wrong-seed controls×1 +8 warmups×48 +24 primary
processes×48 = **44 processes /1572 children**. All normal state/cleanup oracles
pass. Four wrong-seed controls fail as expected with clean disposal. Three
matched pairs per route/P, in A→B, B→A, A→B order. P1 and P4 cohorts are sequential,
not a randomized scaling study. No outlier filtering or post-result repetitions.

The table is the **median of three paired differences**, candidate minus
baseline, in ms. It is not a subtraction of independently aggregated medians.
CPU is process user+system time, including background threads, not CRC-exclusive.

| Route | P | Startup p50 difference |48-child batch wall difference|Batch CPU difference|Suite wall difference|
|---|---:|---:|---:|---:|---:|
|Fork|1|−9.305|−734.793|−1043.577|−750.759|
|Fork|4|−10.731|−291.438|−1308.583|−298.314|
|Fresh|1|+0.815|−40.038|+234.809|−39.144|
|Fresh|4|−0.741|+51.944|−68.460|+50.276|

P1 Fork process-p50 medians are42.803→33.498ms; batch medians2664.948→1930.155ms.
All three P1 Fork batch pairs improve, by734.793/810.657/614.029ms.
P4 Fork startup p50 improves in all three pairs (10.731/7.193/16.861ms), but its
batch pairs are **−291.438/+615.539/−1078.370ms**. One candidate child spends
786.73ms in cleanup and one baseline child spends785.79ms in SQL, in different
pairs. Both remain included. These coarse spans do not identify the owner or
cause of those waits; do not claim an UNDO/shim diagnosis from this campaign.

Fresh P1 batch differences are−40.038/+180.213/−50.879ms; CPU median paired cost
rises234.809ms. Fresh P4 batch differences are+18.442/+51.944/+78.646ms. The
+51.944ms paired median is about5% of the baseline's approximately1.03s median
batch. Independently aggregated batch medians are1026.369→1105.015ms (+7.7%);
this is a different aggregation and must not replace the paired number. Fresh P4
has three candidate and one baseline startups over100ms across the primary
runs. The whole-batch counter-result is not explained by startup medians alone.

Recommendation: retain the implementation and submit supported-platform
correctness CI. Main adoption must explicitly consider the newly measured Fresh
P4 wall cost and Fresh P1 CPU cost against the repeatable Fork-startup benefit.
No further sampling or root-cause search is silently added. RSS savings,
universal latency guarantees, P8, cold installation and cross-platform speedup
are not established.

## Retention and reproduction

`processes.tar.gz` contains all original process JSON/stderr members;
`processes-sha256.json` pins each member. `measurement-records.json` contains the
same measurements and classifications. Other path-normalized logs retain both
original/published hashes in `normalization.json`. `SHA256SUMS.json` seals this
bundle. Owned compiler caches, cloned sources and binaries are disposable.

Read-only replay, with no build/temp directories:

```sh
python3 analyze.py .
```

To repeat rather than replay, use a new bounded experiment workspace with8GiB
budget/12GiB free reserve, clean checkout at1057adf8, a Python3.14 venv in
`temp/venv`, and put `probe.go`, `verify.py`, `measure.py` in `evidence/`.
Acquire the unchanged guest under `temp/guest` using the checksum-bound artifact
in `guest-acquisition.json`, or reproduce that exact guest from canonical source
if the artifact has expired. Run `verify.py` then `measure.py`; the scripts pin
the candidate and select Go1.26.10. They recreate translation/build state.
`verify-observed.py.txt` records the one-time observed metadata-only resume and
is deliberately not the fresh-run recipe. The reproduction scripts only remove
a machine-specific Go path and restore the full generation sequence; the
measured source, workload and comparison order remain pinned.
