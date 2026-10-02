# Lane B: known-length cold copy experiment

Common base: `6940bf1ac3010a020c8a67cd366d9e26c42c4974`.
Only `experiment/v04-snapshot-preallocation` owns this experiment.
No integration change, canonical benchmark, CoW or GC policy change is proposed.

The helper patch calls POSIX `ftruncate` on the newly created exclusive output
before its existing 64 KiB copy loop. A cold regular source has a known stable
size. Truncate does not move the output offset; extension is zero-filled. This
uses the existing WASIX descriptor truncate import and MemFS implementation,
not a path/address-specific optimization or a global growth-rule change.

Rebuild with the pinned source recipe (the preparation order supports patches
against overlays and archived replay preserves the experiment-branch guard):

```sh
python3 benchmarks/spikes/generated-go-integration/readiness_replay.py \
  --output "$work/guest-build" --downloads "$cache/downloads" \
  --converter-archive "$cache/wasm2go-fork.tar.gz" \
  --llvm-dir "$cache/llvm23-wasm-prefix/LLVM-23.1.0-Linux-ARM64" \
  --guest-build-only
python3 benchmarks/spikes/generated-go-integration/translate_guest.py \
  --guest "$work/guest-build/work/artifact/mariamem-legacy-eh-O2-compatible.wasm" \
  --guest-sha256 "$recorded_experimental_sha" \
  --converter-archive "$cache/wasm2go-fork.tar.gz" --output "$work/translation"
python3 benchmarks/snapshotpreallocation/install_experiment.py \
  --translation "$work/translation" --output "$work/after-source"
```

The installer first validates all raw translation input hashes, the new guest
hash and the *unchanged generated runtime/base inventory*. It then archives the
exact common base, applies the same deterministic import/data transform as
`scripts/generate_runtime.py` to regenerated guest functions, and rebinds all
three runtime guest identities to the explicitly recorded new checksum. It
keeps the canonical hand-written adapters. Its output is external diagnostic
source, not a release artifact; historical platform-image/release pins stay
unchanged. No generated instruction/function/address is manually edited.

Build this harness against the untouched common-base runtime for `before` and
against that external source for `after`:

```sh
GOTOOLCHAIN=go1.26.8 go build -p 1 -o "$work/before" ./benchmarks/snapshotpreallocation
(cd "$work/after-source" && GOTOOLCHAIN=go1.26.8 go build -p 1 \
  -o "$work/after" ./benchmarks/snapshotpreallocation)
```

Run fresh-process trials sequentially during an exclusive measurement window.
Each trial records full `TotalAlloc` delta, before/after HeapAlloc, Snapshot
latency, existing opt-in timing traces, logical published-file inventory and a
heap profile. GC is diagnostic only, **after** every measured Snapshot boundary.
The harness then tests two children, fixture count, write/schema isolation,
rollback and independent shutdown. Existing Snapshot validation tests cover
corruption; native helper roundtrip proves exact byte preservation including
empty and sparse data. Do not compare hashes of independently initialized
MariaDB files as though they must be byte-identical.

```sh
"$work/before" -out "$work/raw/before-1"
"$work/after" -out "$work/raw/after-1"
GOTOOLCHAIN=go1.26.8 go tool pprof -top -alloc_space \
  "$work/after" "$work/raw/after-1/snapshot.heap"
```

Raw profiles/build trees belong outside the public repository. Retain small
checksums, per-trial numeric results and the focused report. Do not claim a
change to Darwin physical accounting from allocation reduction alone.
