# Fork verification cost decomposition

Status: completed both-platform measurements from [run 36499137263](https://github.com/masahitojp/mariamem/actions/runs/36499137263). No verification work is skipped, cached or optimized.
Reference: [completed outer-boundary probe](fork-gap-probe.md), measured main
`80d922b`: native Resolve p50 57/59 ms and snapshot validation 80/93 ms
(macOS/Ubuntu). These are historical totals, not new sub-stage measurements.

## Source path and interval relationship

Public `Snapshot.Fork` locks/checks the snapshot handle, then calls `start`:

1. `artifacts.ResolveTimed`: platform detection; capture native file metadata;
   read/parse native manifest; validate platform; stat and SHA256 each required
   native file; read/parse AOT sidecar; compare its AOT hash and guest build ID;
   recheck captured metadata.
2. Prepare a private runtime directory and claim the single-use verified native
   identity. This claim rechecks metadata, not artifact contents.
3. Host `StartVerified`: recheck native identity; `snapshot.ValidateTimed` checks
   root/manifest types, root inventory, manifest format/version/guest build/storage,
   walks all data entries, hashes every regular file, and compares full inventory.
4. Prepare transfer directory; recheck native metadata directly before launch.
5. Launch Wasmer; guest reads the validated snapshot through `/snapshot-in` and
   copies it into its own memory filesystem, then initializes MariaDB.

**Source fact:** native and snapshot verification are sequential, disjoint
operations in one Fork. Native verification is inside API startup before host
startup; snapshot verification is inside host startup. They are additive at the
individual-duration level, but adding their separate p50/p95 values does not
reconstruct a measured percentile. Guest restore happens later and is another
read of snapshot bytes, not part of either verification interval.

## Guarantees and repeat work

| Work | Required guarantee | Repetition / ownership |
| --- | --- | --- |
| Native manifest and platform checks | Expected supported bundle layout/platform | Once per startup; Go does not validate an unused packaged host |
| Runtime + AOT + sidecar SHA256 | Bytes match the bundle manifest | Each required native file hashed once; previous redundant AOT scans remain removed |
| Sidecar parse/build comparison | Sidecar's AOT hash matches verified AOT; snapshot guest identity is compatible | Small sidecar reread after its hash; distinct interpretation check, not another large AOT scan |
| Metadata capture/rechecks | Detect mutation/replacement during startup | Repeated inode/size/mode/mtime/ctime checks at distinct handoffs; not content hashing |
| Snapshot manifest/types/inventory | Cold snapshot structure and guest build compatibility; no extra/missing/special entries | Required for this Fork |
| Snapshot per-file SHA256 | Contents match snapshot manifest at validation time | One complete content scan in this Fork |
| Prior Snapshot publish scans | Exported and copied bytes agree before a snapshot is returned | Earlier lifecycle, not trust in a possibly mutable snapshot at later Fork |
| Restore reads | Materialize isolated MariaDB state | Reads the same snapshot data again (~138 MiB / 11 files historically); cannot simply substitute for pre-launch verification |

The native manifest is an integrity/compatibility contract, not independently
signed remote provenance. Release provenance checks remain in release tooling;
this probe does not introduce claims of cryptographic provenance authentication
at startup. Native metadata handoffs preserve the existing concurrent-writer race
boundary; they are not atomic protection against a hostile writer. Snapshot
validation similarly must not be described as atomic verification of all later
restore reads.

## Diagnostic boundaries and measurement plan

Reuse `guest-build-boundary.yml`, `fork_gap_measurement=true`: 30 measurement
samples after two warmups, ×1, 1,000-row fixture on macOS arm64 and Ubuntu 24.04
x86_64. No ×4/×8 or expensive memory diagnostics are needed at this point.
Guest source/toolchain/settings are unchanged; verified WASM/AOT reuse applies.

Two new nested traces, `native_verification` and `snapshot_verification`, retain
monotonic timestamps for metadata/manifest work and per-file open, read+SHA256,
close and comparison. `bytes_read` counts actual logical content bytes returned
by existing `io.Copy` or `ReadFile`; `files_touched` counts file visits, including
repeated metadata/open visits, not unique files. Snapshot entry event names allow
unique data file/directory counts and the bytes/time per file to be recovered.
No extra file reads or stats are added for measurement. Read+hash is deliberately
one boundary: separating hashing from reading would change the operation and
requires a different experiment. Directory walking/stat time is between file
boundaries. Close includes small digest-format/deferred-return bookkeeping.

Existing `stage_summary` reports p50/p95 for each ending boundary and raw JSON
retains counts; the existing stage renderer adds logical-work totals. No per-stage
CPU is fabricated: existing runner/runtime observations retain their original
interval/resolution limitations, including sub-second Ubuntu `ps` CPU zeros.
Diagnostic output is outside each trace end and inside the enclosing lifecycle,
so instrumentation perturbation must be considered when comparing old totals.
Measured results below come from raw per-instance traces. No per-stage CPU
is inferred from file sizes or total elapsed time.

## Completed run and artifact identity

Measured host/harness: `58594f9eaecaf9864caaf452635eb72d54441e7e`, clean
checkout; Go 1.26.8, Python 3.14.7, Wasmer 7.4.2, embedded MariaDB 13.1.0.
macOS 15.7.9 arm64 and Ubuntu 24.04 x86_64 (kernel 6.17.0-1022-azure,
glibc 2.39, SSE2+SSSE3 AOT). Both used 30 samples, two warmups, ×1, 1,000 rows.
No guest/build-input or integrity changes accompanied this instrumentation.

Downloaded common WASM files were rehashed against `reuse.json`; both result
bundles' AOT manifests were rehashed against provenance. Both provenance records
identify the same WASM and handoff provenance; result environment commit matches
the measured host. The guest-producing checkout remains `d44157a`, deliberately
separate from current host/harness identity for verified measurement reuse.

- WASM: `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`
- macOS AOT: `a74927f01e387f8d60fecb5e61a182e344b6a0d2b524d735817e5d632bcc6d4d`
- Ubuntu AOT: `e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb`

AOT bytes are not uploaded in the result bundles, so local result inspection
cannot independently rehash those binaries; CI performs the artifact verification.
Raw JSON/Markdown remain in `initialization-<platform>-58594f9...` artifacts,
with common guest files in `guest-wasm-58594f9...`. Raw data is not committed.

## Measured ×1 decomposition

All timings below are p50 / p95 ms. Aggregates are calculated **per sample first**,
then percentiles; rows and percentile columns must not be added.

| Interval | macOS | Ubuntu |
| --- | ---: | ---: |
| Fork → first SQL | 494.48 / 711.34 | 516.56 / 539.19 |
| Native verification total | 65.29 / 92.76 | 66.42 / 66.95 |
| Native read+SHA256 sum | 50.25 / 75.70 | 66.20 / 66.68 |
| Native platform detection | 13.93 / 21.61 | 0.034 / 0.056 |
| Other native work (metadata/open/close/manifest/comparison) | 0.478 / 0.846 | 0.167 / 0.200 |
| Snapshot verification total | 95.02 / 156.84 | 104.47 / 104.94 |
| Snapshot read+SHA256 sum | 93.73 / 154.04 | 104.07 / 104.55 |
| Other snapshot work (inventory/metadata/open/close/manifest/comparison) | 1.302 / 2.464 | 0.352 / 0.500 |
| Native + snapshot verification (per-sample sum) | 166.16 / 249.53 | 170.83 / 171.49 |
| Restore, later guest interval | 167.62 / 222.69 | 216.97 / 224.79 |
| MariaDB initialization | 82.38 / 154.14 | 82.79 / 99.17 |
| Startup envelope outside recorded guest interval | 53.53 / 86.68 | 38.97 / 40.94 |

**Measured fact:** almost all Ubuntu verification time is content read+SHA256,
not filesystem metadata or manifest comparison. macOS additionally spends about
14 ms launching/reading `sw_vers` for platform detection. This is a real platform
check, not repeated content verification. The new totals differ from the earlier
57–59/80–93 ms run without an optimization; hosted-runner variation and diagnostic
perturbation remain confounders. The Ubuntu p50 gap in this run is 16.56 ms, not
a stable reduction from the previous 32–39 ms gap.

## Native files and small repeated work

| Required file / step | Logical bytes | macOS p50 / p95 ms | Ubuntu p50 / p95 ms |
| --- | ---: | ---: | ---: |
| Runtime read+hash | 12,502,256 macOS / 20,792,088 Ubuntu | 7.59 / 11.04 | 15.18 / 15.44 |
| AOT read+hash | 68,597,800 macOS / 68,999,272 Ubuntu | 41.84 / 65.69 | 50.98 / 51.36 |
| Sidecar read+hash | 200 | 0.026 / 0.069 | 0.007 / 0.009 |
| Sidecar reread for interpretation | 200 | 0.017 / 0.041 | 0.011 / 0.027 |
| Manifest read | 398 macOS / 462 Ubuntu | 0.048 / 0.143 | 0.016 / 0.017 |
| Capture four file identities | no content read | 0.075 / 0.211 | 0.028 / 0.032 |
| Resolve final metadata recheck | no content read | 0.017 / 0.062 | 0.018 / 0.025 |

Native bundle logical reads total **81,100,854 / 89,792,222 bytes** per Fork
(macOS/Ubuntu), with 16 recorded file visits, not 16 unique files. Each runtime
and AOT is hashed exactly once in this call. Repeated AOT hashing removed by the
first FAST tranche has not returned. The only repeated content read here is the
200-byte sidecar: hashing establishes byte integrity; parsing establishes build
compatibility. Even eliminating that reread entirely has a measured microsecond,
not 30–50 ms, opportunity. Further metadata rechecks at claim/host/prelaunch
preserve handoff mutation detection and were already observed as tiny intervals;
the decomposition does not time each of those internal stat calls separately.

## Snapshot files and verification versus restore

The snapshot contains **11 data files and four directories** in its inventory.
It reads 144,885,818 data bytes (**138.174 MiB**) plus a 2,173-byte manifest,
for **144,887,991 logical bytes** and 31 recorded file visits per Fork.
The 11 data byte counts agree across platforms and samples.

| Data file read+hash | Bytes / MiB | macOS p50 / p95 ms | Ubuntu p50 / p95 ms |
| --- | ---: | ---: | ---: |
| `ib_logfile0` | 100,663,296 / 96 | 63.39 / 102.80 | 72.25 / 72.69 |
| `ibdata1` | 12,582,912 / 12 | 7.44 / 12.68 | 9.05 / 9.30 |
| `undo001` | 10,485,760 / 10 | 6.24 / 10.76 | 7.51 / 7.68 |
| `undo002` | 10,485,760 / 10 | 6.28 / 9.99 | 7.52 / 7.54 |
| `undo003` | 10,485,760 / 10 | 6.49 / 12.85 | 7.50 / 7.53 |
| `benchmark_rows.ibd` | 163,840 / 0.156 | 0.103 / 0.415 | 0.120 / 0.190 |

The remaining five files total 18,490 bytes; all have read+hash p50 ≤0.026 ms
on macOS and ≤0.018 ms on Ubuntu. Root metadata is 0.012/0.544 ms macOS and
0.005/0.008 ms Ubuntu; root inventory 0.057/0.156 and 0.017/0.041; manifest
identity parsing/comparison 0.065/0.142 and 0.057/0.122; full inventory comparison
0.021/0.044 and 0.013/0.017. These do not hide tens of milliseconds.

**Derived calculation:** redo alone accounts for a median 68.1% / 69.2% of
snapshot verification wall time, calculated as the per-sample ratio. The fixed
redo/system/undo files account for 99.87% of data bytes. No file is hashed twice
inside this Fork. The existing guest restore subsequently reads the same complete
inventory to materialize a fresh isolated filesystem. This establishes repeated
**bytes**, not a redundant **guarantee**: prior verification rejects corrupt or
incompatible snapshots before launch; restore creates the database's state.
Snapshot construction's earlier export/copy/hash work also cannot prove that a
mutable source is unchanged at a later Fork. No file may be omitted on this basis.

## CPU, attribution and interpretation limits

Existing Fork runner CPU p50/p95 is 0.174/0.215 CPU-sec on macOS and 0.185/0.187
on Ubuntu. Descendant sampled CPU is 0.315/0.425 on macOS and 0/0 on Ubuntu;
Ubuntu's sub-second `ps` accounting is too coarse, not evidence of zero CPU.
Runner accounting includes measurement/cleanup and has no per-stage boundaries,
so it cannot be used as exact hashing CPU or added to an independent lifecycle
interval. The native/snapshot host read+hash totals and runner CPU are consistent
with substantial host CPU work, but do **not** causally separate SHA256 execution,
read servicing, waiting or scheduler time. Logical bytes do not establish physical
storage reads, cache misses or physical-disk latency. No new CPU/memory framework
or expensive memory diagnostics was introduced.

**Conclusion:** there is no measured 30–50 ms redundant check to delete. The
large remaining work verifies distinct native and snapshot contents once. A faster
implementation of those same read+hash operations is not ruled out, but no savings
is demonstrated by attribution alone. Avoiding mandatory scans across calls or
fusing validation with runtime restore would change trust/ownership boundaries;
that needs a separate architecture review, not an optimization disguised as
removing duplication. No optimization is implemented or selected here.

### Verification optimization candidates

1. **Same-guarantee native read+hash implementation:** AOT 41.84/50.98 ms
   median plus runtime 7.59/15.18 ms (macOS/Ubuntu); no duplicate large-file scan.
   Preserve manifest SHA256, sidecar compatibility and startup mutation checks.
   Smallest boundary: a bounded A/B of the existing file read+SHA256 implementation,
   without identity caching. Expected benefit unknown; the measured scan duration
   is a ceiling, not achievable savings. Integrity risk if results, errors or file
   identity handling change; no evidence yet for a 30–50 ms gain.
2. **Same-guarantee snapshot read+hash implementation:** measured aggregate
   93.73/104.07 ms median, mainly redo; no repeated hash within Fork. Preserve
   every file, inventory, format/build and content check. Smallest boundary:
   ordinary hash/read implementation investigation, with full failure tests.
   Expected benefit unknown; deleting metadata cannot provide meaningful savings.
   Risks: CPU/concurrency trade-offs and integrity; no omission or cross-call cache.
3. **Verified-byte ownership across validation and restore (review required):**
   138.174 MiB read once for validation and again for materialization; verification
   total 95.02/104.47 ms and later restore 167.62/216.97 ms. Those costs cannot
   simply be subtracted or both eliminated. Preserve fail-closed prelaunch behavior,
   exact restored contents and mutation semantics. Smallest boundary is an explicit
   trust/transfer design review before any prototype. Expected savings unmeasured;
   scope/semantic risk higher. Stop for that review if avoiding these scans is
   required rather than improving their implementation.
