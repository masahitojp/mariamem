# MemFS attribution evidence

See the [Human Review](../memfs-limited-attribution.md). JSON is compacted without
dropping keys or numerical values. Local paths use `<experiment-work>`,
`<repository>`, `<user-home>`; trailing text whitespace is removed. Original and
archived SHA256/lengths are in `archive-index.json`. Empty process outputs are
omitted, with command/campaign returncodes retained.

The committed `benchmarks/spikes/memfs-attribution/instrument.py` and templates
produce the experiment-only support files from exact canonical preimages. Their
manifest and two independent replay receipts preserve both observer versions.
These outputs deliberately do not update canonical provenance or release guards.

Replay with a new disposable workspace, 6 GiB owned budget and 8 GiB minimum
free reserve. Use clean standalone clones in `<work>/temp/control` at
`a8137b8b444f86068d3128a291e3a848adfdfd56` and `<work>/temp/observed` at
`c3a527d26ceaaad74f5480ac1469ed586716366c`. Create `temp/gocache`, `temp/go-tmp`,
`temp/tmp`, `evidence`; copy archived scripts into `temp/`. Go1.26.8, native
macOS arm64, C compiler and permitted localhost/OS counter access are required.
Dependencies/toolchain must already be available or separately downloaded.

Run:

1. `python3 <work>/temp/guard.py` — focused observer/contract tests, correctly
   stamped builds, existing process-counter helper and all 24 cases. Pair order
   alternates, each process contains at most one active DB. No optimization.
2. `python3 <work>/temp/guard.py timer` — one same-source 10 MiB/8-table Fresh
   run with aggregate resize time enabled; not part of the paired medians.
3. Advance only the observed clone to
   `1c639ceb4516ff5e21ec245dfb319e0508698e8f`, keeping it clean. Run
   `python3 <work>/temp/guard.py events` — focused tests, stamped bounded-event
   build, one same-case run and pure arithmetic current/1.5 growth replay.
4. `python3 <work>/temp/analyze.py` and `phase_medians.py` — regenerate scalar
   summaries and check primary final mapping counters. The event variant is not
   silently pooled with primary samples.

The guard samples disk every 5 seconds and bounds the task to 3,600 seconds;
individual commands have recorded limits, ordinary DB scenarios 180 seconds.
Historical `guard-primary.py` and `guard-with-timer.py` preserve the earlier
driver versions. Final `guard.py` supports all three named modes. Use fresh output
paths rather than overwriting these archived observations. Record all failures;
returncodes/source stamps/counts/coverage limits fail closed in the scripts.

Binary identities are recorded per build; times and binary bytes may vary with
replay environment/path. Independent instrumentation replay is source-output
identity, not formal production Wasm→Go regeneration or release acceptance.
