# CRC32C product candidate

The Human approved adopting the equivalent CRC32C calculation and building a
minimal product candidate on 2026-11-07. The approximately +1% Fresh batch
counter-result remains an unresolved observation, not a universal regression
claim or a zero-cost guarantee. Main integration and release are not approved
by that decision.

## Reviewed evidence and scope

- Product base: `66f2fe9d4bbde9b20323e9ee9b1562f3af16b8a4`.
- [Original experiment](https://github.com/masahitojp/mariamem/blob/e1fe6d448c5193a02cb5fa0f59ecdccbae631945/benchmarks/crcfast/results/README.md):
  binary source `7ecb119a194f9bdebba34d4f743f0ae6a460c711`, Apple M1/macOS27.2,
  Go1.27.3, P1/Pipe/warm experimental static image, owner logging enabled.
  Three matched pairs improved Fork p50 by 4.55–4.80ms; batch median improved
  22.8%. These are experiment numbers, not measured product-candidate promises.
- [Fresh follow-up](https://github.com/masahitojp/mariamem/blob/b76f7b98292f4539ae683a3301f6347f563dcd9b/benchmarks/crcfresh/results/README.md):
  binary source `a6ebe27ddfdbeaeb490078f09e254203dc953643`. Four balanced pairs
  did not reproduce consistent startup-p50 worsening (median difference
  -0.0513ms); batch difference remained +17.053ms, approximately 1%.
  CRC-free children also varied. The cause is not identified as noise, GC or
  CRC. Full-lifecycle CRC counts differ between arms; equal total engine work
  is not claimed.

## Production boundary

`scripts/runtime_crc32c.py` is an explicit single-guest installer adaptation,
following the existing thread-lifetime adapter ownership model. It requires
the pinned guest, the exact original entire validator and its 4096-byte CRC
table. It replaces only the computation blocks in the full-page CRC path with
the checked `base.CRC32C` helper, using Go's standard Castagnoli implementation.
Changed inputs stop generation for review; this is not an arbitrary WASM pattern
optimizer. Regeneration owns the output and its provenance.

The helper borrows the original guest page through `MemoryEA`; it does not copy,
cache, mutate or skip validation. The original complement, stored-checksum
comparison, LSN checks, other format branches and failure returns remain.
The replacement applies wherever the selected validator executes this path,
including later SQL/cleanup, not only rollback-segment startup reads.

No new dependency, public API, environment switch, async cleanup, static-page
image, timing hook or UNDO-owner observer is part of the product change.
Guest bytes, converter and all source input pins remain unchanged. Handwritten
helper/tests are explicitly installer-owned. The exact original validator is
retained as generated test-only code for differential corruption tests; it is
not linked into shipping binaries.

## Fixed verification exit

1. Input-drift negatives and canonical installer/inventory tests pass. Clean
   regeneration from the unchanged guest reproduces the committed output.
2. CRC vectors/alignment/bounds and original-vs-new page checks pass; changed
   payload/checksum/LSN must still fail. Run in supported Mac arm64 and Ubuntu
   x86_64 profiles through exact-source runtime CI. No broader encrypted or
   compressed-format corruption campaign is implied.
3. Product Fresh/Fork SQL, independent children and completed disposal pass.
   Existing integration owns these contracts; no timing threshold is added to CI.
4. One finite local product comparison, without the experimental static image
   or observer overlays: unchanged base vs candidate, Pipe, 48 children, P1/P4,
   three alternating pairs per route/parallel setting after warmups. Report
   all startup/cleanup/batch/suite timings and CPU; no tail filtering, retries
   to obtain favorable results or repeat-until-zero Fresh criterion.

If correctness or regeneration fails, fix or stop the candidate. If product
Fork benefit disappears or Fresh harm becomes material, return the measurements
for a Human decision; do not silently broaden the investigation. Cross-platform
performance, cold installation, RSS savings and a universal speed guarantee are
outside this exit. Original experiment evidence is never relabeled to this SHA.

## Current local result and remaining decision

Local candidate `1057adf8fb430f5540f9d4f420f6b3f6f2012aa9` passes independent
regeneration, 78 source/ownership/license tests, 832 CRC cases, 80 differential
validator cases, and real Snapshot/Fork/Pipe/Close/capacity checks on macOS27.2
arm64 with Go1.26.10. Later product-branch edits only record these results.

[Full local receipt and all measurements](https://github.com/masahitojp/mariamem/blob/4f68e66f07f0cc976606e671c03899f55928add6/benchmarks/crc32c-product/results/README.md)
are saved on a separate evidence branch; they are not part of this product PR.
The fixed 44-process/1572-child product-only campaign completed without retries
or sample exclusions; all normal SQL/cleanup oracles and expected-negative
controls passed. No static-image or observer overlay was used.

Median paired differences (candidate minus baseline):

| Route | P | Startup p50 |48-child batch wall|Batch CPU|
|---|---:|---:|---:|---:|
|Fork|1|−9.305ms|−734.793ms|−1043.577ms|
|Fork|4|−10.731ms|−291.438ms|−1308.583ms|
|Fresh|1|+0.815ms|−40.038ms|+234.809ms|
|Fresh|4|−0.741ms|+51.944ms|−68.460ms|

Fork startup p50 improves in all six P1/P4 pairs. However, Fresh P4 batch wall
increases in all three pairs (+18.442/+51.944/+78.646ms); its +51.944ms paired
median is about5% of the baseline median batch, not the earlier experiment's
approximately1%. Fresh P1 CPU also increases. P4 Fork batch variation includes
one786.73ms candidate cleanup and one785.79ms baseline SQL span in different
pairs; all are retained and their causes are unassigned.

Recommend retaining the candidate for supported-platform correctness CI and
then reviewing main adoption with these counter-results explicitly visible.
This is not universal performance non-regression. No further samples or
root-cause campaign are added. macOS15/Ubuntu runtime CI remains to be observed;
no product-platform matrix PASS, main merge or release is claimed here.
