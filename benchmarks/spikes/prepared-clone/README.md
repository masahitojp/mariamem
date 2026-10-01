# Prepared persistent-state reconstruction spike

Source: `8658310fce7745c7a8df04bc0aed7d7a6ce5ce14` (`v0.4/cow-spike`).
This is a clean-shutdown filesystem clone with fresh execution state and the previous
thread-free initialized linear image. It is **not a MariaDB-ready heap continuation**.
See [report](../../prepared-clone-feasibility.md).

All generated Go remains under a separate ignored module. Templates are `.go.txt`.
Reuse the previous spike's generated module, unchanged legacy guest and OS cost helper.
Run from the mariamem root; output directories must be fresh.

```sh
cp -R benchmarks/results/cow/proof benchmarks/results/cow/prepared-clone
python3 benchmarks/spikes/prepared-clone/setup.py benchmarks/results/cow/prepared-clone
cd benchmarks/results/cow/prepared-clone
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o prepared-probe .
cd ../../../..
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/prepared-clone/capture.py \
  --binary benchmarks/results/cow/prepared-clone/prepared-probe \
  --output-dir benchmarks/results/prepared-clone/capture
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/prepared-clone/capture.py \
  --binary benchmarks/results/cow/prepared-clone/prepared-probe \
  --output-dir benchmarks/results/prepared-clone/capture-repeat-1
build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/prepared-clone/measure.py \
  --binary benchmarks/results/cow/prepared-clone/prepared-probe \
  --capture benchmarks/results/prepared-clone/capture \
  --linear-image benchmarks/results/cow/initial-image \
  --helper build/bench/process-cost --output-dir benchmarks/results/prepared-clone/measure
PREPARED_FS_IMAGE=benchmarks/results/prepared-clone/capture/base PREPARED_FS_MODE=cow \
  build/sqlalchemy-dogfood/py314/bin/python benchmarks/spikes/cow/inspect_mapping.py \
  --binary benchmarks/results/cow/prepared-clone/prepared-probe \
  --image benchmarks/results/cow/initial-image --helper build/bench/process-cost \
  --output-dir benchmarks/results/prepared-clone/mapping
python3 benchmarks/spikes/prepared-clone/summarize.py \
  --results benchmarks/results/prepared-clone \
  --output benchmarks/spikes/prepared-clone/evidence.json
```

Capture requests the existing `0xfffffffe` guest snapshot frame. Only after the guest
joins sessions, ends MariaDB and returns, and all generated workers join, does the
observer export `/snapshot-out/data` as a readonly base. No live Go object is saved.
`/runtime` and `/sample` are diagnostics, not coherent snapshot endpoints.

Each child gets new MemFS nodes and file offsets, WASI fd tables, thread pool, timers,
and SQL sessions. `cow` maps clean files privately; `copy` copies the same contents
into anonymous mappings. Normal MemFS grow/truncate behavior remains; growing a
mapped file may allocate a private Go array and retains the old map until teardown.
Mappings are unmapped after guest-worker join and observer shutdown.

Single prepared-cow starts: 30; control single starts: 10; ×4/8/16: 3 groups each.
Hash verification is performed once before trials and again afterward. Per-child
product verification, MySQL wire setup, and capture/build time are excluded.
These are exploratory direct-process costs, not public Snapshot/Fork benchmarks.
macOS localhost/process-inspection permissions are required.
