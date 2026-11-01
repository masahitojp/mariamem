# Issue #68: evidence before a read-I/O candidate

2026-11-02; additional bounded evidence, no candidate adoption.

**Hold candidate progression as a resolution of #68.** Read4 still produces
367.143 /375.639 /387.507ms COUNT waits in the new same-binary phase trial.
The earlier read4 zero-tail result remains true for its own144 children, but is
not a reliable elimination claim. No evidence of faster typical server init is
present. The one-DB memory increment is small in this local profile.

The strongest counterpoint is that phase-file/trace recording changes scheduling
and may change tail incidence. This follow-up is not an uninstrumented speedup
replication. Nevertheless, actual read4 waits falsify a claim that the setting
alone removes the symptom; this warrants narrowing the recommendation before
paying for guest regeneration. Read4 may be a partial mitigation, but its benefit
and the residual wait mechanism are not established sufficiently for adoption.

## Evidence checklist

| Requested evidence | Observation |
| --- | --- |
| Child distribution / threshold counts | Old plain trial re-reduced; new phase trial retained separately |
| Existing phase attribution | All required existing guest marks captured; long waits occur in post-ready COUNT |
| One-DB RSS p50/p95 |20 fresh process pairs, one held DB per process, own G0 subtracted |
| Rotation and identical host binary | Fixed alternating orders; single binary hash; pinned guest data proof shows one argv byte |
| macOS replication | Both old and new trials are macOS M1; Ubuntu is NOT RUN here |

These are observation PASS results, not proof of a completed latency fix or
both-platform candidate acceptance.

## Child distributions: earlier plain trial

144 children per variant,3 fresh P8/48-child processes. P50 is median; p95/p99
use sorted index floor(p×(n−1)); with144 samples, p99 can omit the two largest
values, so threshold counts and maxima are retained alongside it.

| Interval (ms) | read1 p50/p95/p99/max | read4 p50/p95/p99/max |
| --- | --- | --- |
| Fork |76.251 /124.393 /178.215 /189.248 |76.438 /102.541 /111.814 /113.555 |
| Ready through SELECT1 |88.191 /140.115 /189.643 /192.403 |88.042 /115.009 /123.998 /128.951 |
| COUNT |4.393 /18.011 /375.960 /784.487 |4.460 /13.011 /17.241 /51.928 |
| Full child incl cleanup |108.788 /203.379 /455.563 /889.948 |111.689 /141.524 /153.048 /169.072 |

COUNT >50/100/250/500ms counts are read1 **3/3/3/1**, read4 **1/0/0/0**.
Full-child >250ms is3→0, but its median slightly increases. Thus the earlier
27.1% batch-median reduction is a local tail/batch observation, not a27% faster
ordinary Fork, server init or child. Full threshold tables and run-qualified
slow-child labels are in legacy-distribution.json. Old source/receipt is retained.

## Same-binary phase trial

Again144 children per variant. Fresh-process order is1→4,4→1,1→4.

| Metric | read1 | read4 |
| --- | ---: | ---: |
| Fork p50/p95 |74.667 /99.077ms |75.573 /102.067ms |
| COUNT p50/p95 |4.669 /17.685ms |3.747 /13.654ms |
| COUNT >100 / >250 / >500ms |2 /2 /1 |3 /3 /0 |
| COUNT max |787.083ms |387.507ms |
| Full child p50/p95 |108.900 /130.710ms |108.954 /135.253ms |
| Batch values in paired run order |807.715 /1469.314 /671.033ms |807.632 /737.639 /839.330ms |
| Batch median |807.715ms |807.632ms |

Read4 is faster in one pair, nearly equal in one and slower in one. The earlier
all-three-pairs shortening and27% median effect do not repeat in this instrumented
comparison. Do not pool these results with the previous plain runs to estimate
tail frequency: observation overhead and binary differ.

| Existing guest interval | read1 p50/p95 | read4 p50/p95 |
| --- | ---: | ---: |
| open_begin→server_init_complete |59.188 /86.241ms |59.061 /85.245ms |
| server_init_complete→routine_schema_complete |1.169 /7.144ms |1.172 /7.083ms |
| open_begin→routine_schema_complete |62.280 /87.207ms |62.307 /89.746ms |

No shift of hundreds of milliseconds into server init appears. For the three
read4 slow children, server-init durations are61.329 /70.586 /72.881ms and their
post-init-to-routine durations are1.016 /3.373 /0.999ms. Their subsequent COUNTs
are375.639 /367.143 /387.507ms. Read1's two slow children likewise complete
startup before the393.621 /787.083ms COUNT waits. The observed user delay is
after ready in SQL, rather than hundreds of milliseconds spent synchronously
inside the measured server-init interval. Background page prefetch can still
continue after ready and is not ruled out by these marks.
These phase markers do not capture completion of every background startup task;
readiness and background quiescence are different boundaries. New residual waits
have no queue-level instrumentation, so their exact pool cause is not declared
identical to the earlier800ms cases solely from timer-shaped durations.

## One-DB RSS

Each value is MiB;20 fresh processes per condition, paired alternating order.

| Process observation | read1 p50/p95 | read4 p50/p95 |
| --- | ---: | ---: |
| G0: Snapshot holder, no live DB |50.344 /50.641 |50.438 /50.719 |
| G1: exactly one live DB, post-SQL held |129.828 /130.156 |130.406 /130.938 |
| Per-trial G1−G0 |79.430 /79.828 |79.867 /80.266 |

Compute the read4-minus-read1 increment within each round first: paired
p50 **+0.383MiB**, p95 **+1.016MiB**, range **−0.609 to+1.625MiB**.
This small observed increment does not reproduce a34MiB one-DB cost. It also
cannot attribute the earlier process maximum to one outlier DB or rule out a
parallel-only allocation/GC/peak effect. The resource probe holds one DB and
measures RSS; it is deliberately not a full resource-envelope campaign.
Full individual paired observations remain in summary/compact evidence.

## Corrections to the requested premises

The previous trial was already macOS27.2 arm64 / Apple M1, not Ubuntu. Its
actual fresh-process order was read1→4, read4→1, read1→4. These are retained in
the old source-bound receipt; no receipt is relabeled.

The old maximum RSS difference of about34MiB is between **whole processes**,
each executing48 children with at most8 simultaneously live. Dividing that
maximum by48 does not estimate individual-DB memory. It also does not locate
the increment in a single DB or prove a uniform increment across8 live DBs.

The referenced [memory/session envelope](memory-session-envelope.md) is an older
native/AOT/Wasmer runtime study. Its roughly320MiB/DB is marginal **Ubuntu PSS**,
while the historical macOS measure is footprint. This trial observes current
v0.6.0 generated-Go process **RSS** on macOS. Source, runtime, platform and metric
differ; adding these deltas to320MiB or quoting them as a comparable percentage
would be invalid. The present trial supplies its own matched G0→G1 baseline.

## Observation boundary

One host binary selects the unique `--loose-innodb-read-io-threads=1` startup
argument byte before any guest instance starts. The same binary is used for all
read1 and read4 processes. The initialized guest data hashes differ by exactly
that one argv byte; generated executable functions, canonical WASM, all other
arguments and host source/overlays are common. This remains an experiment,
not a rebuilt guest whose canonical provenance hash has changed.

`MARIAMEM_TIMING_DIR` enables the existing guest `MARIAMEM_GUEST_TIMING` marks.
The linked runtime stores startup-timing.json in MemFS, while the current host
reader looks in the transfer directory; simple enablement does not deliver the
guest record there. A diagnostic-only overlay registers a reader for that
already-closed MemFS file and lets the existing post-ready recorder consume it.
It does not invent new phase markers, change SQL or alter engine policy. Both
settings use that identical bridge. This is a known observation adapter, not a
product timing-delivery fix.

The phase comparison repeats fixed P8/48-child fresh processes in order1→4,
4→1,1→4. Detailed queue instrumentation and latency-triggered stack capture are
disabled. Guest-file and host-trace recording still add observation overhead;
the previous plain trial retains ownership of its uninstrumented-guest result.
Guest phase differences are computed only within each guest monotonic clock:
open_begin→server_init_complete and server_init_complete→routine_schema_complete.
COUNT/Fork/ready times are host intervals. Independent clock origins are never
subtracted or combined to invent a perfectly aligned timeline.

The RSS probe uses20 matched round-robin pairs (1→4 on even pairs,4→1 on odd
pairs), each condition in a fresh process. G0 holds the prepared Snapshot with
no live DB. Exactly one child is held after successful SELECT1, aggregate,
isolated update, verify and profile check; the supervisor observes3 RSS samples
5ms apart before allowing cleanup. Per-trial G1−G0 uses the median of those3
held samples. P50/p95 describe20 independent process increments per condition,
not48 sequential children or a lifetime high-water mark divided by a count.
Paired difference is computed from each pair's two increments before percentiles.
Go heap/GC, host and engine memory remain included; this is process increment
with one live DB, not uniquely attributed InnoDB allocation. The held probe is
not used for latency claims.

No forced GC, buffer resizing, native-AIO selection, write/purge tuning or
400/500ms timer changes are made. Effective settings and SQL/isolation/cleanup
are validated in every process. Missing phase files or memory samples fail
the observation rather than becoming zeros.

## Source and execution identities

- Product v0.6.0 source commit: `b3b3b46a8807482ad3f96725af86e031fe369b01`;
  annotated tag object: `b57183b08d48884840111e8b53daa500734337f0`.
- Measured harness commit: `51d1c1620f0d3d2523a262250a9533baa8cfab4d`.
  Product/tag/clean source checked with scripts/git_identity.py before build.
  Go1.27.3, CGO0, GOMAXPROCS8, macOS27.2 arm64, Apple M1,16GiB.
- All48 accepted processes use the **same host binary** SHA256:
  `b7297f2b12d5de360d2b67b1f29fd091c8afe289083ed10a390ad5b7e1ba5e1d`.
- Canonical guest WASM provenance stays
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
  No new WASM is built. Effective generated data is6,856,219bytes; byte428683
  is ASCII49→52 (`1`→`4`), preserving all lengths/offsets. Baseline payload SHA256
  `6111bfe83de71695517e3d9f25fed842d4a43bfc6ae774815abafd81af9064dd`;
  read4 payload
  `05a18a05924f85ff628aa8955472da3856e3298c53cd3bb3b3632812b48fc698`.
  data-source-check.json reconstructs the pinned generated data and verifies
  both expected hashes, the exact1byte delta, and all48 observations. The
  canonical WASM provenance hash is not relabeled as the altered image identity.

Accepted observations:2 P8/8-child smokes,6 P8/48-child phase processes,40
P1/1-child held-memory processes:344 children,48 fresh processes. Every root
and child observes the expected read value and unchanged effective write2,
purge1,nativeAIO0. All row/isolation/cleanup oracles PASS. An additional invalid
selector control exits before any DB starts; a missing phase mark and altered
byte-count identity are rejected. No extra performance repetitions were added.

## Evidence and reproduction

[Compact](forkcompare/results-io4-detail/compact.json),
[summary](forkcompare/results-io4-detail/summary.json),
[old child distributions](forkcompare/results-io4-detail/legacy-distribution.json),
[data identity proof](forkcompare/results-io4-detail/data-source-check.json),
[negative controls](forkcompare/results-io4-detail/analysis-verification.json),
[raw reference](forkcompare/results-io4-detail/raw-reference.json),
[checksums](forkcompare/results-io4-detail/SHA256SUMS.json).
Compact keeps requested guest marks and selected host observations; complete
trace files/counters and raw RSS samples remain in the archive.

New raw archive is `raw.tar.gz` at evidence commit
`c9786725bb12e29204497d7254168e5415c07105`, ref
`evidence/read-io4-detail-20261102`,294,576bytes, SHA256
`ce491040fb07724d27f03b07ddf11ba1d24359632ab4e6995d19f0cc29658013`.
Its1,571 members include source/overlay/binary identities, all run data and
existing host/guest traces; archive member original/published hashes record
workspace-prefix normalization. The old plain archive retains its original ref
and SHA from [the prior report](read-io4.md).

Read-only verification after disposable build cleanup:

```sh
python3 benchmarks/forkcompare/analyze-evidence.py --results benchmarks/forkcompare/results-io4-detail --check --verify-data-source
```

Run from this Git repository so the exact pinned generated source can be read.
For full raw reduction, extract the checksum-verified new archive and add
`--evidence <new-raw-directory> --legacy-archive <old-raw.tar.gz>`.
No evidence input is overwritten by --check. A fresh runtime reproduction uses
a disposable workspace at the measured harness source, its pinned product clone
in temp/product, and evidence-run.py copied to evidence/run.py. Execute
--phase build, --phase smoke, --phase measure; expected source/platform/toolchain,
disk limits and fixed process counts are enforced. New builds/runs produce new
receipts. No hosted CI, native reference, Ubuntu execution, canonical guest
rebuild, main integration, qualification or release is included.

## Recommendation boundary

Do not advance read4 alone as a resolved SQL-latency candidate. If partial
mitigation is worth pursuing, the next focused question is why read4 still has
~400ms post-ready waits, using the existing queue recorder; no further experiment
was launched here. This does not expand into v0.7 resource tuning. Ubuntu and
ordinary candidate correctness/regeneration checks remain absent, not implicitly
accepted by macOS evidence. The earlier27% result is retained as a local sample;
its broad interpretation is superseded by this evidence.
