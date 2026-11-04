# Issue100 exit: charset/collation initialization attribution

**The dominant early common call is character_set_collations.from_text: 14.908ms.** Within it, actual registry initialization is 3.547ms and actual UTF8mb3/UTF8mb4 UCA1400 collation-handler initialization is about5ms each. The ordinary default-charset lookup is 0.001ms and filesystem case-sensitivity probe 0.020ms. This reaches #100's investigation exit: the major calls are identified and a bounded improvement candidate can be selected.

Recommendation: consider a **small WASM UCA UTF8 comparison-booster experiment before whole-server initialized-state cloning** (#103). Source has per-level booster creation for single-byte-minimum encodings, with two65536-entry population loops. A first diagnostic should disable creation and corresponding accelerated consumer paths together, preserving Unicode/collation selection and the normal comparison implementation, then compare startup and text-query costs. This is a proposed experiment, not an implementation or adoption.

Strongest objection: measured spans cover full handler initialization, not booster alone. Tailoring/weight initialization also occurs there; the saving is unproven, and removing comparison acceleration may slow SQL or change edge-case results. Only a paired trial with native text oracles can decide. Do not call the full10ms removable, drop charset support, or change default collations to bypass the work.

## Fixed identities and execution

- Product source_commit `bc00b8e66e5fd57bc9b2127001faf8e05952b417`, matching preceding observations; historical measurement pin, not latest-main identity.
- Actual final binary harness source_commit `668e8e92d80a5789d168af82bd54f595a6a9fcd8`. Commit-object/clean-tree/benchmark-only diff checks precede build; binary VCS stamp verified afterward.
- Guest SHA256 `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`. No guest rebuild, settings/engine/API/product changes. Generated-Go overlay adds read-only observations.
- Apple M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,TCP,1000 integer rows, explicit cap1. Root captured and closed before four sequential children, with seed/independent mutation/subsequent SELECT and cleanup oracles.
- Final primary: three alternating fresh-process pairs (callbacks off/on,on/off,off/on), four children each. Separate warmup8, final positive pilot4 and negative1. Both modes retain existing full guest init diagnostics; new callbacks off/on in the same binary. No primary exclusions/repeats.
- Two earlier pre-primary pilot pairs (positive4+negative1 each) identified where to add direct callbacks. They are retained separately under their actual earlier source/binary identities, not relabelled as final trials. Total47 children across14 processes; final primary denominator24.

## Major-call accounting

Each value is the median of three process medians, each over four children. Intervals are host-monotonic wall durations. Guest and host origins differ. Nested intervals and independently aggregated medians need not sum exactly; [summary](charsettail/results/summary.json) retains per-child accounting.

| Within collation override setup | ms |
| --- | ---: |
| Charset/collation registry initialization | 3.547 |
| UTF8mb3 UCA1400 collation init, id2048 | 5.007 |
| UTF8mb4 UCA1400 collation init, id2304 | 5.058 |
| UCS2 UCA1400 collation init, id2560 | 0.424 |
| UTF16 UCA1400 collation init, id2816 | 0.415 |
| UTF32 UCA1400 collation init, id3072 | 0.419 |
| Parsing/other remainder, excluding the above | 0.048 |
| Enclosing character_set_collations.from_text | 14.908 |

Per child, the reducer subtracts registry and handler spans from the enclosing parse span and asserts a non-negative remainder. Handler calls outside the parse interval (including id8 later in startup) are preserved but excluded from this accounting. This is execution of initializers, not merely lookup/token parsing.

| Other tail / enclosing metrics | Callbacks off | Callbacks on |
| --- | ---: | ---: |
| Public Fork wall, ms | 37.895 | 36.572 |
| Public Fork process CPU, ms | 51.809 | 51.581 |
| Guest server_init, ms | 32.988 | 31.963 |
| Guest common init, ms | 17.280 | 16.448 |

With callbacks: default lookup 0.001ms; path parsing 0.004ms; DB-options-cache interval 0.001ms; filesystem case probe 0.020ms; entire tail 14.957ms. These are not the main15ms cost.

Paired Fork-wall changes -3.73%, -2.80%, +14.48% are observation/scheduling variability, not a product speedup or negative instrumentation overhead. Guest stage CPU counters remain unavailable (`null`), so stage wall is not assigned wholly to CPU. No RSS, P4 attribution or full-suite improvement is measured.

## Source correspondence and candidate boundary

[MariaDB source hashes](charsettail/results/source-audit.json) pin `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.

1. [mysqld.cc default](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L362) contains five uca1400_ai_ci overrides (utf8mb3,utf8mb4,ucs2,utf16,utf32). [init_common_variables](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/mysqld.cc#L4456) parses them before the default charset lookup. This explains why the earlier pre-lookup interval was large; removing/clearing this setting would change behavior.
2. [Charset_collation_map_st::from_text](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/charset_collations.cc#L84) resolves charset and collation names. [get_internal_charset](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/mysys/charset.c#L862) invokes actual charset/collation initialization when not ready.
3. Exact generated `p0.Fn5572` call to Fn20110 is bracketed for the parser; Fn969 is bracketed separately for default lookup. `p7.Fn820` once gate calls slot542, bound by p1 initialization to Fn960, the registry initializer. Entry/defer observations measure that function. `p4.Fn966` brackets actual charset/collation vtable init calls with charset ID and handler slot. Slots216/244 map to Fn502/Fn539, whose bodies correspond to UTF8mb3/mb4 UCA wrapper initialization; slot190 maps to generic Fn465. Selected spans, bindings and hashes: [mapping](charsettail/results/mapping.json), [registry mapping](charsettail/results/registry-mapping.json), [handler mapping](charsettail/results/handler-mapping.json), [overlay](charsettail/overlay.py).
4. [UCA1400 ID layout](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca1400.h#L204) maps2048/2304/2560/2816/3072 to utf8mb3/utf8mb4/ucs2/utf16/utf32. This is source decoding of observed IDs, not names inferred from timing.
5. [init_weight_level](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca.c#L34460) creates a comparison booster when mbminlen==1. [Booster construction](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca.c#L34292) populates byte-pair lookup data; [pair loop](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca.c#L34107) and [weight loop](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca.c#L34202) each visit65536 entries. This supports a concrete hypothesis for repeated setup cost, not a measured exclusive cost.

**Safety condition for a prototype:** simply setting booster=NULL is invalid. [Comparison consumers](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/strings/ctype-uca.inl#L103) dereference it under compile-time MY_UCA_ASCII_OPTIMIZE, without a runtime NULL guard. Disable construction and all affected comparison/transform fast paths coherently, or provide valid precomputed tables. Existing scan fallback is a source-level route to test, not proven parity. Preserve ordering/equality/PAD/contractions/Unicode behavior and hash consistency; validate UNIQUE/ORDER BY and string-heavy workloads against native as well as integer fixture startup. No patch is included here.

Precomputing deterministic booster data could retain comparison acceleration, but pointer/identity/ownership and static image size require a separate design. That is narrower than cloning a live initialized MariaDB, yet more work than the first bounded mechanism trial. #103 is not adopted or ruled out.

## Verification, retention and reproduction

All44 positive children pass existing SQL/independence/cleanup oracles; three separate wrong-seed negatives detect failure and clean up. Across14 processes active mappings/RW/reserve and release failures are zero. All47 children have zero dropped init records. Final observations include paired registry/handler boundaries; no silent skip. The saved reducer also validates preliminary oracles and rejects four mutations: missing common marker, dropped record, hidden mapping leak and missing handler end.

Initial sandbox dependency-download failure and later sysctl metadata denial occurred before primary measurement, not discarded runtime trials. The two adaptive pilots and their binary inputs are preserved under separate names. No guest rebuild/CI was used. [Assessment](charsettail/results/assessment.json) distinguishes confirmed calls, candidate inference and unfinished adoption/correctness/performance work.

Read-only verification after deleting all build/temp files:

```sh
python3 benchmarks/charsettail/analyze.py benchmarks/charsettail/results --check benchmarks/charsettail/results/summary.json
```

The command rederives the summary, checks all result-file hashes and rejection controls. [compact.json](charsettail/results/compact.json) retains final10 process records; [preliminary.json](charsettail/results/preliminary.json) retains earlier4, both with lossless column encoding of guest init events. Decode equality to all original records was checked before reduction. [Inputs](charsettail/results/inputs.json) and the separate preliminary inputs retain their actual source/binary identities; [publication](charsettail/results/publication.json) records original/published hashes and workspace-prefix normalization only. SHA256SUMS.json binds saved results.

For execution, clean-clone the fixed product into disposable workspace temp/source; copy and commit benchmarks/charsettail; set MARIAMEM_EXPERIMENT_TEMP to temp (with sibling evidence) and run run.py --phase build, pilot, measure using the committed overlay generator and Go1.27.3. New runs record their own clean harness/binary stamp; do not relabel the preserved historical one. The final harness includes all markers, so adaptive preliminary pilots are not prerequisites for reproduction.

Useful evidence and Git history are preserved before deleting owned clone/binary/cache. #100 records the final cleanup and post-cleanup reducer check. No product change, main integration, qualification or release follows from this investigation exit. The next decision is whether to authorize the bounded booster mechanism prototype, not whether to adopt a performance change.
