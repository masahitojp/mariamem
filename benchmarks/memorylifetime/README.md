# Snapshot memory-lifetime diagnostic

Public direct-link API, isolated executable, macOS only. This is attribution,
not a canonical benchmark or production runtime path. It does not modify the
runtime, force production GC, or implement the proposed copy pre-sizing change.

Use the canonical Go toolchain and keep **all** raw work outside `publish/`:

```sh
work=/path/to/ignored/work/memory-lifetime
mkdir -p "$work"
GOTOOLCHAIN=go1.26.8 go build -o "$work/probe" ./benchmarks/memorylifetime
cc -O2 benchmarks/tools/process_cost.c -o "$work/process-cost"

# Each command is an independent process; do not run trials concurrently.
"$work/probe" -scenario fresh -out "$work/raw/fresh-1" -helper "$work/process-cost"
"$work/probe" -scenario snapshot -out "$work/raw/snapshot-1" -helper "$work/process-cost"
for n in 1 4 8 16; do
  "$work/probe" -scenario forks -workers "$n" -out "$work/raw/forks$n-1" -helper "$work/process-cost"
done
# Repeat into distinct directories (two or three trials suffice).

# Extra views only; their overhead changes sampling/scheduling.
"$work/probe" -scenario forks -workers 16 -vmmap -live-gc \
  -out "$work/raw/forks16-map" -helper "$work/process-cost"
# No MariaDB in this reduced Go allocator control.
"$work/probe" -scenario heap -out "$work/raw/heap-1" -helper "$work/process-cost"

python benchmarks/memorylifetime/summarize.py "$work/raw" \
  --source-sha "$(git rev-parse HEAD)" --binary "$work/probe" \
  --output "$work/values.json"
GOTOOLCHAIN=go1.26.8 go tool pprof -top -inuse_space \
  "$work/probe" "$work/raw/forks16-map/live_children_gc.heap"
GOTOOLCHAIN=go1.26.8 go tool pprof -top -alloc_space \
  "$work/probe" "$work/raw/snapshot-1/snapshot_retained_gc.heap"
```

The harness uses existing timing opt-in, `runtime.MemStats`, heap profiles,
canonical process counters and built-in `lsof`; optional `vmmap`/`footprint` are
separate observations. No third-party profiler. Profiles before explicit GC can
lag the GC epoch; use the `*_gc.heap` views for reachability. `KeepAlive` pins
closed handles through the corresponding collection checkpoints. Two helper
capture pipes appear in lsof counts; compare equal boundaries.

The Snapshot API combines export/shutdown/publication/validation. The harness
records that combined boundary and does not invent interior checkpoints.
`-live-gc` keeps children operational while collecting an up-to-date live profile.
All GC and FreeOSMemory calls are diagnostic only. Numeric views and profiles
are consecutive, not simultaneous; these observations cannot replace canonical
latency or active per-DB physical-memory measurements.
