# Fork growth: observed requests and a bounded batching hypothesis

The small-growth hypothesis is supported: all six observed children made 101
positive growth requests after initial activation, including 53 requests of just
64 KiB. A 16 MiB rounding model reduces protection calls to 11–12. This is a
calculation on recorded requests, **not an optimized runtime or measured speedup**.

The recommendation is a small host-only 16 MiB prototype, conditional on explicitly
accepting the changed OS protection boundary for the experiment. Its strongest
objection is that ahead-of-logical-size memory becomes writable: software bounds
may preserve guest semantics, but hardware protection against unchecked accesses
is weaker. This investigation does not prove equivalence or authorize adoption.
Keeping the exact current OS boundary would rule out this batching approach for
the same synchronous request stream.

## Observations

Three fresh processes, two sequential independent children each; Apple M1,
16 GiB, macOS 27.2, Go 1.27.3, CGO disabled, GOMAXPROCS=8. The prepared fixture
contains 1,000 integer rows, checked through TCP with COUNT=1000 and SUM=500500.
Each child independently mutates the fixture; the next starts pristine. The
observation-only overlay records successful Grow(old,next), without changing
allocation/protection behavior. Both positive and intentionally corrupt pilots
passed their respective oracles. All six measured children passed isolation and
cleanup checks; mapping counters returned to zero, with no growth/release failures.

| Per child | Observed |
|---|---:|
| Initial RW activation (excluded below) | 256 MiB, one call |
| Subsequent positive growths | 101 |
| Of these, 64 KiB | 53 |
| Of these, 192 KiB | 15 |
| Of these, at most 256 KiB | 73 |
| Total subsequent growth | 369.9375 MiB |
| Final logical and RW size | 625.9375 MiB |

All recorded calls occurred during Fork, none during SQL verification or Close.
The request ordering varied slightly in one trace; counters and captured event
counts agreed. These byte sizes describe virtual logical/protection extents,
not resident physical memory. See the [previous attribution](fork-initialization.md)
for residency and the separate unmodified-engine CPU profiles (Grow/mprotect was
22.35% and 24.72% of sampled lifecycle CPU, not a predicted latency saving).

## Arithmetic replay, not an executed optimization

Whenever a request exceeds the modeled RW extent, round it up to the chosen
chunk boundary, capped at 2 GiB. Keep each logical size exactly as observed.

| Policy | Calls after initial activation | Maximum ahead-RW bytes | Final ahead-RW bytes |
|---|---:|---:|---:|
| Current exact extent | 101 | 0 | 0 |
| 16 MiB rounding | 11–12 | 15.9375 MiB | 14.0625 MiB |
| 32 MiB rounding | 7 | 31.9375 MiB | 14.0625 MiB |
| 64 MiB rounding | 5 | 63.9375 MiB | 14.0625 MiB |

Five traces give 12 calls with 16 MiB rounding, one gives 11. This model assumes
protection succeeds; it models neither syscall cost, resident memory, contention,
nor the engine's behavior after a real implementation. It therefore establishes
an opportunity, not a performance result. Six sequential children on one host
cannot establish parallel behavior or Linux behavior.

## Contract implications and bounded next step

At the pinned source, MemoryMapping.enabled currently tracks both successful
logical handoff and OS RW extent. Grow validates old==enabled, alignment, monotonic
growth and the 2 GiB cap, then protects exactly old:next. A prototype would need
separate logical and RW extents; it cannot just round enabled and keep the current
old==enabled validation.

MemoryGrow serializes with MemMu and publishes MemSize only after successful
PrepareMemoryGrow. MemoryInBounds/MemoryEA/AtomicEA and the inspected handwritten
host entry points use MemSize. These are encouraging anchors, not a complete
audit of every access. A logical bounds check must still reject the ahead-RW
region. Anonymous untouched pages provide zero initialization today.

The prospective experiment should preserve logical memory.size and growth return
values, data and stable pointers, zero-filled newly exposed pages, upper bounds,
worker visibility and join-before-unmap ownership. Test failed speculative
protection with an exact-request fallback; both failures must leave logical state
unchanged and retain retry/cleanup ownership. Any possibility of partial OS
protection failure must be accounted for. Exercise the distinction between
logical bounds and the changed hardware boundary explicitly. Existing
TestMappingFailureOwnership, TestMappingInitialCleanupFailureRetainsOwner and
TestMappedMemoryContract are starting anchors, not new passes from this task.

The relevant host files (memory_backing_unix.go and code/base/memory_mapping.go)
are preserved handwritten inputs in scripts/generate_runtime.py. This makes a
host-only prototype plausible without rebuilding the guest. Raising the guest's
initial logical memory or changing its allocator is a different, broader proposal.
First compare exact vs 16 MiB on this bounded fixture, with identical SQL oracles,
CPU/wall/RSS and correctness checks; stop if the protection tradeoff is unacceptable
or improvement is absent. Broader acceptance belongs after that decision.

## Identity, reproduction and retention

- Product: v0.6.0 source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`,
  tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`.
- Clean measurement harness: `f45d5241a75c29201050b357340e2a75ae4fe33b`.
- [Inputs](forkgrowth/results/inputs.json) bind binary, harness and before/after
  overlay hashes; the binary is instrumented, not an unmodified release binary.
- [Summary](forkgrowth/results/summary.json), [complete compact traces](forkgrowth/results/observations.json)
  and [checksums](forkgrowth/results/SHA256SUMS.json) are self-contained.
- [Archive manifest](forkgrowth/results/archive.json) pins raw evidence at
  `02a67e0c85b77ddc31db2204d459820c99a3efb8`, ref
  `evidence/fork-growth-20261101`, path `benchmarks/forkgrowth/raw/`.
  Published workspace prefixes are normalized, with original/published hashes.

Read-only analysis works after workspace cleanup:

```sh
python3 benchmarks/forkgrowth/analyze.py --results benchmarks/forkgrowth/results --check
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/forkgrowth/test_analysis.py
```

To recollect compact traces, extract the pinned raw tree, verify its SHA256SUMS.json,
then run analyze.py --collect RAW --results OUT and compare observations.json and
summary.json with the committed files. To remeasure, use an owned disposable
workspace: clean worktree/ at the measurement harness commit; temp/product/ at the
verified release pin (including tag object); copy benchmarks/forkgrowth/run.py to
evidence/run.py. Run it with --phase build, then pilot, then measure, under the
recorded Go version and the plan.json disk/time guards. Build and downloads are
outside observations. Keep raw evidence on its separate ref; any proposed main
adoption should select the compact final tree, not merge exploratory history.

No production implementation, optimized-performance acceptance, integration or
release occurred in this task.
