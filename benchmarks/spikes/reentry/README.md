# Ready-state reentry boundary experiment

Source: `5676f901239c5ba4935c10061b8895216c212505`.
See [report](../../reentry-feasibility.md). These tests do **not** resume a ready MariaDB.

Reuse the accepted prepared-clone module, binary, clean files and initialized image.
Generated files remain in ignored results directories with their own `go.mod`;
tracked templates are `.go.txt`. No production source or guest build setting changes.
The same bounded imported-memory/function-index converter patches and WASIX host apply.

From the mariamem root, with `WASM_TOOLS` pointing to an installed wasm-tools binary:

```sh
python3 benchmarks/spikes/reentry/setup.py \
  --source-module benchmarks/results/cow/prepared-clone \
  --output-dir benchmarks/results/reentry \
  --wasm-tools "$WASM_TOOLS" --converter build/wasm2go-spike/wasm2go-memory-shim
cd benchmarks/results/reentry/semantic
GOTOOLCHAIN=go1.26.8 go test -race -v ./generated -run TestSemanticWorkerRebind -count=20
cd ../module
# Supply the absolute path to the existing clean base; go test runs in generated/base.
GOTOOLCHAIN=go1.26.8 REENTRY_PREPARED_FILES="$PREPARED_FILES_ABSOLUTE" \
  go test -race -v ./generated/base -run '^TestReentry' -count=3
cd ../../../..
.venv/bin/python benchmarks/spikes/reentry/observe.py \
  --binary benchmarks/results/reentry/module/prepared-probe \
  --prepared-files benchmarks/results/prepared-clone/capture/base \
  --linear-image benchmarks/results/cow/initial-image \
  --output-dir benchmarks/results/reentry/observe --runs 3
```

Localhost permission is needed for the existing observer. Samples are diagnostics,
not coherent captures. The two-second idle interval observes ordinary inactivity;
it does not coordinate worker ordering. No timing configuration is changed.

- `semantic-worker.wat`: one bounded work unit, explicit completion and join. Retain
  guest data/globals, discard execution, instantiate fresh agents and resume **at a
  semantic entry**, with new logical identity and separate mutable-global TLS.
  Not musl pthread, not an InnoDB worker, no arbitrary continuation serialization.
- `component-test.go.txt`: the actual generated base's waiter queue cannot be
  recovered from bytes; old wait still wakes correctly. Also rebind regular MemFS
  logical descriptors for actual redo/fixture files plus an unlinked file, preserving
  dynamic FD numbers, file identity, offsets and flags. Two private copies prove
  reads, writes, rename/unlink and close isolation. No live Go object is cloned.
- `observe.py`: accepted prepared files are reopened with **fresh** MariaDB execution;
  fixture COUNT1000, idle, table export quiesce, global read lock, unlock and shutdown.
  Numeric generated-function IDs identify frames only in this exact artifact, never
  serve as restore addresses or a proposed production contract.

Regular-file proof excludes stdio, sockets, directories, duplicated descriptor
aliases, OS advisory locks and outstanding I/O. Full rights enforcement is not
present in the inherited experimental host. It is not a complete FD serializer.
Results must not be used as ready-heap child memory/latency measurements.
