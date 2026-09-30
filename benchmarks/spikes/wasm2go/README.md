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
