# CRC32C host fast-path prototype

**An equivalent Go CRC32C computation improves Fork in all three matched primary
pairs.** Fork API p50 falls by4.55–4.80ms; the48-child batch falls by377–386ms.
Header CRC p50 falls from4.182ms to0.257ms in the separate diagnostic pair.
Original-generated/independent-reference checks and real page-validator corruption
controls pass. This supports continuing candidate work, not product adoption.

The material counter-result is **Fresh slowing in all three pairs**, by0.028–1.233ms
in API p50 and21–108ms per batch. Its cause remains unresolved; do not dismiss it
as noise or claim universal non-regression. Before adoption, isolate this result,
choose a maintainable integration boundary and verify the supported platforms.
No new samples or product integration are included in this report.

## Change and correctness

The experiment replaces only the inlined full-page CRC32C computation within
`buf_page_is_corrupted`/generated Fn18145. `base.CRCFast` checks the unsigned
memory32 range with existing `MemoryEA`, borrows those bytes without copying,
and calls Go `hash/crc32.Checksum` using the Castagnoli table. The original
complement, stored-checksum comparison and subsequent LSN checks remain. The
original software loop is kept behind a process-start environment switch.
Both arms use the **same binary**; `MARIAMEM_CRC_FAST=0/1` selects the calculation.
No page-validation result is cached, no validation is skipped, no page bytes
are modified, and there is no external dependency or guest rebuild.

This replacement applies to **all full_crc32 computations reaching Fn18145**,
not just rseg headers or startup. Other CRC implementations/call paths are not
rewritten. Thus later SQL/Close work may also benefit, but those sites were not
separately attributed. The prototype assumes the pinned MariaDB CRC polynomial
and canonical constant table; it is not a general arbitrary-WASM rewrite rule.

Go1.27.3's arm64 implementation dispatches on `internal/cpu.ARM64.HasCRC32` and
has a software fallback. Its source hashes are in `go-crc-source.json`. We did
not force ISA choices, inspect final assembly or measure an x86 backend. The
measured speedup is established independently of that dispatch interpretation.

Correctness gates:

- 832 length/alignment cases: lengths0–65532, offsets0–31; the fast result equals
  both the exact extracted generated CRC loop and an independent bitwise CRC32C.
  The original4096-byte guest lookup table is extracted and hash-pinned.
- Known `123456789` CRC32C result0xe3069283, empty boundary and four rejected
  out-of-bounds ranges. Inputs are checked unchanged.
- 80 actual generated Fn18145 cases: five page sizes4/8/16/32/64KiB, four offsets,
  valid data, flipped payload bit, flipped checksum bit and LSN inconsistency
  with a freshly correct checksum. Both arms return the same exact status;
  valid pages succeed and all three corruption variants fail.
- All884 runtime children retain the existing SQL/state/isolation and cleanup
  oracles. Four wrong-seed controls fail as expected and clean up. These are
  runtime state controls, not corruption-injected running databases.

The generated-function tests construct bounded synthetic memory without starting
a DB. They prove the selected validator boundary, not every encrypted/compressed
format or every DB-level corruption-reporting route. This is a local Go overlay
prototype; permanent converter/guest/host integration remains undecided.

## Primary performance

Apple M1 /16GiB /macOS27.2 arm64 /Go1.27.3. P1,48 children, equal prepared
schema/seed, Pipe, same warm experimental static-page image. Three pairs per
route, arm order software→fast, fast→software, software→fast. Detailed startup
clocks/logging are **off** in primary runs, while UNDO-owner logs remain **on** in
both arms as requested. The binary contains inactive diagnostic hooks, so this
is a paired prototype comparison, not a pristine shipping-binary benchmark.

Table entries are medians of three process values; for child metrics, medians
of the process p50 values. Pair deltas are reported separately below.

| Fork metric | Software | Fast CRC32C | Change |
| --- | ---: | ---: | ---: |
| API elapsed p50 |25.472ms|20.840ms|−18.2%|
| API-window process CPU p50 |38.090ms|31.991ms|−16.0%|
|48-child batch elapsed |1688.210ms|1303.287ms|−22.8%|
|48-child batch CPU |2524.096ms|1905.003ms|−24.5%|
| Whole suite, setup through cleanup |1770.882ms|1383.889ms|−21.9%|
| Child count/sum SQL p50 |1.924ms|1.062ms|−0.862ms|
| Child Close p50 |6.066ms|3.516ms|−2.551ms|

CPU is process user+system time during the measured interval, including its
background threads, not CPU exclusively charged to CRC. P1 avoids overlapping
child API windows, but does not remove internal concurrency. Close includes its
existing disposal guarantees; no earlier return or asynchronous cleanup change
was made. The Close reduction is observed, not localized to a particular read.

| Fork pair | API p50 fast−software | Batch fast−software | Batch CPU fast−software |
| --- | ---: | ---: | ---: |
|0|−4.633ms|−386.378ms|−639.293ms|
|1|−4.552ms|−380.437ms|−643.868ms|
|2|−4.800ms|−377.186ms|−618.900ms|

The prespecified continuation gate passes: all three Fork API p50 pairs improve,
with median improvement4.633ms >=1ms, and correctness passes. This gate does not
accept the Fresh counter-result or authorize integration.

| Fresh pair | API p50 fast−software | Batch fast−software | Batch CPU fast−software |
| --- | ---: | ---: | ---: |
|0|+0.585ms|+20.598ms|+37.379ms|
|1|+0.028ms|+31.104ms|+70.902ms|
|2|+1.233ms|+107.746ms|+282.297ms|

Fresh median process API p50 is21.980→22.478ms, batch1747.912→1790.301ms,
CPU2746.176→2839.268ms. Fresh's read/creation profile differs from restored Fork;
we have not isolated why it slows here. No additional repetitions were added to
seek a preferred result. All samples remain, with no child elapsed spans >100ms.
Process lifetime max RSS is about279MiB for both arms; this experiment does not
establish an RSS improvement or retained-memory envelope.

## Diagnostic pair: the intended work shrinks

Two additional observer-on Fork processes,48 children each, are attribution
only and excluded from primary speedup calculations:

| Per-child interval p50 | Software | Fast |
| --- | ---: | ---: |
| Header CRC computation |4.182083ms|0.257330ms|
| Other corruption-validation work |0.014654ms|0.013858ms|
| Recovery function |0.024063ms|0.023716ms|
| Other read-completion work |0.034598ms|0.032218ms|
| read_complete total |4.253332ms|0.327540ms|
| Rseg-header acquisition |4.548330ms|0.630449ms|

Percentiles do not add arithmetically; the reducer verifies exact per-child
exclusive addback before aggregation. Each diagnostic child has128 header
misses,128 CRC calls over2,096,640 bytes and128 actual recovery calls, in both
arms. The same checks still run. CRC timing includes the fast-call overhead and
excludes the common final complement/comparison. The diagnostic pair's approximately
16.3× CRC speedup is not a16× whole-Fork claim, nor a three-pair stage campaign.

## Identity, finite work and limits

Binary source_commit **`7ecb119a194f9bdebba34d4f743f0ae6a460c711`**;
parent attribution report71c61ed30de11ee4322ad407a0f80fbbe87fe878.
Guest SHA256 **`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`**,
MariaDB12.3.3. `inputs.json` pins binary hash, build metadata, overlay hashes and
measured plan hash. `crc-mapping.json` pins original CRC function/table/reference.
Later report/plan clarification commits are not relabelled as the binary source.

One benchmark binary built,8.4s after test compilation populated the dedicated
cache. Two pre-binary test-harness compile/link failures were corrected (reference
label separator; linking all generated partitions from an external test package).
They started no benchmark processes; records are retained. Focused wave race and
observer tests passed, as did CRC correctness tests. No broad runtime suite or
Release CI was used.

Fixed campaign:4 semantic pilots×4 +4 wrong-seed controls×1 +4 warmups×48
+12 primary processes×48 +2 diagnostic processes×48 = **26 processes /884 children**.
All884 untruncated owner logs are retained,1,681,365 events. Final mappings,
reservations/failure counters and image-owned FDs are zero. Fifteen private-copy
analysis mutations reject broken state, cleanup, ownership, wave, arm, CPU and
CRC accounting; original inputs remain unchanged.

The original measured plan contains inherited attribution-only exit/mapping
phrases inconsistent with its new question, criteria and the user-authorized
optimization. `plan-clarification.json` records that copy error explicitly. The
report commit cleans those fields in the executable plan without changing the
retained measured plan, binary, criteria, samples or their identities.

No product/API/canonical guest/generated files changed, no new dependency was
adopted, no main merge or release occurred. Generated anchors are exact-source
experiment mechanics, not a maintainable production patch. Ubuntu, P4/P8,
ordinary owner-off overhead and broader format/error acceptance remain unmeasured.

## Reproduction and next decision

Retained-only replay after removing owned build/worktree/cache:

```sh
python3 -B analyze.py . --check
python3 -B check_analysis.py
```

`summary.json` retains every child, tails, process metrics and matched deltas.
Original reports/timing and every owner log are compressed and hash checked;
`SHA256SUMS.json` covers the retained set. To remeasure, use the exact binary
source's `benchmarks/crcfast/build.py` and `run.py` in a bounded disposable
workspace,8GiB budget/12GiB free-space floor. Do not replace its source pin with
the report commit or reinterpret observer-on samples as primary runs.

Recommend preserving this candidate and next deciding its permanent boundary
(e.g. explicit CRC primitive/import versus converter support), alongside a small
Fresh-regression check. Preserve polynomial/initial/final XOR, range checks,
checksum comparison, LSN behavior and corruption errors. The Fork opportunity is
now demonstrated; cross-platform/product adoption remains a separate decision.
