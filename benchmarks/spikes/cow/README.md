# Isolated CoW characterization / proof

Source: accepted wasm2go HEAD `965da8c9d2702e6ecdd830d684e8463d31e94311`.
See [report](../../cow-feasibility.md) and [compact evidence](evidence.json).
Darwin/M1 observer only; generated code and binaries remain ignored under a separate `go.mod`.
Never copy templates into normal packages. No production Snapshot/Fork implementation.

## Reproduce

From the mariamem root, reuse the previous spike's isolated generated module and unchanged legacy guest.
Fresh output directories are required. Build completions must precede measurements.

```sh
cp -R benchmarks/results/wasm2go-execution/import-patched benchmarks/results/cow/profile-replay
python3 benchmarks/spikes/cow/setup_profile.py benchmarks/results/cow/profile-replay
cd benchmarks/results/cow/profile-replay
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o profile-probe .
cd ../../../..
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/cow/characterize.py \
  --binary benchmarks/results/cow/profile-replay/profile-probe \
  --helper build/bench/process-cost --host build/cow-spike/mariamem-host \
  --guest build/wasm2go-legacy-eh/artifact/mariamem-legacy-eh-O2-compatible.wasm \
  --output-dir benchmarks/results/cow/content-replay --runs 3
```

Repeat `characterize.py` with `--os-only` and a different output directory for physical growth.
The host is built from unchanged `./cmd/mariamem-host`; `build/bench/process-cost` comes from
the existing `benchmarks/process_cost.c`. Localhost and macOS process-inspection access are required.
ORM measurements require the existing dogfood Python environment.

One initialized-memory sharing proof:

```sh
cp -R benchmarks/results/cow/profile-replay benchmarks/results/cow/proof-replay
python3 benchmarks/spikes/cow/setup_initial_image.py benchmarks/results/cow/proof-replay
cd benchmarks/results/cow/proof-replay
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o proof-probe .
cd ../../../..
COW_BUILD_INITIAL_IMAGE=benchmarks/results/cow/image-replay \
  benchmarks/results/cow/proof-replay/proof-probe instantiate
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/cow/proof.py \
  --binary benchmarks/results/cow/proof-replay/proof-probe \
  --image benchmarks/results/cow/image-replay --helper build/bench/process-cost \
  --output-dir benchmarks/results/cow/proof-replay-results
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/cow/inspect_mapping.py \
  --binary benchmarks/results/cow/proof-replay/proof-probe \
  --image benchmarks/results/cow/image-replay --helper build/bench/process-cost \
  --output-dir benchmarks/results/cow/mapping-replay
```

`fresh` uses the existing Go heap backing; `anon` privately copies the image into mmap;
`cow` uses a private view of the same readonly image. No sharing of running Go state.
Default proof trials are 10 single starts per mode and 3 groups per mode at ×4/8/16.
The image precedes MariaDB startup, so these are fresh DB starts, not prepared DB forks.

`summarize.py --results benchmarks/results/cow --output <file>` compacts the accepted
`characterization-resident`, `os-only`, `proof-measure`, and `mapping` directories.
Raw resident hashes and vmmap output remain local; public evidence contains no machine paths.
One bounded proof only; optional private filesystem loader/export are observation utilities,
not a filesystem sharing prototype.
