# Current-main serial Fork: where the elapsed time goes

2026-11-04. **The dominant interval is MariaDB server initialization: about33.64ms
within a traced Fork of37.57ms. Prepared-file setup and ready-to-return are small.**
The original question about stages3/4/5 is answered for this local fixture.
The next useful configuration comparison is Issue88's16→8MiB buffer pool trial;
this observation does not establish that the buffer pool owns all33.64ms or predict
how much of it can be removed.

## Inputs and method

- Main source_commit: `5c5b4d3ffbc1d9cdcad420d5def523bafb1c874d`, including the
  adopted buffer-pool alignment and finite Fork limiter.
- Measured harness_source_commit: `42e883285197928d2060829e56a7963827e30e20`.
  Standalone clean clone, commit-object identity checked through git_identity.py;
  the diff from main contains only benchmarks/forkstages. Actual binary VCS
  stamp is this harness commit with modified=false, verified before execution.
- Guest SHA256: `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`.
  No guest regeneration or configuration change. MariaDB12.3.3.
- Apple M1,16GiB,macOS27.2 arm64; Go1.26.10,CGO0,GOMAXPROCS8.
- Same1,000 integer rows: COUNT1000/SUM500500. Snapshot consumes the prepared
  root; it is closed before children. Explicit cap1; each child is fully closed
  before the next Fork. No capacity contention.
- Five fresh processes per mode, four serial children per process; alternating
  plain/traced order. One separate warmup process per mode. No primary exclusions
  or additional repeats. Each child verifies its pristine baseline and isolated
  update, retires its TCP connection and closes.

The same overlay binary runs both modes. The three-file observation overlay adds
host-clock callbacks to existing timing marks, reserve/construct and prepared-FS
boundaries, and a read-only handle to the already existing guest startup JSON.
Plain mode disables these callbacks and existing timing. This is a calibration
control, not an independently built unmodified binary. Existing generated code,
engine branches, synchronization, SQL, timers and settings are unchanged.
The overlay generator, preimage/overlay hashes, binary hash/stamp and fixed
plan are in [inputs](forkstages/results/inputs.json).

## Results

Each process contributes its four-child median; the table reports the median
and range of five process medians, in ms. Twenty children are not twenty
independent process repetitions. Rows are nested where indicated; separately
computed medians must not be summed to reconstruct a total.

| Plain public operation | p50 | Five-process range |
| --- | ---: | ---: |
| Fork elapsed |38.362|35.465–39.220|
| Fork process CPU, all threads |48.022|46.842–50.717|
| Subsequent connect/SQL/independent update |4.447|4.294–4.994|
| Child Close after connection retirement |2.162|2.068–2.183|

| Traced Fork attribution | p50 | Five-process range |
| --- | ---: | ---: |
| Whole public Fork elapsed |37.574|34.458–38.677|
| Admission and Snapshot-handle readiness |0.0067|0.006–0.008|
| Handle readiness→filesystem setup begins: API/temp/ownership/pipes/scheduling |0.1618|0.155–0.176|
| **Stage3: filesystem/environment/prepared handles** |**0.0501**|0.048–0.053|
| Stage2: anonymous memory reservation |0.0078|0.007–0.010|
| Stage2: generated module construction |1.4937|1.459–1.546|
| **Stage4 envelope: execute guest→host observes ready** |**35.2321**|32.150–36.440|
| ↳ guest main→ready prepared, nested |34.8574|31.835–36.146|
| ↳ **server_init begin→complete**, nested |**33.6420**|30.806–34.691|
| ↳ routine/schema bootstrap, nested |0.9793|0.919–1.097|
| ↳ execution/readiness residual outside guest main→ready-prepared, nested |0.3063|0.300–0.352|
| **Stage5: host ready response→public Fork returns** |**0.4471**|0.438–0.522|
| ↳ ready observed→TCP listener ready, nested |0.0494|0.048–0.053|

The retained per-child partition also includes the tiny gaps before reserve,
between reserve/construct, and before execute; each child's disjoint host
intervals sum exactly to its public Fork elapsed time. Host callbacks use one
monotonic clock. Guest offsets have a separate origin: only guest durations are
subtracted from their containing host envelope. The0.306ms residual includes
pre-main execution, timing-file output, framing and handoff; it is not pure CPU
or a specifically identified wait.

Snapshot backing Acquire alone is0.0159ms, nested in the pre-filesystem envelope;
prepared-handle attachment alone is0.0469ms, nested in stage3. In the current
path these handles are attached **before** generated module construction.
There is no full database-file copy represented by a large stage3 interval.
The guest restore markers are effectively a no-op here (about0.0002ms): files
are already attached by the host, not restored by that old guest copy path.

Stage5 contains trace serialization/publication as well as ordinary return work.
It must not be presented as the uninstrumented return cost. Traced Fork CPU is
50.092ms versus plain48.022ms. Paired traced/plain wall differences are
−1.16%,−10.18%,+1.74%,−1.39%,−2.57%; a faster traced median does not establish
negative overhead, equivalence or an optimization. Scheduling/background effects
remain. The large server-init interval is clear without needing those differences
to be zero.

## Recommendation and boundaries

Prioritize stage4. Stage3 (~0.05ms) and stage5 (~0.45ms including diagnostics)
do not explain the tens of milliseconds in this Fork. Initial module construction
is about1.5ms. Server initialization occupies roughly nine tenths of traced
elapsed time, but its buffer allocations, engine recovery, worker synchronization,
CPU and waits are not individually timed here.

Continue the separate [Issue88](https://github.com/masahitojp/mariamem/issues/88)
16/8MiB A/B to learn whether reducing buffer-pool capacity materially shortens
that initialization interval and retained RSS, while checking SQL cost. Do not
interpret33.64ms as buffer-pool initialization alone. This task does not measure
RSS, diagnose the post-ready800ms SQL tail, or change any default.

This is one local host/fixture, not Linux replication, product qualification or
release acceptance. Earlier v0.6.0/Go1.27.3 values are separate cohorts, not a
before/after regression comparison. Traced records retain guest-reader closures
until process exit; no memory-footprint inference follows from them.

## Verification, reproduction and storage

Ten primary processes/40 children, two warmups/eight children and a positive
pilot/four children pass SQL/isolation/cleanup. The wrong-seed pilot fails at the
expected oracle and still cleans its one child. All14 processes have empty owned
scratch and zero active mappings/RW/reserved bytes, with no release failure.
Three analysis mutations reject a missing stage, hidden oracle failure and a
mapping leak. Four setup failures occurred before any measurement: wrong runner
cwd, wrong MemFS method, Darwin timeval type mismatch and an obsolete metadata
filename. [Setup records](forkstages/results/setup-attempts.json) preserve them;
no failed receipt is relabelled PASS. Setup/tooling exceeded the initial25-minute
estimate; measurement scope and primary repetition count were not increased.

```sh
python3 benchmarks/forkstages/analyze.py --check
```

This read-only check recomputes the summary from the compact process records,
checks hashes and the negative/analysis controls, without any build/temp files.
[Summary](forkstages/results/summary.json),
[assessment](forkstages/results/assessment.json),
[publication hashes](forkstages/results/publication.json),
[checksums](forkstages/results/SHA256SUMS.json).
These process records already contain every captured startup event; separate
per-scope diagnostic files, binaries, source clones and build caches are redundant.

To rerun: prepare a new disposable workspace with7GiB budget/16GiB free reserve,
clone exact measured harness42e88328 into temp/source (a standalone .git directory
is required for stamping), copy its run.py into evidence, and set
MARIAMEM_EXPERIMENT_TEMP/EVIDENCE to that workspace's directories. Run
`python3 evidence/run.py --phase all` under experiment_disk.py with a1000-second
deadline. The runner owns its Go cache and per-process scratch. Use a new evidence
directory and retain its actual input identities, not these historical hashes.
The analysis source added before the measured build is unchanged in the report.

Only benchmark tooling/results/report are proposed on the experiment branch.
No product/API/guest/generated/release files, main integration or hosted CI change.
