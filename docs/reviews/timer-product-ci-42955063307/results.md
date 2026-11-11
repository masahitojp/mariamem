# Bootstrap source-control results

Source/run/artifact identity remains in [assessment.json](assessment.json). These
are compiled source-unit controls, not installed guest or performance measurements.

## Millisecond calibration

Result: `INITIALIZER_UNIT_PASS`. Compiler: `c++ (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0`.

| Profile | Calls before | Calls after | Probe skipped | Timer metadata equal |
| --- | ---: | ---: | --- | --- |
| wasi_no_cycles | 1001 | 21 | true | yes |
| wasi_pfs | 1001 | 1001 | false | yes |
| wasi_cycles | 12012 | 12012 | false | yes |
| native_no_cycles | 1001 | 1001 | false | yes |
| native_cycles | 12012 | 12012 | false | yes |
| wasi_unavailable | 1 | 1 | false | yes |
| wasi_zero_first | 1 | 1 | false | yes |
| wasi_other_clock | 1001 | 1001 | false | yes |
| wasi_seconds | 21 | 21 | false | yes |
| wasi_ftime | 1001 | 1001 | false | yes |

All four mutations were detected: `cycle_guard`, `pfs_guard`, `native_guard`, `frequency`.

## SQL timer selection

Result: `SELECTION_UNIT_PASS`.

| Profile | Treatment | Exit | Frequency | Delta for 20 ms | Correct |
| --- | --- | ---: | ---: | ---: | --- |
| wasi | before | 3 | 0 | 0 | false |
| wasi | after | 0 | 1000000 | 20000 | true |
| native_cycles | before | 0 | 1000000000 | 20000000 | true |
| native_cycles | after | 0 | 1000000000 | 20000000 | true |
| native_no_cycles | before | 0 | 1000000 | 20000 | true |
| native_no_cycles | after | 0 | 1000000 | 20000 | true |

Both one-sided reversions were rejected:

- `static inline double timer_tracker_frequency()`: frequency=0, delta=20000, correct_20ms=false.
- `ulonglong measure() const`: frequency=1000000, delta=0, correct_20ms=false.

## Source bindings

- calibration `mariadb_source_commit`: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`
- calibration `source_before_sha256`: `442aef4799c12fa99dba80659c2af49fe1dcf8ae0949ccf32a55087af8a0cf32`
- calibration `source_after_sha256`: `3b1529d68aa9352cb473bfffa14ab19a7db0f116260e27cee9c8c6d752a69787`
- calibration `patch_sha256`: `e51d1f3119f6f079810bdec6be2c5924d91d23f066811506c6e1bdb5d32429ee`
- selection `source_patch_sha256`: `e51d1f3119f6f079810bdec6be2c5924d91d23f066811506c6e1bdb5d32429ee`
- selection `mariadb_source_commit`: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`
- selection `patch_sha256`: `e51d1f3119f6f079810bdec6be2c5924d91d23f066811506c6e1bdb5d32429ee`
- selection `header_before_sha256`: `b1448683d58426071ff95a4fe95868eb1d9884de490bf6919e701bfe23cb5748`
- selection `header_after_sha256`: `44274055f6e399fb640f6016cd95c191765ec9b22bc9025a4f6adef9db605aa7`
- selection compiled source, before: `489f50c48111754568f89194588bc5791cf0a559f52b5c9362ac6623776279de`
- selection compiled source, after: `5135de92ab231d2a01dacfe2eeca040c0217ef5868d4c5c1cc6c92123aa40d36`

## Limits

Controlled clocks, exact C initializer; no actual-guest timing or performance claim.

Exact methods with stub clocks; not actual guest/SQL/runtime evidence.

Original output hashes are in [reduction.json](reduction.json). No result is
rebound to the later installed candidate or promoted to platform acceptance.
