# Prepared UCA booster reuse: bounded comparison

**Recommendation: continue this approach as a candidate for adoption review.**
The fixed-input experiment reduced Fork work while retaining the measured string
SQL speed. This is one macOS host, not product adoption or release qualification.
The strongest concern is maintaining generated data against the exact Unicode/
MariaDB inputs and safely rebinding a changed guest; the supported scope and
both-platform acceptance for a production candidate remain a separate decision.

| Median metric | Original baseline | Prepared tables | Change |
|---|---:|---:|---:|
| Fork elapsed per child | 36.35ms | 26.23ms | −27.8% |
| Fork host process CPU | 49.49ms | 39.36ms | −20.5% |
| ASCII query elapsed, 1000 rows | 1.589ms | 1.569ms | −1.3% |
| ASCII query host CPU | 1.622ms | 1.622ms | approximately equal |
| Mixed-string query elapsed, 1000 rows | 1.026ms | 1.020ms | approximately equal |
| Whole fixture, setup through cleanup | 575.79ms | 524.88ms | −8.8% |
| Zero-child host RSS | 44.70MiB | 47.67MiB | +2.97MiB |
| RSS increment with one retained child | 78.39MiB | 74.84MiB | −3.55MiB |
| RSS increment with four retained children | 309.97MiB | 296.42MiB | −13.55MiB |
| Absolute host RSS with four retained children | 354.86MiB | 344.03MiB | −10.83MiB |

Child metrics use the median of four children per process, then the median of
five processes. Whole process/RSS readings use the median of five processes.
Each row is summarized independently; subtracting independently summarized
values is not an additive phase decomposition. RSS is host RSS after that
child's SQL, not PSS, peak RSS, or an exclusive allocator measurement.

Five paired Fork changes were −26.8%, −28.6%, −35.4%, −28.0%, −24.7%; whole-fixture
changes were −6.5% to −13.0%. All five pairs improved for those metrics. ASCII
query pair changes ranged −4.0% to +4.7%, and mixed strings −5.9% to +4.5%: this
small sample shows no consistent SQL regression, not a universal non-regression
guarantee. No trial or tail was excluded. Earlier booster-off results in
[Issue106](https://github.com/masahitojp/mariamem/blob/b6fcf1f70e0d3554c392f0158314bbc4c16d67bc/benchmarks/ucaboosteroff/README.md) are a different experiment; this report does
not treat the two trials as a simultaneous three-way measurement.

## What changed

The original MariaDB routines generate numeric comparison tables from the pinned
Unicode14 input. We store the resulting three typed, immutable C tables inside
the guest. utf8mb3 and utf8mb4 versions were compared byte-for-byte and proved
identical, allowing reuse of the three tables across those two encodings.
The existing optimized comparison consumers remain enabled.

The experimental constructor selects prepared data only for exact built-in
UCA1400 default PAD ai_ci IDs2048/2304, levels0/1/2, and their expected shared
UCA-level object. Other IDs, tailorings and detached objects use the original
producer. Source/version inputs are fixed by the build; the constructor does
not claim a generic runtime version-negotiation interface. Different first
initialization routes can fall back to dynamic generation; no speedup is claimed
for every alias, strength, tailoring or caller sequence.

Each table is918,016 bytes, with no internal pointers. Typed data totals
2,754,048 bytes. The actual guest initial-data payload grew6,856,219→9,610,331
bytes, an increase of2,754,112 (tables plus64 bytes of other data). BSS size stayed
8,982,576 bytes. This is numeric-data reuse, not a snapshot of a running guest,
threads, FD state or InnoDB. It does not resolve/abandon Issue103's separate
initialized-state-template idea or Issue84's prewarmed DB pool idea.

The net result includes avoided allocation/population and the changed static
image. We did not separately profile each population loop, allocation or page
fault inside Fork. No claim is made that these measurements explain parallel
scaling or the whole pgmem performance difference.

## Increased initial-data copy cost

A supplementary Go probe calls the **actual unchanged `base.MemoryInit`** with
both guests' real data segments and destinations. It uses a fresh32MiB anonymous
mapping, five alternating pairs per mode, separate warmup, full output-byte
oracles and matching source/data hashes. Mapping/prefaulting, oracle and unmap
are outside the timer; no guest or database executes in this probe.

| Standalone copy component | Baseline | Candidate |
|---|---:|---:|
| Fresh mapping wall | 0.729ms | 0.990ms |
| Pre-touched mapping wall | 0.345ms | 0.498ms |
| Fresh mapping minor-fault delta | 419 | 587 |

This demonstrates a small extra copy cost in this component. It is not an
exclusive Fork phase measurement, and must not be subtracted from Fork latency
to infer an exclusive table-generation duration.

## Correctness and safety matrix

| Check | Result |
|---|---|
| Original Unicode-data tool + original booster producer, native ASan/UBSan | PASS |
| Six whole-table native roundtrips, repeat generation, cross-encoding equality | PASS |
| One-cell corruption and unmatched-selector controls | PASS, native scope |
| Actual candidate constructor: six hits, detached/different-tailoring fallbacks | PASS, native scope |
| Exact source/header/table bytes entering guest compilation | PASS |
| Guest build and development native host SQL smoke | PASS, UNQUALIFIED |
| Actual guest root and Fork: six full original-vs-prepared table comparisons each | PASS |
| Fresh native12.3.3 vs baseline/candidate SQL corpus and Snapshot replay | PASS |
| Isolation, UNIQUE1062, cleanup, wrong-seed failure controls | PASS |
| Fixed experimental binding and eleven rejection/state-restoration checks | PASS |
| Five alternating fresh-process pairs and read-only summary replay | PASS |
| Actual MemoryInit component, twenty measured copies and four warmups | PASS |
| Ubuntu / complete product qualification | SKIP, outside this bounded spike |

SQL coverage is the unchanged Issue106 fixture: utf8mb3/utf8mb4 UCA1400 ai_ci
ordering, pairwise STRCMP/equality/less-than, WEIGHT_STRING, GROUP BY, UNIQUE,
NULL/empty/PAD/NUL, case/accents/combining characters, and explicit selected
contraction probes including Czech tailoring. Finite corpus equality does not
establish arbitrary collation/application compatibility.

Guest verification uses the existing host `MARIAMEM_TIMING_DIR` diagnostic route
to pass `MARIAMEM_GUEST_TIMING` into the guest. **Only in this experimental guest**,
that also enables original table construction and full `memcmp`; each match must
cover918,016 bytes. Verification includes that extra computation and is untimed.
Its retained diagnostic phase files cannot be used as fastpath performance
measurements. Primary runs strip all MARIAMEM_/MYSQLMEM_ variables and use no
verification or timing instrumentation.

The accepted worker ABI's nineteen generated bodies were compared in full.
Allowed differences are the proven zeroed-BSS relocation(+2,754,112), one
byte-identical read-only C string, and explicit symbol mapping: Fn219 moved
p7→p3; Fn4068 became Fn4069 in p7. Call bindings are compared after that exact
mapping. TLS505 bytes and module G0–G3 are identical. No new worker instruction,
layout field or reclamation semantics was admitted. Selected complete bodies,
initializer, TLS and source fixture are retained for read-only proof replay;
wrong address, wrong callee and extra instruction controls are rejected.

The development installer exception is bound to one manifest hash, exact guest,
whole generated-source inventory/data hash and all nineteen body hashes. Original
Module/yield/body checks still run; temporary adapter state is restored even on
failure. Unknown inputs and release-mode overrides fail. This experiment-specific
installer and exploratory history are not proposed for automatic main integration.

## Identity, method and reproduction

- Product behavior base: `bc00b8e66e5fd57bc9b2127001faf8e05952b417`.
- Guest source origin: `f24c308bb6758e97722f4cb26bcb1de7c2df16b9`.
- Host-stage source: `d6c7e8b6` (full SHA in results/inputs.json); only
  scripts/generate_runtime.py changed from the guest origin.
- Baseline guest: `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`.
- Candidate guest: `c71cb10c1a042c3014f748981545685a840f92ff7d9f6bf4b7053bb0472992fb`.
- MariaDB source: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, version12.3.3.
- macOS27.2 arm64,16GiB,8 logical CPUs; Go1.26.10/CGO off/GOMAXPROCS8,
  Python3.14.10/PyMySQL1.1.2; native12.3.3 arm64 image
  `sha256:23ccfa2f2df26837c8f397a8f9a070ad728768c095d246edd07cd8d24e9ec40c`.
- Four **sequential** children retained in one shared host per process; cap4.
  Each fixed ASCII/mixed query scans1000 rows, is primed, then repeated20 times.
  Five alternating baseline/candidate fresh-process pairs; warmups separate.
  This is not a parallel-four throughput campaign. Host CPU uses a calibrated
  libproc Mach-tick conversion; whole process wall includes setup and cleanup.

Native generators use unmodified pinned source fragments/headers and the original
uca-dump, with a minimal platform configuration. They are prototype tooling, not
a new Unicode implementation or a generally portable production build recipe.
Use Python3.14 for tools/*.py, with the disposable workspace path as the first argument:
acquire → build_minimal → prepare_data → build_producer → check_prepared →
make_patch → check_constructor. Initial source/build identity must be checked
before compilation. The raw table header is generated into the experimental
patch, not edited manually. The compiler input manifest confirms all three
changed files equal the native-tested inputs.

A pinned18GiB budget and16GiB minimum free space guarded the experiment. The
first Docker source preflight stopped before compilation because an output mount
hid tracked build/go.mod; supplying identical bytes fixed the mount. That
failure is retained, not relabelled. The subsequent single guest compilation
completed in841.37s. Time extension from the earlier trial was not reused.

Full guest reproduction uses the pinned builder/toolchain/commands and guest
origin above. Translate once for the explicit ABI proof, then advance only the
host-stage installer and supply the byte-exact experimental-binding.json through
MARIAMEM_EXPERIMENT_THREAD_BINDING to the existing UNQUALIFIED development
pipeline. Native/guest checks must pass before timing. Source/guest/binary/tool
hashes, full inventories and original/published normalization hashes are retained.

[Primary results](results/summary.json), [all ten records](results/measurements.json),
[controls](results/checks.json.gz), [inputs](results/inputs.json),
[copy component](results/copy-summary.json), [checksums](results/SHA256SUMS.json).
Provenance uses a shared base inventory with explicit `$ref`/`$base`/`remove`/`set`
deltas. Published path prefixes are normalized; provenance hash references refer
to original artifacts, not normalized copies.

After deleting all build/temp files, only Python's standard library is needed:

```sh
python3 benchmarks/ucaboosterreuse/results/analyze.py \
  benchmarks/ucaboosterreuse/results --check
python3 benchmarks/ucaboosterreuse/results/check_worker_evidence.py \
  benchmarks/ucaboosterreuse/results/worker-evidence.json.gz
python3 benchmarks/ucaboosterreuse/results/check_copy.py \
  benchmarks/ucaboosterreuse/results
```

Performance results do not authorize product adoption, main integration,
qualification, version selection or release. A production candidate needs a
maintainable generated-data recipe and both-platform checks under its separately
reviewed scope; no new release gate is implied by this local spike.
