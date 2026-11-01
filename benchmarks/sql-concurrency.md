# Issue #68: why the MariaDB pool becomes concurrency 1

2026-11-02 diagnostic checkpoint; no product correction or adoption.

**The setting comes from upstream MariaDB startup work combined with the pinned
WASIX recipe, not a wrong CPU count from the Go host.** The host reports 8 CPUs,
MariaDB initially chooses concurrency 16, and InnoDB temporarily changes it to
`innodb_read_io_threads` while loading the saved buffer-pool cache. The
`lite4mariadb` recipe sets that variable to 1. The pool returns to 16 afterward.

This identifies the origin of the concurrency=1 observed in the
[previous queue/wake investigation](https://github.com/masahitojp/mariamem/blob/3b8884889a4d8bf80abb97ce99407e84432e322b/benchmarks/sql-wake.md).
That checkpoint tied four ~800 ms page waits to delayed queued work, while
notification-to-return took under 0.1 ms. This checkpoint does **not** reproduce
those long waits or demonstrate a performance fix. Native MariaDB runtime parity
has not been measured; the same upstream mechanism can apply to a native server
with matching settings. Calling this a WASIX-only bug would exceed the evidence.

## What was observed

Two instrumented processes, P1 with one child and P8 with eight children, on Apple
M1 / 16 GiB / macOS 27.2, Go 1.27.3, GOMAXPROCS=8, CGO_ENABLED=0. All nine children
passed the 1,000-row/sum500500 pristine oracle, isolated update/read oracle and
cleanup checks. The root was snapshotted and closed before the children ran.

All nine restored children followed this sequence; instance IDs are process-local.

| Phase/caller | Explicit argument | Effective pool concurrency |
| --- | ---: | ---: |
| Pool construction / Fn16609 | 0 (derive default) | 16 |
| Startup recovery / Fn18568 | 1 | 1 |
| Recovery finished / Fn18568 | 0 | 16 |
| Background buffer-pool load / Fn17498 | 1 | 1 |
| Background load finished / Fn17498 | 0 | 16 |

The fresh root had only the initial 16 event in each process. Every recorded
host CPU count, guest `sysconf(84)` result and C++ hardware-concurrency result was
8. Both traces had zero dropped events (16,842 and 55,150 recorded events).

| Run | Children | Background concurrency=1 spans | Maximum COUNT/SUM time | COUNT >100 ms |
| --- | ---: | ---: | ---: | ---: |
| P1 | 1 | 14.376 ms | 7.970 ms | 0 |
| P8 | 8 | 2.380–55.492 ms | 38.190 ms | 0 |

These timings locate events in diagnostic runs. Logging and stack capture affect
scheduling; they are not uninstrumented benchmark results or tail-frequency
estimates. No fresh corrupt-seed/delay-control campaign was run here; the earlier
recorder controls retain their original receipt. Analysis negative controls below
only test the new configuration assertions.

## Source attribution

Pinned MariaDB source: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
Pinned lite4mariadb recipe: `24be9371a2f6c71250a2356631ad6feab2280b02`.

- [buf0dump.cc lines 697–710](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0dump.cc#L697):
  `buf_dump_load_func` sets pool concurrency to `srv_n_read_io_threads`, calls
  `buf_load()`, then resets it. This path is ordinary upstream code, not a WASIX
  conditional. The generated Fn17498 structure and its event stacks match it.
- [lite4mariadb.c lines 334–342](https://github.com/shyim/lite4mariadb/blob/24be9371a2f6c71250a2356631ad6feab2280b02/wasm/lite4mariadb.c#L334):
  the WASIX launch recipe explicitly supplies `--loose-innodb-read-io-threads=1`
  and disables native AIO. Its SHA256 matches `guest/input.json`:
  `c0a959b6755d3463de31d9d08d2a43031cc418a332768a0956ebfd5046e15526`.
- [ha_innodb.cc line 19644](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/handler/ha_innodb.cc#L19644):
  upstream `read_io_threads` default is 4. Buffer-pool dump at shutdown and load
  at startup default to true (lines 19442 and 19493). These are source defaults,
  not observations from a native server run.
- [srv0start.cc line 1618](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/srv/srv0start.cc#L1618):
  recovery also restricts the same pool and then resets it, explaining the first
  pair of changes. Generated/source correspondence is structural, not newly
  recovered WASM debug symbols.

The canonical portability patch selects simulated AIO. No matching override of
read-I/O thread count or buffer-pool-load policy was found in the product guest
patches. Neither the 400 ms maintenance timer nor the 500 ms long-task threshold
was changed in this experiment.

## Recommendation and stopping point

Continue #68 with one bounded A/B: disable **startup buffer-pool cache loading**
in an experimental guest configuration, keeping I/O-thread count and pool timer
policy unchanged. Compare the same restored-child SQL/row/cleanup oracles and
queue events against the baseline. This targets cache warmup metadata, not schema
or seed data. It is a proposed experiment, not an adopted default or a proven fix.
Changing the Go host or increasing timers/threads now would obscure this test.

To claim improvement, a subsequent run must observe the original slow queue path
in its baseline and compare it with the altered path; absence in another nine
children is insufficient. Native matching-configuration execution and an
uninstrumented performance comparison remain separate missing evidence. No native
acquisition/build was undertaken here. This checkpoint stops after identifying
the caller and configuration source, within its 2-process/9-child budget; it does
not expand into a native build or broad campaign.

## Identity, evidence and reproduction

- Product v0.6.0 source commit: `b3b3b46a8807482ad3f96725af86e031fe369b01`;
  tag object: `b57183b08d48884840111e8b53daa500734337f0`.
- Measured harness source: `d951670c187846d40f0f101f71d5d83f03de79f7`.
  Clean product/tag identity was checked with `scripts/git_identity.py` before
  build. The Go binary records that clean harness revision.
- Eight diagnostic overlay files, including a new event recorder, retain
  before/after hashes in [results](forkcompare/results/overlay-hashes.json).
  No canonical product, guest patch or generated source was edited.
- [Compact events](forkcompare/results/compact.json),
  [summary](forkcompare/results/summary.json),
  [source correspondence](forkcompare/results/source-correspondence.json),
  [archive identity](forkcompare/results/raw-reference.json) and
  [checksums](forkcompare/results/SHA256SUMS.json).
- Raw archive: evidence commit `e9a6094e7a7b8f6271d3dc98031c10919976e62b`,
  path `raw.tar.gz`, SHA256
  `4b335e1ce5cd2de71792fec78ffae79aa57df85f81005de6b85d73f561aa00d7`.
  It retains reports, event traces, samples, input identities and pinned source
  excerpts; workspace prefixes are normalized with original/published member
  hashes. Raw data is on its evidence ref, not this report branch.

After cleanup, compact-only verification is read-only:

```sh
python3 benchmarks/forkcompare/analyze.py --results benchmarks/forkcompare/results --check
```

For full raw-to-compact verification, extract the checksum-verified evidence
archive into a disposable directory and add `--evidence <extracted-directory>`.
The checker verifies the configuration sequence, caller stacks, CPU values,
summary and checksums. Altered CPU observations and altered summary are rejected.

For a new runtime observation, create a disposable experiment workspace at the
measured harness commit, clone the pinned product into `temp/product`, copy
`benchmarks/forkcompare/run.py` to `evidence/run.py`, and run its `--phase build`
then `--phase pilot`. The driver requires the exact Go/platform profile and clean
source identities; it creates diagnostic overlays and builds with `-trimpath`.
`--phase measure` intentionally refuses an expanded campaign. New timings need
new receipts and must not replace these observations.
