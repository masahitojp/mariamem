# v0.4 artifact license inventory

Audit base: `05d85afccefdb61f448ea68e9b29a6e20bcba053`, whose
[hosted verify run](https://github.com/masahitojp/mariamem/actions/runs/37096640237)
returned both-platform/aggregate READY. This packaging-only change creates new
artifact/source/notice identities; that READY does not approve the changed bytes.
No runtime, generated source, guest input or build option changes here.

## Evidence and scope

The canonical linked WASM hash is
`94b2ae2ba97f424faf419daf4e819f2dfeefc8640b529ae19a98ee3579cb7d1b`.
Repeating its accepted Binaryen133 `-O2` recipe with **only `--symbolmap` added**
produced byte-identical final WASM:
`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
Thus the emitted index/name map applies to the actual converter input, not a
different debug build. `--debuginfo` was also tried diagnostically; it changed
runtime sections and is **not** used as final-code evidence.

Match each selected index to an actual `Fn<index>` body in committed generated
Go (not a linkname declaration), and to the prior verified host's `go tool nm`
symbols. [Machine-readable evidence](../release/generated-license-evidence.json)
records patterns, counts, examples, map digest, guest/generated identity and
host hash/source SHA. Some functions disappear through Go inlining/linking;
each retained library has positive native-symbol evidence. Counts are lower
bounds of matching names, not byte contributions or an exhaustive member SBOM.

Actual CMake cache: WITH_SSL, WITH_ZLIB, WITH_PCRE, WITH_LIBFMT are `bundled`.
Actual guest link: wrapper object + `libmariadbd.a`, `-ldl`, pthread/exceptions,
driver-selected WASIX C/C++ sysroot. The final symbols include the libraries
below; configured dependencies alone were not used to justify retention.
The prepared `wasm/CMakeLists.txt` links only `mysqlserver`; its include roots
are the server's source/build `include`. `libmysqld/CMakeLists.txt` uses its own
`libmysql.c`, `lib_sql.cc` and `sql-common/client.c`, not Connector/C objects.
Thus Connector/C stays a preparation/configuration source input; it is not
silently relabeled as the implementation of the retained mysql_* symbols.
`go list -deps ./cmd/mariamem-host` contains only stdlib and mariamem packages;
`go version -m` confirms CGO_ENABLED=0 and no linked Go third-party modules.
wasm2go helper templates are copied/rendered into `code/base` and SIMD files;
the converter MIT text is checked against its pinned archive during packaging.

## Component → artifact chain

Classification concerns implementation code in the normal artifacts. A legacy
license text can remain in the Go module without bundling its engine. `source`
below refers to the common corresponding-source package; full upstream archives
preserve original notices even for build/preparation inputs.

| Component | Classification | Build / guest link | Generated Go / Go module | Python host wheel | Source / attribution |
| --- | --- | --- | --- | --- | --- |
| MariaDB | DISTRIBUTED / DERIVED | compiled server/InnoDB | translated server, e.g. mysql_server_init/query | linked server | full pinned source + changes, GPL2 |
| lite4mariadb / patches | DISTRIBUTED / DERIVED | wrapper/protocol, 7 retained l4m symbols | translated wrapper + source overlays | linked wrapper | full fork source/patches, GPL2, modified-work NOTICE |
| WASIX libc/sysroot | DISTRIBUTED / DERIVED | C/thread/I/O runtime | 51 defined matching support functions, e.g. pthread mutex/clock wrappers | linked support | WASIX source and header sources; original multi-license/musl/cloudlibc texts |
| dlmalloc | DISTRIBUTED / DERIVED | sysroot allocator | dlmalloc/dlfree bodies | native symbols retained | same WASIX archive; original public-domain/CC0 notice added |
| compiler-rt | DISTRIBUTED / DERIVED | sysroot builtins | 5 matching defined functions, incl. __multi3/__udivti3 | native symbols retained | pinned LLVM runtime source; full component license added |
| libc++ | DISTRIBUTED / DERIVED | C++ library/templates | 775 matching defined std::__2 functions | native symbols retained | same LLVM source; full component license added |
| libc++abi | DISTRIBUTED / DERIVED | exceptions/ABI | 27 __cxa functions | native symbols retained | same LLVM source; full component license added |
| libunwind | DISTRIBUTED / DERIVED | EH support | 6 _Unwind functions | native symbols retained | same LLVM source; full component license added |
| wolfSSL | DISTRIBUTED / DERIVED | MariaDB bundled crypto/auth | 1,982 matching defined crypto functions | native symbols retained | pinned wolfSSL source; COPYING + LICENSING retained |
| zlib | DISTRIBUTED / DERIVED | bundled compression | 15 matching defined inflate/deflate/CRC functions | native symbols retained | bundled MariaDB source + zlib license |
| PCRE2 | DISTRIBUTED / DERIVED | bundled regex | 23 matching defined pcre2 functions | native symbols retained | pinned archive + original BSD texts |
| fmt | DISTRIBUTED / DERIVED | compiled/header templates | 61 matching defined fmt functions | native symbols retained | pinned archive + MIT |
| wasm2go helpers/runtime | DISTRIBUTED / DERIVED | converter emits/copies helpers | base/MemFS/SIMD helper implementation | linked helpers | pinned converter archive/patches, MIT (Masaaki Goshima) |
| Go runtime | DISTRIBUTED / DERIVED | normal Go compiler links runtime | consumer's standard toolchain, not vendored module code | linked Go runtime | Go1.26.8 pin + Go BSD text; standard toolchain source not vendored |
| pgmem fixture design | DISTRIBUTED / DERIVED | no PostgreSQL engine link | design attribution in fixtures/lifecycle | Python fixture implementation | preserved MIT attribution; no pgmem DB engine source requirement asserted |
| LLVM23/clang/LLD tooling | BUILD-ONLY | compiler/backend, different revision from sysroot runtime | pins/scripts, no compiler binary/code | absent | exact compiler pin/download retained as build provenance; runtime sources above separate |
| WASIXCC / Binaryen / ICU | BUILD-ONLY | driver, optimizer, compiler-host dependency | recipes/pins, no tool executable | absent | build provenance, not runtime-wheel notices |
| Connector/C preparation input | BUILD-ONLY | prepare_guest installs source for configure | no separately linked connector library; embedded client is libmysqld/libmysql.c | no connector library | full pinned archive/terms retained conservatively for source preparation |
| Wasmer / headless / Singlepass | LEGACY-ONLY | not used in normal build/link/translation | fallback integration source/notices retained, engine external | engine/AOT/notices absent | external engine archive excluded; repository MIT/BUSL/Rust notices retained |
| Native-bundle Rust dependencies | LEGACY-ONLY | Wasmer bundle dependency graph only | old inventories retained, not translated | absent | existing macOS/Linux legacy notice guards unchanged |
| PyMySQL / pytest / xdist | UNUSED | acceptance/optional install, not artifact build/link inputs | dependency declarations/tests, no copied implementation | not copied | independently installed packages retain their own terms |

The [pinned wolfSSL terms](https://raw.githubusercontent.com/wolfSSL/wolfssl/1d363f3adceba9d1478230ede476a37b0dcdef24/LICENSING)
permit GPLv2 election when combined with MariaDB Server. This distribution
records that election and keeps both upstream texts, rather than replacing them
with a generic GPL2 label. [WASIX upstream terms](https://raw.githubusercontent.com/wasix-org/wasix-libc/09503b230e8acc721c1e013ca28a41bf149e4ee2/LICENSE)
include original subcomponent licenses. [LLVM's pinned terms](https://raw.githubusercontent.com/llvm/llvm-project/6bb93a243f6d15855f485f5aec3810d9e2de150d/llvm/LICENSE.TXT)
include the LLVM exceptions; full runtime component texts are preserved rather
than assuming the compiler's license disappears on translation.

## What changes / what remains

`release/distribution-licenses.json` partitions all flat license files, binds
their hashes and the evidence, and records one classification per component.
Unknown/missing/changed license files fail closed. Normal wheel metadata selects
only distributed notices; the explicit legacy wheel mode still selects all.
The five removed **normal-wheel** files are Wasmer-MIT, Wasmer-ATTRIBUTIONS,
Wasmer-Singlepass-BUSL-1.1, Wasmer-Rust-NOTICES and Wasmer-Linux-NOTICES.
Their original bytes remain in both source mirrors and legacy guards.
The zlib text now uses the pinned source's dedicated `zlib/LICENSE`, replacing
the full README previously used as its license file. Original README remains
in corresponding source. Fifteen complete copied upstream texts are checked
against their checksum-verified archives, including the four LLVM runtime texts.

Corresponding source excludes only `wasmer-full-source.tar.gz` (external engine
not distributed). It still includes product/fallback source, repository notices,
every guest/library/runtime/header source input, original lock and converter.
Source manifest binds **both** distributed and repository notice sets plus the
license inventory. Offline preparation and runtime/header source checks remain.
No guest/compiler/runtime source is removed merely because it has no native
dynamic-library dependency. LLVM runtime source remains at its original pinned
sysroot revision, not replaced by LLVM23 compiler source.

This is an evidence-backed component inventory, not a complete final linked-file
SBOM or an independently rebuilt sysroot. Full upstream archives cover originals
and remaining subcomponent notices; this audit does not prune them. No new
license ambiguity requiring removal of guest code was found. Existing sysroot/
toolchain-source closure limitations in [releasing](releasing.md) remain explicit.

## Repeat / verify

Given the canonical linked WASM, use Binaryen133 with the exact recipe in
`benchmarks/spikes/wasm2go/legacy_eh_toolchain.sh`, adding `--symbolmap` and
redirecting stdout to a disposable file. Require the final raw SHA above.
Then `audit_generated_licenses.py` reproduces the small evidence record without
altering generated code or build flags. Paths below are disposable work paths:

```sh
python scripts/audit_generated_licenses.py --linked "$work/linked.wasm" \
  --guest "$work/mapped.wasm" --function-map "$work/function-map.txt" \
  --host "$work/mariamem-host" --output "$work/license-evidence.json"
python -m pytest -q tests/test_distribution_licenses.py \
  tests/test_generated_release.py tests/test_packaging_license_mirrors.py \
  tests/test_runtime_sources.py tests/test_runtime_notices.py \
  tests/test_linux_runtime_notices.py
git diff --check
```

Build both host-only wheel metadata layouts and the exact candidate's new source
archive using normal Release CI before publication. The earlier verify artifacts
must not be relabeled. No CI dispatch, tag or publication is part of this audit.

Local checks: 63 source/notices/provenance/packaging tests passed, exact upstream
license byte verification passed (15 texts), all three existing runtime/header
source coverage checks passed, canonical generated source/image identity passed,
and public source inventory/diff checks passed. Packaging fixtures built normal
macOS and Ubuntu metadata wheels with no Wasmer notices, plus a legacy metadata
wheel retaining all notices. The Ubuntu fixture uses a previously verified macOS
host to test **license selection only**, not Ubuntu runtime/platform acceptance.
Pinned setuptools80.9.0/wheel0.45.1 were used, matching CI. Final-artifact checks
for the changed source/notices must run in the next exact-SHA hosted verification.
