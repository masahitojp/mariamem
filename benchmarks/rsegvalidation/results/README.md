# Rseg read completion: CRC dominates the measured path

The question was whether the previously measured approximately4.2ms per Fork
inside `buf_page_t::read_complete()` was validation, conditional recovery or other
work. **Full-page CRC32C computation accounts for98.3% of that interval** in this
bounded Mac/P1 workload. Recovery runs, but is only0.023ms per Fork.

Recommend a separate small correctness-first prototype accelerating the same
CRC32C computation, with unchanged input bytes, checksum interpretation and
corruption rejection. Do not remove validation or attempt to optimize redo
recovery based on this result. The main limitation is attribution-only evidence:
no optimized implementation, observer-off speedup, stage CPU measurement,
parallel campaign or Ubuntu result exists. The approximately4.1ms observed CRC
interval is an opportunity ceiling for this specific path, not a promised gain.

## Results

Apple M1,16GiB, macOS27.2 arm64, Go1.27.3. Three alternating Fresh/Fork pairs,
48 children per process, P1, same diagnostic binary, warm experimental static
page image, same prepared schema/seed and Pipe connection. Primary population:
144 Fresh and144 Fork children. These experimental image settings are not a
claim about all product configurations.

Elapsed milliseconds per Fork child (means add back exactly):

| Disjoint completion component | Mean ms | Per-child p50 ms | p95 ms |
| --- | ---: | ---: | ---: |
| CRC32C computation |4.121510|4.103522|4.211045|
| Other work within corruption validation |0.014335|0.014045|0.015709|
| `recv_recover_page` |0.023410|0.023330|0.024788|
| Remaining completion/wrapper/unlock work |0.033810|0.033104|0.037253|
| **read_complete total** |**4.193066**|**4.174477**|**4.286453**|

Validation including CRC totals4.135846ms. Do not add it again to the disjoint
rows. Independently aggregated percentiles need not add up. Median per-child CRC
share of read_complete is98.314%; mean per-child share98.294%.

Rseg-header acquisition totals4.494608ms mean; rseg-array initialization totals
5.255781ms mean. Whole Fork API p50 is26.909479ms in this diagnostic build;
Fresh API p50 is23.720624ms. These are not before/after optimization results.
Comparing them to earlier diagnostic binaries does not establish a speedup.

| Fork primary process | CRC mean ms | CRC p50 ms | Recovery mean ms |
| --- | ---: | ---: | ---: |
|0|4.117468|4.102247|0.023207|
|1|4.125771|4.102812|0.023379|
|2|4.121293|4.104858|0.023644|

All144 Fork children individually have128 read-complete calls,128 validation
calls,128 CRC computations and128 actual `recv_recover_page` calls. The recovery
argument is true on all128 calls: this is not evidence that recovery was bypassed.
It also does not count redo records actually applied.

CRC bytes per child are exactly **2,096,640 =128 ×(16,384−4)**. Each page excludes
its four-byte stored checksum, as the source requires. Fresh has one cached rseg
header and zero read-complete/CRC/recovery calls **in this bound header path**;
this does not mean Fresh performs no CRC computations anywhere in startup.
No child API/SQL/cleanup span exceeds100ms; all samples remain, no exclusions.
The decision gate (component median >=0.5ms and median share >=50%) identifies
only CRC. `decision.json` also retains per-process early0–7/late8–47 distributions.

## Source identity and mapping

Binary source_commit **`dbc3638c04cd48564d01f26b26e845390e3f1f31`**.
Parent report4daf7d531ff54d75f8fd74b320e85b6c7274846b.
Unchanged guest SHA256 **`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`**.
MariaDB12.3.3 source_commit **`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`**.
`buf0buf.cc` was fetched at that pin and checked against its previous Git blob,
byte count and SHA256 in `source-files.json`; other manifest entries remain prior
source identities, not claims of a new fetch.

- [read_complete](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L3553-L3687):
  Fn18174. Four direct generated callsites of Fn18145 are timed as corruption
  validation; actual invocation counts determine the taken path.
- [full_crc32 corruption checking](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0buf.cc#L630-L691):
  Fn18145. The `my_crc32c` computation is inlined into generated labelsL23–L36,
  with seed~0, page-size-minus4 bytes, software table lookups and final XOR.
  Timing ends before the final complement/stored-checksum comparison and subsequent LSN checks;
  those checks remain in validation-other. This is CRC32C, not arbitrary CRC32.
- `read_complete`'s l2 flag, frame-pointer branch and Fn17470(space,page) identify
  actual `recv_recover_page` invocations. False recovery follows the separate
  READ_FIX decrement. Recovery is timed whole; its internal work is not split.

`validation-mapping.json` pins function bodies and every patched anchor.
`crc-cfg-check.json` records reachability fromL23 with only timed exitL36 and no
calls/returns within the region. `page-mapping.json` preserves the inherited
outer observer anchors, including UNDO-owner hooks. Source and generated-code
calculations, checks, branches and return values are unchanged; instrumentation
is a Go overlay, not edits to canonical generated code or guest inputs.

## Scope, controls and interpretation

Observers bind to the exact rseg-header caller's Module, not its shared pool.
Completion categories are non-overlapping. CRC is nested only within a direct
validation call from that completion; checks recursively reached during recovery
would remain in recovery, avoiding double attribution. Other completion work is
an explicit residual, including observer/wrapper overhead. Adding components
back to all outer intervals is mechanically checked for every recorded child.

New timing adds768 clock reads per Fork child, zero per Fresh header path,
on top of inherited observers; unbound calls also pay lookup overhead. No
observer-off calibration or CPU/scheduling attribution was measured. The source
shows a software CRC loop, making an equivalent accelerated CRC implementation
a concrete candidate; measurements alone do not prove an exact CPU saving or
explain parallel scalability. Zero read-wait spans from the prior split do not
prove every lower-level service is wait-free.

One diagnostic Go build100.4s. Two semantic pilots ×4 children, two wrong-seed
negative controls ×1, two warmups ×48, six primary processes ×48:12 processes,
394 children. SQL/state, isolation, fixed-wave ordering and cleanup passed;
wrong-seed cases failed as expected and still cleaned up. No retries or extra
samples. All394 child owner logs are retained without truncation,753705 events.
Final mappings, reservations, failure counters and image-owned FDs are zero.

Focused wave race tests and observer units passed. New fake-clock tests cover
CRC/validation/recovery accounting, exact-Module scope, inactive phases, overlap,
unfinished spans and disabled observers. Twenty-seven private-copy analysis
mutations must be rejected, including missing completion data, invalid counts,
recovery without its flag, CRC escaping validation, invalid bytes and incomplete
spans. Mutated trace hashes are rebound privately so accounting must reject the
mutation, rather than only detecting a hash mismatch. Originals are unchanged.

No optimization, validation skip, canonical product/API/guest/generated change,
heavy CI, adoption, main integration or release occurred.

## Reproduction and next bounded step

Retained-only replay, with build/temp/worktree removed:

```sh
python3 -B analyze.py . --check
python3 -B check_analysis.py
python3 -B decision.py --check
```

`summary.json` retains all children, `decision.json` pooled/process distributions
and counts; compressed original process reports and all owner logs retain the
raw evidence with hashes. `SHA256SUMS.json` covers the compact result set.
`inputs.json` binds binary, exact source, guest, plan and overlay hashes. A later
report commit must not be called the measured binary source.

New measurements reproduce the pinned source's `benchmarks/rsegvalidation/build.py`
and `run.py` in an8GiB disposable workspace with12GiB free-space guard. Mapping is
already embedded in the overlay; no temp-extracted source file is needed to build.
`acquire.py` can re-fetch the pinned native source for inspection.

Suggested next bounded task: first prove an equivalent CRC32C fast path against
the existing result on page-shaped data, boundary lengths and deliberately
corrupted pages; then compare one ordinary baseline/candidate with the same
Fresh/Fork workload. Keep checksum verification and corruption-error semantics.
A host CRC32C facility is a hypothesis to evaluate, not a chosen architecture or
an already available improvement. Other validation and recovery work are too
small here to justify further decomposition first.
