# Buffer-pool alignment: bounded local prototype

2026-11-01. **Continue as a narrowly scoped guest-source prototype if desired;
this generated-Go overlay is not an integration candidate.** Aligning the one
buffer-pool allocation to 2 MiB eliminated the observed allocation retry and
17.707 MiB of zero writes per Fork. Local Fork time/CPU improved in 4/5 pairs,
and retained RSS improved in 5/5. The strongest objection is noisy timing on one
non-isolated Mac: one pair regressed, and no canonical guest rebuild, OOM handling
or second-platform validation was performed. The causal allocation result is
stronger than the speedup estimate. The fixed exploratory exit is complete.

## Question and exact intervention

The [preceding source correspondence](https://github.com/masahitojp/mariamem/blob/cb67868a5bbd0252992228a72be70f2bebba7c75/benchmarks/zero-fill-cause.md)
identified an InnoDB buffer-pool alignment retry. In the pinned generated
`p0_pure.go`, inside the large `Fn18568`, only this call-site argument changes:

```go
// Original
v2929 = Fn239(m, v2919+int32(12), int32(4096), v2928)
// Experimental overlay
v2929 = Fn239(m, v2919+int32(12), int32(2097152), v2928)
```

`run.py` asserts exactly one match. No other `posix_memalign` call, zero fill,
allocator, mapped-memory permission code, canonical guest patch or product file
changes. The 2 MiB value is the wasm32 buffer-pool extent alignment, not an OS
huge-page request. `Fn18568` contains inlined pool setup; its whole function is
not identified as `buf_pool_t::create`.

Both binaries use the same observation-only `base.go` overlay. The callback is
installed only for the pilot, before starting any guest. It remains nil for the
performance campaign, so there are no per-fill clocks, stacks or event recording
then; the nil check remains. Neither binary is the unmodified release binary.
The alignment overlay additionally replaces `p0_pure.go` for the candidate.

## Source and method

- Product baseline: `b3b3b46a8807482ad3f96725af86e031fe369b01`, v0.6.0;
  annotated tag object `b57183b08d48884840111e8b53daa500734337f0`.
- Measured harness source: `d2f65eff84226006dbd1edb239decdf85e03e837`.
  Identity was checked using `git_identity.py`; both binaries record that
  revision and `vcs.modified=false`. Original/overlay and binary SHA256 values
  are in [inputs](bufferalignment/results/inputs.json).
- Apple M1, 16 GiB, macOS 27.2, local Go 1.27.3 darwin/arm64,
  `CGO_ENABLED=0`, `GOMAXPROCS=8`, `-trimpath`, serial builds. This is not
  release-toolchain Go 1.26.10 or Linux evidence.
- One observed positive and one deliberately corrupted-seed negative per
  variant. Positive processes create four retained children from one prepared
  1,000-row Snapshot; pristine COUNT/SUM and independent mutations are checked.
- Five fresh-process pairs, order alternating baseline/aligned then
  aligned/baseline. Four sequential Forks per process; prior children stay open.
  This is retained-child cost, not simultaneous Fork throughput or parallelism4.
- Fork wall and process CPU measure the Fork call only. SQL verification,
  mutation, RSS sampling, preparation and closing are outside those intervals.
  `ps` samples RSS at a post-GC baseline and after each verified child. Process
  CPU includes any background work of previously retained children.
- No trials discarded; no adaptive repetitions. This is a desktop with
  uncontrolled background services (including active indexing observed before
  builds), not an isolated performance host. Comparisons are within this batch,
  not against historical 36 ms observations or pgmem figures.

## Results

The time columns below are medians of five process means (four children each).
RSS is the median of five within-process increases from baseline to four
retained children. Trace quantities come from four observed children per variant,
not the uninstrumented measurement cohort.

| Quantity | Original alignment | 2 MiB alignment |
|---|---:|---:|
| Buffer-pool zero calls per child | 2 | 1 |
| Buffer-pool zero bytes per child | 33.707 MiB | 16.000 MiB |
| Total zero bytes during Fork, median | 82.065 MiB | 64.358 MiB |
| Fork wall, median process mean | 40.712 ms | 38.729 ms |
| Fork CPU, median process mean | 53.608 ms | 52.027 ms |
| RSS increase with four retained children | 312.203 MiB | 308.859 MiB |

All four traced candidate allocations returned a guest address divisible by
2 MiB and performed just one 16 MiB fill at the selected pool caller. Original
children performed the 16 MiB plus 17.707 MiB sequence. Together with the pinned
control-flow correspondence, this establishes that the observed alignment retry
is avoided for this fixture; it is not a trace of all allocator free events.

Paired wall differences: -9.93%, -15.31%, -7.70%, -3.28%, +0.27%.
Paired CPU differences: -10.76%, -5.09%, -2.56%, -2.18%, +3.31%.
The median paired percentages (-7.70% wall, -2.56% CPU) are a different statistic
from the table's difference of medians. The RSS delta improved by 2.83–3.64 MiB
in every pair. See [complete summary](bufferalignment/results/summary.json) and
[compact observations](bufferalignment/results/observations.json) for all values.

Avoided zero writes are not equivalent to freed memory. Much of the old first
fill covered addresses subsequently reused by the retry; first-touch costs can
move to the surviving allocation. Thus about 17.7 MiB less zeroing per child does
not imply 17.7 MiB less RSS, nor does the traced duration equal avoidable CPU.
The observed benefit is modest and does not explain all Fork startup cost.

## Correctness and limits

PASS: 2 positive pilots, 2 intended negative-oracle failures, all 10 measurement
processes (40 children), pristine data, independent mutation, empty owned scratch,
and final active mappings/reserved bytes/RW bytes all zero. Four mutation tests
reject missing pairs, a surviving retry, an unaligned target and a mapping leak.
Checksum and summary verification can run after all build scratch is removed.

Not established: allocation failure/low-memory semantics, other seed sizes,
other MariaDB pool settings, Linux, race acceptance, canonical wasm regeneration,
or product-wide compatibility. Observer clock totals are diagnostic only.
The first sandbox build attempt failed fetching modules due to DNS restrictions;
the same source built successfully with network permission. No runtime trial
was lost or selectively retried.

A next source prototype should preserve `my_large_virtual_alloc`'s zero-filled
contract and scope alignment to the pool reservation needing it. A blanket
alignment change for every allocation or removal of memset is not justified by
this result. Canonical guest build/regeneration and focused failure/platform
checks would be separate work before considering adoption. No integration,
version change, release or new CI campaign is part of this experiment.

## Reproduce and retain

From this report ref, with no compiler or temp directories present:

```sh
python3 benchmarks/bufferalignment/analyze.py --check
python3 -m unittest discover -s benchmarks/bufferalignment -p 'test_analysis.py'
```

For runtime reproduction, create a disposable experiment workspace at measured
source `d2f65eff84226006dbd1edb239decdf85e03e837`, using
`experiment_workspace.py prepare` with `--min-free-gib 16 --budget-gib 8`.
The runner intentionally fixes Go 1.27.3/darwin/arm64. In that owned `worktree/`:

```sh
cp benchmarks/bufferalignment/run.py ../evidence/run.py
python3 ../evidence/run.py --phase build
python3 ../evidence/run.py --phase pilot
python3 ../evidence/run.py --phase measure
```

Use the analysis script from this report ref with `--collect <evidence>` and an
explicit disposable `--results` directory to reduce a new run. `--check` is
read-only and requires no temp tree; collection never rewrites input receipts.
Timing values are not expected to reproduce byte-for-byte.

Raw evidence is a deterministic 30,423-byte gzip archive on dedicated evidence
commit [`f308db403eaaf3ce4d82fc274d6e13714ec41173`](https://github.com/masahitojp/mariamem/blob/f308db403eaaf3ce4d82fc274d6e13714ec41173/raw.tar.gz),
ref `evidence/buffer-alignment-20261101`. Archive SHA256:
`ee51dfedeed13e008d1fd07d6eaaf6261cd1b54b1ebec680c83e69ee7192bb88`.
It contains the original trace/measurement JSON, RSS checkpoints, runner, build
logs, source receipts and member checksums. No local workspace prefix occurs in
published build info. This report branch retains compact observations and
analysis, with [checksums](bufferalignment/results/SHA256SUMS.json); raw evidence
is not proposed for main integration. Owned worktree, build output and caches
are disposable after preservation. Historical receipts retain their own sources.
