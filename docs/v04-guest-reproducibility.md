# v0.4 legacy-EH guest reproducibility

This is the generated-Go candidate's build-time contract. It does not change
public v0.3 runtime selection, SQL semantics or Snapshot/Fork behavior.
WASM is a build intermediate for this candidate.

## Comparison boundary

Compare independent builds of the **same v0.4 legacy-EH recipe**. Do not require
identity with the old new-EH production artifact, or with an arbitrarily selected
output of the nondeterministic legacy-EH compiler. Existing artifact trust gates
remain exact-file SHA-256 gates; there is no canonical-digest exception.

## Cause and toolchain decision

The original SDK pins WASIXCC 0.4.7 / LLVM distribution 21.1.206 (compiler reports
WASIX clang 21.1.2), distribution tag source
`wasix-org/llvm-project@98c00cb849c94742b2b29918bb414d236c83ae97`.
The lock separately records runtime-source revision
`6bb93a243f6d15855f485f5aec3810d9e2de150d`; it must not be cited as the
compiler binary revision. Build-compiler and prebuilt sysroot/runtime-library
source identities need separate provenance in the release source closure.
It lacks LLVM upstream commit
[`fd76c9bdf10383ae536d8c504dafe3bd91947d83`](https://github.com/llvm/llvm-project/commit/fd76c9bdf10383ae536d8c504dafe3bd91947d83).
Pointer-keyed DenseMap iteration in WebAssembly exception lowering produces
unstable `try/delegate` nesting. Repeated compilation of InnoDB `log0log.cc`,
function `log_write_up_to()`, gives identical machine IR before CFG Stackify and
two forms immediately after it. This propagates through the object, InnoDB and
MariaDB archives, linked WASM and Binaryen output. It is code-section variation,
not timestamps, debug/custom sections or a post-processing-only problem.

The isolated validation recipe uses official **LLVM/LLD 23.1.0**, commit
`ea7d852a70e8bdfaf601d6626a760f9771b2c4b4`, containing the upstream MapVector fix.
WASIXCC 0.4.7, the existing `v2026-07-03.1` legacy-EH sysroot, pthread/shared
memory settings, MariaDB sources and Binaryen version_133 remain unchanged.
There is no binary patch, retry-until-a-preferred-SHA loop, EH normalization or
exception disabling. The full 23 compiler upgrade is the validation bridge; a minimal
21 compiler backport is not assumed equivalent without its own verification.

## Pinned bootstrap

The required inputs are explicit local cache files, fetched from:

- [LLVM-23.1.0-Linux-ARM64.tar.xz](https://github.com/llvm/llvm-project/releases/download/llvmorg-23.1.0/LLVM-23.1.0-Linux-ARM64.tar.xz), SHA-256 `cfb31bfc713ef453248bf5bd026312f838ad6c52c25623e987cb6a340f3050d4`.
- [Ubuntu libicu70_70.1-2_arm64.deb](https://ports.ubuntu.com/ubuntu-ports/pool/main/i/icu/libicu70_70.1-2_arm64.deb), SHA-256 `ac68372cf4a976e6a206858fd9b28c68e49d37d650b9b8653270038a6e7bc174`.

ICU is a build-tool dependency of the official LLD distribution, not a guest or
product runtime requirement. It is extracted only into the isolated LLVM prefix.
No system package or existing SDK is modified. The WASM header profile excludes
native-only `arm_neon.h`, matching the existing WASIX SDK. Stock LLVM publishes
that ARM header; xxHash interprets its presence under WASM SIMD as SIMDe
availability and otherwise fails compilation. The original build selects the
scalar xxHash implementation; this target-header profile preserves that selection
without changing guest sources, hashing behavior or disabling WASM SIMD.
Both compilers directly confirm `XXH_VECTOR=XXH_SCALAR` and
`__wasm_simd128__=1` in preprocessor output.
The bootstrap script verifies both
inputs and records all selected file/symlink identities in `toolchain-inputs.json`.
The initial scripted stock prefix matches the initial probe prefix across 377
entries. The final WASM profile and its complete inventory are recorded separately.

```sh
python3 benchmarks/spikes/generated-go-integration/prepare_llvm23.py \
  --llvm-archive build/generated-go-integration/LLVM-23.1.0-Linux-ARM64.tar.xz \
  --icu-package build/generated-go-integration/libicu70_70.1-2_arm64.deb \
  --output build/llvm23-clean

python3 benchmarks/spikes/generated-go-integration/repeat_guest_builds.py \
  --output build/guest-six-clean \
  --downloads build/downloads \
  --converter-archive build/wasm2go-spike/wasm2go-fork.tar.gz \
  --llvm-dir build/llvm23-clean/LLVM-23.1.0-Linux-ARM64 \
  --trials 6 --parallel 2
```

Each build archives the exact source HEAD and verifies the five guest-source
archives against `release/inputs.lock.json`; no prior source/object directory is
reused. Container identity is
`sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`,
network disabled, Linux arm64. Container paths stay `/work/source` and
`/work/source/build-legacy-no-postopt`; independent host directories vary.
Build flags remain `WASIXCC_WASM_EXCEPTIONS=legacy`,
`WASIXCC_RUN_WASM_OPT=no`, `WASIXCC_WASM_OPT_SUPPRESS_DEFAULT=yes`,
`WASIXCC_WASM_OPT_FLAGS=-O2`, `WASIXCC_WASM_OPT_PRESERVE_UNOPTIMIZED=yes`,
`JOBS=3`. The same explicit Binaryen `-O2`/feature flags follow linking.
`LD_LIBRARY_PATH=/root/.wasixcc/llvm/lib` supplies isolated ICU. LANG, LC_ALL,
TZ and SOURCE_DATE_EPOCH are unset in the container image. No timestamp
normalization is performed. Reports retain UTC times, paths, probe versions,
source preparation identity, flags and raw/final artifact SHA-256 and sizes.

`--guest-build-only` compares recipe outputs without the historical guest pin.
The default replay path retains its historical checksum gate. `--llvm-dir` is
rejected without `--guest-build-only`, preventing implicit adoption of a new guest.

## Stage and compiler probes

```sh
python3 benchmarks/spikes/generated-go-integration/compare_guest_builds.py \
  build/guest-six-clean/run-1/work build/guest-six-clean/run-2/work \
  --output build/guest-comparison.json

python3 benchmarks/spikes/generated-go-integration/probe_guest_compiler.py \
  --work build/guest-six-clean/run-1/work --name compiler-six \
  --llvm-dir build/llvm23-clean/LLVM-23.1.0-Linux-ARM64 --trials 6
```

The comparator records object/archive inventories, build configuration, every WASM
section and changed function-body indexes. The compiler probe uses the exact
CMake flags, preserves original objects and records preprocessed-source and
CFG Stackify before/after hashes. It does not special-case guest addresses.

## Adoption gates

A new guest requires a new explicit guest/generated-source input manifest and a
compiled-guest binding, never a weakened identity check. `setup_audit.py` and
`setup_candidate.py --input-manifest` validate every generated source/assembly
file and bind execution to that manifest's exact guest SHA. Default manifests
remain unchanged until the selected build strategy is accepted for distribution.

Native Ubuntu x86_64 generation/tool bootstrap, clean release CI, corresponding
source/notices propagation and supported-platform acceptance remain required.
The arm64 local bootstrap is not a portable release pipeline. Changing the
compiler pin does not remove MariaDB GPL-derived obligations or the need to
control Go executable VCS metadata separately.

## Six clean builds: result

**REPRODUCIBLE**, without normalization. Source SHA for all six builds is
`98eb7f038b96b8422424800702baa780458e590e`. Each starts with an independent
source archive and empty source/build directory. All 860 objects, archives,
configuration inventories, linked WASM sections/function bodies and postprocessed
WASM sections/function bodies match run 1. Builds run two at a time; no output
selection/retry is used. Full stage timings, UTC timestamps, paths, tool/input
hashes and compiler-pass trials are in
[retained evidence](../benchmarks/v04-guest-reproducibility-evidence.json).

| Runs | Linked WASM SHA-256 (22,051,110 bytes) | Final WASM SHA-256 (18,560,224 bytes) |
| --- | --- | --- |
| 1, 2, 3, 4, 5, 6 | `2b3a7ffdbeda9e9709d266e331b0c5c8c0c03265c81a91d31cbf498daa6ae781` | `5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb` |

The old compiler's six diagnostic runs have one pre-CFG-Stackify hash
(`2c34d5f3…`) and two post-pass hashes (`8c7005bf…`, `a0cad31f…`), split 4/2.
Its ten object-only trials split 4/6 between two outputs. With the pinned LLVM23
WASM profile, all six diagnostic runs have the same pre-pass hash (`5c73be26…`),
post-pass hash (`80eeff7a…`) and object hash (`6f113f6a…`). This removes the
observed two-output nondeterminism in both reduced and full builds. A finite
campaign is evidence of this recipe's reproducibility, not a proof for arbitrary
LLVM inputs or environments. No claim is made that old/new compiler code is
byte-identical or formally equivalent.

## Regeneration and compatibility

LLVM23 additionally emits two `f64x2.relaxed_madd` instructions. The existing
pinned generator first rejects opcode `0x107` at function 13127. The isolated
`relaxed-madd.patch` adds only decoding, SSA/code generation and a two-lane Go
`math.FMA` helper. The Relaxed SIMD contract permits a fixed fused projection;
see the [upstream specification](https://github.com/WebAssembly/relaxed-simd/blob/main/proposals/relaxed-simd/Overview.md).
No fast-math flag, guest patch, instruction removal or SIMD disabling is used.
The minimal WAT fails with the old generator and passes six race-tested cases
with the patch, covering fused cancellation, overflow cancellation, subnormal,
signed zero, NaN/infinity and lane/operand order.

```sh
python3 benchmarks/spikes/generated-go-integration/translate_guest.py \
  --guest build/guest-six-clean/run-1/work/artifact/mariamem-legacy-eh-O2-compatible.wasm \
  --guest-sha256 5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb \
  --converter-archive build/wasm2go-spike/wasm2go-fork.tar.gz \
  --output build/llvm23-translation-clean

python3 benchmarks/spikes/generated-go-integration/setup_candidate.py \
  --source-module build/llvm23-translation-clean/module \
  --guest build/llvm23-translation-clean/guest.wasm \
  --input-manifest benchmarks/spikes/generated-go-integration/llvm23-generated-source.json \
  --output build/llvm23-candidate-clean
```

Use the resulting `module` as the candidate setup input and explicitly pass
`--input-manifest benchmarks/spikes/generated-go-integration/llvm23-generated-source.json`.
The manifest pins guest, converter archive/revision, three automatic patches and
all generated source/assembly/data files. Go1.26.8 builds the converter with
`-trimpath -buildvcs=false`; converter archive SHA is
`1fcd91eecc66e367495d91f34644c68df1ff856a786d00c24fa66061c3dbce0f`.
Two independent fresh converter builds/translations produce identical inventories
of 51 files and identical converter binaries. The full candidate is compiled
against this exact new guest checksum. Historical default pins remain unchanged.

The new candidate passes macOS arm64 generated/base race tests, Go race/Python
integration, SQLAlchemy **44/44**, GORM **32/32**, Snapshot/Fork **50** checks,
raw-wire **38** checks and auth self-test. All 66 imports/signatures and shared
memory limits (4096–32768 pages) match the previous guest; `try_table` and
`throw_ref` remain absent. Legacy EH still cannot be validated by Wasmer7.4.2;
these are structural and behavioral checks, not same-runtime validation.
The unchanged production Wasmer Go race/Python integration also passes.

The source→WASM blocker is resolved for the pinned local recipe. This task does
not switch normal distribution to the new guest, publish artifacts or rerun
performance benchmarks. Previous canonical performance figures still describe
the previous measured guest. Native supported-platform release CI/bootstrap,
runtime-kind-aware distribution/cache migration, failure-path hardening and
source/notices propagation remain release gates.

Final ordinary checks pass: Go test/vet, Python373 PASS/3 SKIP and public-source
420 files. Owned-source check copy excludes only the untouched, pre-existing
untracked npm manifests. The initial timing test TempDir cleanup flake is retained;
unchanged retries pass. Public report paths are redacted to a repository-root
placeholder; raw local evidence digests and WASM bytes remain unchanged.
`git diff --check` passes.

For subsequent local runs use the [external cache/work layout](development-cleanup.md).
Repeated source/build trees may be discarded after the canonical evidence is
retained. The recipe accepts explicit downloads, toolchain and output paths; no
recorded compiler/object output is a prerequisite for regeneration.

## Accepted cold-copy guest update

The A+B integration adopts canonical source recipe
`1687465bcbaff74a334b3e89181c47e66478792c`, with seven added helper C lines to
pre-size cold exclusive output files. No experimental.patch is present. A clean
build produces guest SHA-256
`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`
(18,560,271 bytes), matching the independent experiment artifact. Toolchain,
MariaDB sources, WASIX/shared memory/threading/legacy-EH settings are unchanged.
The fresh canonical converter manifest is byte-identical to the independently
translated experiment inventory; repeated runtime installation is byte-identical.
This is not a claim of six new full builds: the six-build table above documents
the earlier recipe/toolchain reproducibility evidence. New canonical build,
overlay identities, tool hashes and stage results: release/generated-go-build.json.

For current regeneration, use the same explicit cache and LLVM23 build command
above on the pinned recipe, then translate with the new exact guest hash. Pass
`--input-manifest release/generated-go-translation.json` to setup_candidate.py,
and its resulting module to scripts/generate_runtime.py. That installer rejects
any candidate inventory differing from release/generated-go-inputs.json and
recursively transforms all generated packages; no manual generated-Go edit.
Regenerate required compatibility images with scripts/embed_generated_runtime.py
and verify using scripts/verify_generated_runtime.py. Ordinary Go startup does not
use those images. Historical manifest/recipe evidence is retained, not silently
rewritten. No licensing/notices or legacy fallback removal occurs in this update.
