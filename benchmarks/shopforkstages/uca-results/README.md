# Which UCA initialization remains? — 2026-11-11

**Conclusion:** the five startup UCA calls are the default UCA1400 ai_ci
collations for five encodings. Their remaining cost is inside
`my_uca_info_init`, not booster population. The current prepared booster shortcut
is already doing its intended job for the two UTF-8 defaults in this profile.
Do not expand prepared boosters merely to address this observed startup cost.

**Recommendation:** next assess a narrowly scoped immutable template for the
untailored default weight/contraction data used by these five IDs, retaining
private descriptors, pointers that require relocation, readiness flags, locks and
mutable ownership. First split page-array allocation/copy, contraction setup and
hash population, and verify which structures are immutable after initialization.
This is a concrete candidate to investigate, not evidence that contraction hashes
alone dominate, nor approval to remove initialization or ship a shared structure.
The strongest objection is that the whole measured region is only about2.35ms;
source maintenance and added static bytes may cost more than this opportunity.
Stop if attribution/ownership review does not yield a small locally verifiable
change. No optimizer, guest regeneration, timer change or CI was attempted here.

## Bounded observed profile

Product `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`; instrumentation lineage
`809036801dc8d3f6d4dae543e73eb57bfca42b23`; built observer/harness source
`b0c457e1d314b8a957ff7b149d400be4ae05a146`. Exact guest, symbol map,
source file/body and binary hashes are in `inputs.json`, `uca-bindings.json` and
`function-map-proof.json`. `uca-source.json` pins the four source files to the
verified upstream commit. Host identity is in `uca-host.json`.

One diagnostic Go build; two P4 Shop70 processes on Apple M1/macOS27.2 with
Go1.27.3, Go Pipe, GOMAXPROCS8/GOGC100,16MiB pool/read1, cap5.
Each process runs50 reads on one child and20 writes on individual children:
**42 Forks +2 Fresh,140 SQL cases passed**. Both finish with zero active mappings
and empty owned scratch. This is per-child elapsed attribution under the observer,
not exclusive CPU, treatment performance, P8 or Ubuntu acceptance.

| ID / collation | UCA call p50 | Nested `my_uca_info_init` p50 | Booster population calls/startup |
| --- | ---: | ---: | ---: |
|2048 utf8mb3_uca1400_ai_ci|0.465ms|0.464ms|0|
|2304 utf8mb4_uca1400_ai_ci|0.468ms|0.467ms|0|
|2560 ucs2_uca1400_ai_ci|0.467ms|0.466ms|0|
|2816 utf16_uca1400_ai_ci|0.462ms|0.460ms|0|
|3072 utf32_uca1400_ai_ci|0.467ms|0.466ms|0|

Each ID occurs exactly once in all44 observed startups. Per-Fork aggregate UCA
p50 is2.348ms, p95 nearest rank3.932ms, max5.344ms. The median per-child nested
coverage ratio is99.86%. Nested times are inclusive: do not sum them with parent
times. Zero booster calls applies only to these selected startup paths; other
collations still have the original runtime producer.

## What is and is not resolved

The prior five unnamed calls are now named, and their expensive region is
localized. Source inspection shows `my_uca_info_init` initializes three UCA1400
levels and includes allocation/copy of page metadata, rule/page processing,
contraction allocation/copy and hash population. See `source-notes.md`.
Individual subcosts and allocator/page-fault contributions remain unmeasured.
Equal per-ID timings suggest repeated work but do not prove tables can be aliased
safely or that all three levels have equal cost. Removing non-UTF8 collations or
changing defaults is outside the proposal.

A next bounded observation can add three per-ID subphase marks to the same
source-bound overlay: one diagnostic build plus two P4 runs, approximately
10–20 minutes/under8GiB on this host. Only then select a template prototype if
there is a dominant immutable subregion. Validate any later prototype using
complete table equivalence, native SQL ordering/collation cases, fallback paths,
full both-OS acceptance and alternating observer-off performance pairs. None of
those candidate acceptance results is claimed here.

## Reproduction and retention

Read-only summary check after cleanup:

```
python3 benchmarks/shopforkstages/uca-results/analyze.py
```

For exact runtime reproduction, create a managed experiment workspace at built
source `b0c457e1d314b8a957ff7b149d400be4ae05a146`, recover `run-uca.py` from this
report commit into its evidence directory (its SHA is in `execution.json`), then
run `acquire-map.py`, `build.py` and `run-uca.py <worktree>` using Python3.14.
Use the workspace/disk guard with8GiB owned,8GiB free and30-minute build timeout;
record exact source identity before build. The build uses one canonical guest
artifact and a Go overlay; it does not regenerate the guest. The observer is
bounded to this startup profile, not a general diagnostics API.

Retained data is the compact per-startup counters/times, exact bindings/source
hashes, host, summary, execution receipt and reproduction code. Generated output,
downloads, compiler cache and full transient traces are disposable. No local
absolute work paths or native sources are published. `SHA256SUMS.json` covers
this directory other than itself.
