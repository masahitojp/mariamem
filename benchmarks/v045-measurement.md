# v0.4.5 Snapshot and suite characterization

These are completed local observations, not universal performance promises.
No Snapshot optimization is adopted for v0.4.5. Use Fresh for cheap setup;
prepare once and Fork when repeated migration/fixture work justifies the fixed
Snapshot creation cost. Neither payload size nor test count alone decides this.
README remains focused on that user choice, not internal performance tables.

## Identity and conditions

Runtime/Go capture/Python host source:
`34eaea1df86b57765a4d8b0840845a33d539065f`, independently qualified on macOS15
arm64 and Ubuntu24.04 x86_64 by [run 37994377940](https://github.com/masahitojp/mariamem/actions/runs/37994377940).
Measurement machine was **local macOS27 arm64**, not those CI machines.
Go1.26.8, GOMAXPROCS2, Python3.14, PyMySQL1.2.3; private disposable scratch.
Exact platform string, binary hashes/buildinfo and package pins are in the raw data.
Public host override bound the Python SDK to that authenticated binary.

Crossover executable source:
`f0a06f4d0e39756fe7839783fc00dbcc2a8ca0c9`; only the existing OwnedPrepared
benchmark and README differ from the qualified source. The clean binary's real
embedded VCS identity was checked; library/SDK/guest inputs are unchanged.
This is not a claim that f0a06f4 itself received native qualification. No handwritten
override of tag/source or binary identity was used.

Campaigns ran sequentially; no competing benchmark/build. Three trace-disabled
trials per size, each with 16 Forks; attribution is a separate single trace-enabled
trial. Crossover uses three trials alternating Fresh/Fork order. Cold outliers and
approximately one-second tails were retained. Small n does not establish robust
Snapshot p95 or platform-independent thresholds.

## Full public Snapshot and import

| Logical payload | Actual prepared state, approximately | Go Snapshot median | Go Fork-ready p50 / p95 | Python import median | Python Fork-ready p50 / p95 |
| --- | ---: | ---: | ---: | ---: | ---: |
| minimal | 138.1 MiB | 383.6 ms | 54.0 / 63.9 ms | 127.8 ms | 51.0 / 55.2 ms |
| 10 MiB | 157.0 MiB | 395.8 ms | 61.4 / 66.0 ms | 143.3 ms | 57.6 / 61.3 ms |
| 100 MiB | 262.0 MiB | 660.6 ms | 56.7 / 61.9 ms | 234.1 ms | 53.6 / 58.9 ms |

Payload rows contain 1024 bytes each; 10/100 MiB have 10240/102400 rows.
Minimal state still includes 96 MiB redo, 12 MiB ibdata and three 10 MiB undo files.
Startup percentiles pool 48 child samples per size; they are not suite percentiles.
Go capture includes the complete public operation. Import copies/verifies an
already-created external artifact; initial artifact creation is outside its timer.
The Python temporary/persisted capture observations from an already-ready child
were one trial each: 411/421, 489/505, 756/795 ms. Child startup is not inside those
Snapshot timers. These distinct boundaries cannot be used as relative speedup claims.

Within the separate traced operations, enumeration is ~0.2–0.3 ms. Dominant
intervals are host quiesce/export (90/106/149 ms, containing nested export
61/68/113 ms), source read/hash (60/71/127 ms), copy (73/63/118 ms), target
read/hash (61/72/131 ms), and owned acquisition (63/72/129 ms).
Do not add nested totals twice or subtract these from untraced medians.
Read/hash are streaming combined intervals; pure shutdown, read and hash CPU are
not isolated. Small allocation-call time does not exclude later page-touch cost.

Logical counters plus inspected acquisition imply five full-data reads, two
materializations and three hash passes for temporary creation. This is not five
physical disk reads. Complete valid owned state is structural; the precise number
of traversals is implementation-controlled. Any proposed pass fusion needs a
separate correctness/ownership/failure-path decision. No pass was removed here.

The earlier v0.4.3/~400 ms observation used different prepared-state boundaries;
do not infer a regression or speedup from the approximate headline. Prior v0.4.4
spike/runtime numbers have their own source/machine/sample conditions. pgmem's
Snapshot figure is architectural context, not a comparable target. Broad repeated
COUNT remains query work (~280 ms on the local 100 MiB case), outside Fork-ready.

## Snapshot lifecycle research boundary

Post-v0.4.6 reconciliation (2026-10-10): this section maps existing evidence to
future questions; it adds no measurements and leaves all original data/SHAs intact.
The host/export/publish code was compared with the released source before using
these boundaries. The [pgmem review](../docs/reviews/pgmem-vfs-design-review.md)
describes stop → VFS Clone → restart of the original server. mariamem's successful
cold Snapshot consumes its source. pgmem's ~10 ms reference is not a matched
experiment or a target derived from these observations.

| Stage | Existing evidence | Still not isolated / future question |
| --- | --- | --- |
| Full public Snapshot | Public operation median and `public_snapshot` trace | Not a missing total; reuse it rather than timing only the host |
| Quiesce / guest shutdown | Host `sessions_drained`, `export_acknowledged`, `guest_stopped` marks; inspected guest joins workers and calls `l4m_close` before snapshot-copy | Pure guest shutdown versus guest snapshot-copy/ack/wait within the host envelope |
| Export | Nested `snapshot_export` trace, allocation marks and data-read/materialized byte counters | Guest-side snapshot-copy is not the same as this host file export; existing allocation-call intervals do not isolate later page touches |
| Enumeration | Existing inventory trace (~0.2–0.3 ms) | Already bounded; no new enumeration campaign justified |
| Materialization / copying | Export write counters and publish `copy_materialized` bytes; measured copy interval | `io.Copy` combines reading and writing; isolate only if attribution would change a decision |
| Validation / hash | Source/target inventory read-hash intervals, traversal counters and inspected acquisition | Streaming read versus hash CPU; counts are logical data passes, not physical disk reads |
| Publish / owned acquisition / cleanup | `snapshot_publish` total and source/target/copy marks; public `source_cleanup_done` and `owned_backing_acquired` marks | Final manifest serialization/write/rename and detailed cleanup are residuals, not separately timed categories; inspect significance before new instrumentation |
| Fork startup / recovery | Separate Fork-ready/startup timings | Outside Snapshot creation; do not add this to Snapshot or compare it with VFS Clone alone |

Here **publish** means committing the Snapshot manifest after materialization and
validation, not publishing a GitHub release. The host/export and substage timers
are nested; they cannot be added as independent costs. Temporary acquisition and
persisted import have different copying paths. Research should reuse the existing
harness and traces, add only a decision-relevant missing boundary, and obtain a
separate Human Decision before changing traversal count, source lifecycle or
InnoDB shutdown mode. The [MemFS Decision](../docs/reviews/memfs-architecture-decision.md)
owns storage measurement/PoC gates. Neither research thread delays stable-guest
migration in v0.5.0.

## Actual suite crossover

Includes preparation, SQL and disposal in both modes. For serial Go suites the
product column excludes diagnostic counter subprocesses; full wall and CPU remain
in the raw data. Parallel totals use elapsed wall, not overlapping operation sums.

| Payload/workload | Databases | Fresh median | Snapshot/Fork median |
| --- | ---: | ---: | ---: |
| minimal read | 1 / 2 / 4 | 0.069 / 0.132 / 0.291 s | 0.464 / 0.525 / 0.656 s |
| minimal read | 32 | 2.511 s | 2.635 s |
| 10 MiB read | 1 / 2 / 4 | 0.619 / 1.256 / 2.540 s | 1.092 / 1.191 / 1.397 s |
| 100 MiB read | 1 / 2 / 4 | 5.696 / 11.462 / 23.971 s | 6.510 / 6.809 / 7.821 s |
| minimal CRUD | 16 | 1.265 s | 1.567 s |
| minimal multi-connection commit/rollback | 16 | 1.280 s | 1.554 s |
| 10 MiB, multi-connection, 4 workers | 8 | 3.509 s | 2.038 s |
| 64 schema tables, minimal data | 4 | 0.364 s | 1.569 s |

The 10 MiB/2-child edge (~5%) is marginal, not a general rule. At four children
the observed gain is ~45%; 100 MiB gains ~41% with two and ~67% with four.
Simple 64-table DDL alone did not make preparation expensive enough. Reuse pays
when avoided work exceeds Snapshot's fixed cost, not simply because Fork is fast.
Real commits and independent application connections remain part of the workload.

## Resources and comparison limits

Raw counters include CPU, FD before/ready/closed/after and relevant RSS/physical
footprint. Parallel simultaneous peak is not sampled. Physical footprint, RSS,
Go heap and file mapping address space are different measures. Diagnostic timing
and sampling scopes are explicit; do not attribute all benchmark memory to Snapshot.

Previously completed four-test local container controls remain historical pilot
data in the JSON. Native guest 13.1.0-embedded and container 12.3.3, Docker Desktop
and three background containers are not equivalent environments. Shared truncate/
reseed retains server/session state. These controls do not establish complete
Product Validation or equal isolation. No further campaign runs in v0.4.5;
comparable realistic scenarios follow Go persisted-load coverage in v0.4.6.

## Evidence and reproduction

[All raw samples, 12 nested traces, manifests, commands and orchestration](v045-measurements/measurements.json),
[crossover CSV with ranges/wall/CPU](v045-measurements/crossover.csv),
[SHA256](v045-measurements/sha256.json). Files moved from the earlier review
directory **without changing bytes**; their original paths remain in Git history
at `02573816dfe37edd76df6f7400a0d05bd915637f`.

Use the recorded source SHAs in a clean normal Git clone, build with the pinned
Go toolchain and verify using `git_identity.verify_go_binary` before measuring.
Replace `<repository>` in recorded commands with the checkout root; recreate
owned `temp/`/`evidence/` paths and dependencies. Campaign orchestration expects
the documented `worktree`/`temp`/`evidence` workspace layout; `product_control.py`
and `resource_control.py` resolve it from their own file location. Capture then
crossover share existing OwnedPrepared oracles and timing/process helpers.

Typical crossover command, repeat both modes in alternating order:

```sh
GOMAXPROCS=2 ./ownedprepared -lifecycle fresh -payload-mib 10 -forks 4 \
  -workers 1 -workload read -helper ./process_cost -out fresh.json
GOMAXPROCS=2 ./ownedprepared -lifecycle fork -payload-mib 10 -forks 4 \
  -workers 1 -workload read -helper ./process_cost -out fork.json
```

Compile `benchmarks/tools/process_cost.c` using `cc -O2`; build the existing
`benchmarks/ownedprepared` executable and host from their recorded SHAs.
Use `import_measure.py` for the independent Python import/capture boundary.
`MARIAMEM_TIMING_DIR` enables separate attribution runs, not primary latency samples.
Keep raw results and hashes, then delete DB files, binaries, downloads and caches.
