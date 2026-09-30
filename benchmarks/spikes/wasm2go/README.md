# Isolated wasm2go feasibility experiments

These are feature reductions and small, deliberately incomplete adapters. They
are not mariamem runtime implementations and are not imported by normal Go/Python
paths. `.go.txt` files are driver templates copied into ignored generated modules.
The guest and its verification, caches, sessions and snapshot semantics are intact.

Use the original release WASM whose SHA256 is
`d49402efec834414527537f639c9a11e5709bf8642357d34d33c7cfa471322d3`.
The native release `.wasmu.json` records the same hash. Retrieve the original:

```sh
gh run download 36685140023 \
  --name release-guest-wasm-400b7f564277b0627c3f0400c3e07e18fa0598d8 \
  --dir build/wasm2go-spike/release-guest
```

Build the unmodified [pgmem-pinned converter](https://github.com/shibukawa/wasm2go-fork/tree/ac98bcf00c17d8531f0c071a9836d0b50975e7ff)
at `ac98bcf00c17d8531f0c071a9836d0b50975e7ff` with Go 1.26.8. Use wasm-tools
1.259.0. Tool dependencies stay outside production `go.mod`/`go.sum`.
Set `SPIKE_CONVERTER` and `SPIKE_WASM_TOOLS` to their binary paths:

```sh
python3 benchmarks/spikes/wasm2go/inspect_guest.py \
  --guest build/wasm2go-spike/release-guest/mariamem.wasm \
  --wasm-tools "$SPIKE_WASM_TOOLS" --output-dir benchmarks/results/wasm2go-spike/inspection
python3 benchmarks/spikes/wasm2go/attempt.py \
  --guest build/wasm2go-spike/release-guest/mariamem.wasm \
  --converter "$SPIKE_CONVERTER" --output-dir benchmarks/results/wasm2go-spike/fresh-attempt
GOTOOLCHAIN=go1.26.8 python3 benchmarks/spikes/wasm2go/reductions.py \
  --converter "$SPIKE_CONVERTER" --wasm-tools "$SPIKE_WASM_TOOLS" \
  --output-dir benchmarks/results/wasm2go-spike/reductions --host-shims
```

An unsupported conversion/compile/import is an expected retained result, not an
overall successful guest execution. Driver assertions check limited adapter
results; execution exit zero by itself is insufficient (the default OS-root FS
probe returns an errno). `--case` selects individual fixture stems.
Both conversion drivers require unused generated/case directories so stale
files cannot be mistaken for successful conversion. They create an output-root
`go.mod` before conversion, including failure cases, to keep generated `.go`
files outside the product module's `go test ./...` traversal.

For imported-memory diagnosis, apply `imported-memory.patch` with
`git apply --unidiff-zero` **only to a separate converter source copy**, build a
separately named binary, and run:

```sh
GOTOOLCHAIN=go1.26.8 python3 benchmarks/spikes/wasm2go/reductions.py \
  --converter "$SPIKE_MEMORY_CONVERTER" --wasm-tools "$SPIKE_WASM_TOOLS" \
  --output-dir benchmarks/results/wasm2go-spike/imported-memory-shim --case imported-memory
```

The patch exposes imported-memory metadata to the emitter. It is not general
host-owned memory import linking. The futex adapter implements only the
changed-value path and rejects blocking. The path-open adapter rejects all
extended flags. The thread-exit adapter handles only normal worker exit, with a
small generated-package wait hook; it does not handle main/process exit/signals.
The filesystem driver explicitly chooses MemFS instead of the default OS-root
filesystem. None of these adapters can initialize MariaDB.

The source inspection and Wasmer control also use existing product provenance,
`guest/resident.inc`, `guest/snapshot_fs.inc`, `internal/guest/guest.go`, and
`build/bench/isolation-go --init-diagnostics` with the exact release native bundle.
The control has reached SQL through Wasmer; it is not a generated-Go result.

See [report](../../wasm2go-feasibility.md) and
[retained evidence](../../wasm2go-feasibility-evidence.json). Raw commands/logs,
generated sources and executables remain ignored. No performance claim follows
from the small-module execution times or binary sizes.

## Legacy EH toolchain experiment

The experiment uses WASIXCC 0.4.7 / LLVM distribution 21.1.206 / Binaryen 133 /
sysroot v2026-07-03.1. The existing local Linux arm64 image has ID
`sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`.
Release CI uses Linux x86_64; this local host difference is recorded.

Prepare a fresh, ignored work directory. Copy the pinned preparation scripts,
guest overlays, input lock and the five cached source archives into a disposable
product root. Never run these settings on the production build directory:

```sh
SPIKE_WORK="$PWD/build/wasm2go-legacy-eh-replay"
mkdir -p "$SPIKE_WORK/product/build/downloads"
printf 'module example.com/legacy-eh-build\n\ngo 1.26.0\n' > "$SPIKE_WORK/go.mod"
cp -R scripts guest release "$SPIKE_WORK/product/"
cp build/downloads/lite4mariadb-source.tar.gz \
   build/downloads/mariadb-connector-c-source.tar.gz \
   build/downloads/wolfssl-source.tar.gz \
   build/downloads/pcre2-10.47.zip build/downloads/fmt-12.2.0.zip \
   "$SPIKE_WORK/product/build/downloads/"
python3 "$SPIKE_WORK/product/scripts/prepare_guest.py"
cmp "$SPIKE_WORK/product/build/prepared-source.json" \
    build/wasm2go-spike/release-guest/prepared-source.json
mv "$SPIKE_WORK/product/build/source" "$SPIKE_WORK/source"
cp benchmarks/spikes/wasm2go/legacy_eh_toolchain.sh \
   benchmarks/spikes/wasm2go/eh_probe.cpp "$SPIKE_WORK/"
```

Run with the recorded image (verify its ID first), an isolated bind mount and
network disabled. The commands below correspond to the successful final method:

```sh
docker run --rm --network none --mount "type=bind,src=$SPIKE_WORK,dst=/work" \
  mariamem-wasix-build:0.4.7 bash /work/legacy_eh_toolchain.sh probe
docker run --rm --network none --mount "type=bind,src=$SPIKE_WORK,dst=/work" \
  mariamem-wasix-build:0.4.7 bash /work/legacy_eh_toolchain.sh build-no-postopt
docker run --rm --network none --mount "type=bind,src=$SPIKE_WORK,dst=/work" \
  mariamem-wasix-build:0.4.7 bash /work/legacy_eh_toolchain.sh postopt
python3 benchmarks/spikes/wasm2go/inspect_guest.py \
  --guest "$SPIKE_WORK/artifact/mariamem-legacy-eh-O2-compatible.wasm" \
  --wasm-tools "$SPIKE_WASM_TOOLS" --features all \
  --output-dir "$SPIKE_WORK/inspection"
python3 benchmarks/spikes/wasm2go/legacy_eh_inspection.py \
  --before benchmarks/wasm2go-feasibility-evidence.json \
  --after "$SPIKE_WORK/inspection/inventory.json" --output "$SPIKE_WORK/comparison.json"
```

`build` is the retained failed alternative: preserving legacy at every CMake
post-link -O2 step hits malformed prototype-only function probes. The final
method keeps the documented legacy mode, disables the wrapper's automatic
post-link step during configure/build, then runs the existing -O2 stage on the
valid full guest without `--emit-exnref`. No source/exception/threading feature
was disabled. `--all-features` is deliberately absent from postopt: it emitted
compact imports in an intermediate diagnostic, which the current Wasmer rejects.

Attempt the current AOT path before any wasm2go retry:

```sh
WASMER_DIR="$SPIKE_WORK/wasmer-home" build/tools/wasmer/bin/wasmer compile \
  "$SPIKE_WORK/artifact/mariamem-legacy-eh-O2-compatible.wasm" \
  -o "$SPIKE_WORK/artifact/mariamem-legacy-eh.wasmu"
```

In this experiment Wasmer 7.4.2 rejected legacy `try` during validation, so the
MariaDB runtime equivalence gate was not passed and wasm2go continuation stopped.
Do not interpret successful WASM validation or identical import signatures as
successful MariaDB execution. The inspector handles named/quoted function IDs;
unsupported compact/multiline import output fails instead of returning an
incomplete inventory. Original feasibility evidence remains a historical record.
