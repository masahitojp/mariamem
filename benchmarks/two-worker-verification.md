# Final v0.2 verification pass

## Verification optimization

Only independent native-file checks and snapshot inventory file digests run in
parallel, with at most two workers per validation call. Native format/platform,
regular-file/executable checks, all three SHA-256 comparisons, sidecar identity,
and before/after startup identity checks remain required. Snapshot root/manifest,
lexical inventory, link/special-file rejection, every content digest/size and full
manifest equality remain mandatory. There is no persistent/path-based trust cache.

All workers finish before returning; failures are selected in original file order.
Snapshot metadata traversal remains serial, hashes run after enumeration, and a
prior file hash failure takes precedence over a later traversal failure. Concurrent
calls remain independent. Snapshot publication also uses the same inventory
validator; both source and copied destination are still hashed in full.

Diagnostic events are synchronized. Individual read/hash events overlap now:
wall spans for independent files must not be summed as serial elapsed time.
Native and snapshot validator total durations remain the useful phase metrics.
The change adds one extra simultaneous SHA-256 stream per call, bounded worker
stacks and per-item result storage; no database/runtime memory settings change.
Physical memory and CPU effects require measurement, not inference from this bound.

The prior isolated Ubuntu probe showed about 41.6 ms combined median saving from
2-worker content verification; that is historical evidence, not this production
implementation's measured end-to-end result. The completed results are recorded below. Unit/race
checks cover complete item visitation, two-worker limit, ordered failures and
existing corruption/mutation checks. Packaged macOS/Ubuntu lifecycle acceptance
and paired measurements are delegated to the existing CI path.

## Hosted CI interpretation

`guest-build-boundary.yml` with `fresh_runner_latency=true` measures five fresh
Ubuntu jobs. Each builds the unchanged serial control at `2e631cd` and the new
production runner, then uses the **same verified frozen AOT archive** for both.
`final_latency.py --production-only --comparison-runner ... --runs 30` alternates
control/production order per round, retaining 30 independent children per side
plus two labelled warmups. Binary hashes and pinned worktree build logs distinguish the intended sources;
see the completed-run VCS-stamp limitation below. The outer environment identifies
the supervising candidate checkout.

Compare paired latency/CPU/memory changes within each job. Do not compare different
CPU models as if they were paired samples. CPU is runner SELF over the broader
batch and sampled runtime descendant delta; startup/exit edges may be missed.
RSS is secondary and can double-count shared mappings; it is not private/PSS.
No material memory regression can be claimed before examining these observations.
The existing `fast_tranche=true` path adds packaged Go/Python acceptance, race
integration and macOS/Ubuntu latency/resource observations.

Previous identical-code jobs ranged from 354 ms to 544 ms p50, associated with
EPYC 9V45, EPYC 7763 and Xeon 8573C. Hosted jobs monitor correctness and paired
regression/benefit; they are **not the absolute 500 ms acceptance environment**.
A hosted runner remaining above 500 ms does not authorize another optimization.

## Final v0.2 benchmark procedure

Use one fixed supported local reference machine, keeping CPU model, OS/version,
architecture, power/resource conditions and native bytes unchanged across runs.
Obtain the exact production AOT bundle used for regression measurement; verify its
manifest/provenance and retain its artifact SHA256. Do not rebuild between sides.
Record the checkout commit and require a clean tree. No source changes, guest
settings or filesystem/cache tuning are part of acceptance.

```sh
.venv/bin/python benchmarks/final_latency.py \
  --native-dir /absolute/path/to/verified-native \
  --production-only --runs 30 \
  --json benchmarks/results/final-v02-local.json
```

The runner records CPU/OS/architecture metadata, commit, Go version, native file
hashes, all raw child reports and min/p50/p95/max. Diagnostics are OFF. Each trial
creates its own 1,000-row prepared fixture outside Fork timing, then measures the
complete public Fork through connection and verified first fixture query. Only
the two explicitly labelled warmups and fixture/setup work are excluded. Keep all
30 measurements, including slow ones; any failed child invalidates the run.

**Acceptance: p95 <500 ms**, with at least 30 independent measured trials on this
fixed reference. Report the full distribution and exact machine/artifact identity.
Do not pool machines or select a passing subset. The command records results; it
does not silently declare or enforce a release gate.

For CPU/memory impact, run the same procedure with the serial control binary via
`--comparison-runner /absolute/path/to/serial-go-runner` (built from `2e631cd`) on
the same machine/artifacts. Retain paired per-round deltas and both distributions.
Report broader runner SELF and sampled descendant CPU separately, plus ready/peak
process-tree RSS and incremental RSS from raw samples. State limitations; use
existing private/PSS/footprint probes only if RSS indicates a material regression.
No claim of per-stage CPU or unique physical-memory accounting is implied.

The fixed-local acceptance has now passed on the M1 reference; see
[the measured local result](final-v02-local-reference.md). If it fails, report NOT MET
separately and stop; no additional architecture/performance work belongs here.

## Completed hosted regression: run 36522659284

[Actions run](https://github.com/masahitojp/mariamem/actions/runs/36522659284),
production candidate `a48e223dac7af603d92ddaba1fe9874ffa8330b7`, completed
successfully. This section reports observations; it does not declare the
fixed-local FAST acceptance complete or authorize another optimization.

### Evidence and source identity

All five fresh Ubuntu jobs completed 30 independent measured trials **per side**
and two labelled warmups per side (64 child reports/job). Diagnostic stage timing
was OFF; no failing/slow child was excluded. Warmups alone are excluded from the
statistics. Both conditions used the same prepared-fixture recipe and native
bytes. Order alternated control/production and production/control each round.

All jobs reported EPYC 7763, four vCPUs, Ubuntu image `20260920.314.1`, kernel
`6.17.0-1022-azure`, Go 1.26.8 and Python 3.14.7. Native and temporary snapshot
paths were on ext4. Thus these five jobs reproduce the previous **slow regime**;
they do not sample all hosted CPU classes.

The downloaded common archive rehashes to
`10e064751c4ffdd176be44831990552bc8c7e87a9aaa7d4261e7cbb2dff5b917`.
Every sealed file hash was checked; each job's manifest, provenance and reuse
seal matches it. AOT remains
`e729fc07d7cb03de6b4bbf5334f0e1da460a8abfff56b0d3661b2688969e73fb`,
WASM `41e3acfb51fe52ad13d9691de0bd3f05619266571e84dd1a0ddf263e082add7f`,
Wasmer 7.4.2, SSE2 + SSSE3. Build provenance retains its original source identity;
reuse does not relabel that as the new Go host checkout. Recorded harness hashes
match the candidate source. Raw artifacts are retained as
`fresh-latency-1..5-a48e223...`, `fresh-latency-input-a48e223...` and
`initialization-<platform>-a48e223...`; local downloads are outside tracked source
at `/private/tmp/mariamem-parallel-36522659284/`.

**Metadata limitation:** the control and production binaries have different
recorded hashes (control `0306b145b0559ca1c174fac9d2dd15592840195861d354cac9b6ba5c9240cc95`,
production `94a04a04862b515964d9b7375137e08f7460ec434421b92d426adfa76789606f`),
but both child Go build-info records stamp the outer candidate revision.
Consequently those records do **not** independently prove the control revision.
The workflow pins full control SHA `2e631cd7e682fda06b43655edb7e8b685ff12be9`;
completed build logs show the nested worktree at that revision and compilation
inside it. This supports the intended serial-source comparison, with a VCS stamp
ambiguity in the nested build that must remain explicit. A future fixed-reference
comparison should build control in a separate checkout and inspect its build
revision, rather than relying on this stamp. No production code is changed in
this analysis, and candidate/release identity is not inferred from the control
stamp.

### End-to-end paired effect

All latency values are ms. Each percentile comes from that job's 30 raw samples,
using linear interpolation; a paired delta is production minus control for the
same round, **not** a difference of independent medians.

| Job | Control min / p50 / p95 / max | Production min / p50 / p95 / max | Paired delta p50 | Faster pairs |
|---|---:|---:|---:|---:|
| 1 | 515.2 / 539.8 / 558.2 / 566.7 | 478.5 / 508.7 / 529.3 / 538.9 | -27.1 | 29/30 |
| 2 | 516.5 / 535.6 / 548.5 / 572.5 | 482.7 / 498.6 / 524.6 / 534.5 | -30.8 | 28/30 |
| 3 | 517.8 / 538.6 / 564.2 / 564.8 | 487.0 / 513.1 / 525.4 / 544.7 | -29.4 | 30/30 |
| 4 | 523.0 / 544.3 / 563.1 / 578.4 | 490.4 / 509.3 / 524.0 / 549.3 | -37.4 | 29/30 |
| 5 | 507.9 / 537.2 / 554.1 / 566.4 | 480.2 / 506.0 / 540.7 / 546.6 | -29.0 | 26/30 |

**Measured fact:** all five job medians and p95 improve. Paired median saving is
27.1–37.4 ms; 142/150 pairs are faster, with eight slower pairs retained. Job p95
improvements range from 13.4 to 39.1 ms. This is a consistent beneficial wall-time
effect; the earlier isolated ~41.6 ms saving did not transfer one-for-one into
end-to-end improvement on these slower CPUs. No additivity is assumed.

Production p95 remains 524.0–540.7 ms on these jobs. This is not a fixed-local
acceptance PASS; nor is it a hosted regression. Per the agreed boundary, it does
not trigger further optimization. Historical EPYC 9V45/9V74 runs cannot be pooled
with this A/B or substituted for a reference-machine result.

### CPU and memory impact

CPU values here are **Go runner SELF ms over the broader batch**, including
hold/cleanup/GC/sampling. They are not total database CPU over only Fork.
RSS is sampled process-tree peak, not private/PSS or physical memory.

| Job | SELF CPU control p50 | SELF CPU production p50 | Paired CPU delta p50 | Peak RSS control / production p50 (MiB) | Paired peak RSS delta p50 (MiB) |
|---|---:|---:|---:|---:|---:|
| 1 | 186.00 | 188.70 | +2.89 | 422.3 / 419.6 | +0.5 |
| 2 | 186.93 | 188.41 | +1.94 | 420.7 / 417.2 | -3.1 |
| 3 | 184.28 | 187.52 | +3.04 | 423.9 / 421.5 | +0.0 |
| 4 | 185.55 | 186.35 | +0.23 | 424.1 / 419.3 | -3.6 |
| 5 | 186.04 | 188.29 | +3.02 | 422.0 / 421.4 | +1.6 |

**Measured fact:** paired host CPU grows by 0.23–3.04 ms median (roughly
0.1–1.7% of the ~185–187 ms control). Parallel verification reduces elapsed time;
it does not reduce total hashing work. Sampled runtime descendant CPU reports
zero for every trial in this short interval: this is unavailable at the sampler's
resolution, **not proof that the guest consumed no CPU**. Combined precise
host+runtime CPU cannot be established from these counters.

Peak RSS medians remain approximately 417–424 MiB. Paired median changes range
−3.6 to +1.6 MiB; individual paired differences reach roughly ±20–29 MiB.
There is no consistent material sampled peak-RSS increase. Incremental ready
RSS paired medians decrease 6.6–12.7 MiB, but this is **not** evidence of a memory
optimization: earlier readiness changes the sampling alignment, and the nearest
ready observation may precede full startup. Unique physical memory was not
remeasured. The data supports no material observed RSS regression, with those
limits, rather than a precise physical-memory claim.

### macOS and Ubuntu product acceptance

Both platform jobs passed:

- Exact packaged native/public-ref Go consumer and installed-wheel Python paths.
- SQL, Snapshot/Fork, multi-client/session isolation/capacity and cleanup coverage.
- Interrupted-query invalidation and cleanup checks.
- Prepared-key valid/missing/corrupt cases and active plugin/public-key checks.
- Production Go integration under race detection and Python lifecycle regression.

The preceding local unit/race checks additionally cover snapshot corruption,
manifest/native mutation rejection, all-item visitation and deterministic error
selection. The CI integration success is not a claim that every conceivable
corruption or authentication configuration was retested on both platforms.

The separate lifecycle benchmark uses 20 samples/group with guest/init diagnostics
ON. It is a production smoke/resource context, **not** the diagnostics-OFF,
30-independent-trial local acceptance and not a paired macOS before/after study.

| Platform | ×1 per-DB p50 / p95 ms | ×4 group-ready p50 / p95 ms | ×8 group-ready p50 / p95 ms |
|---|---:|---:|---:|
| macOS 15.7.9 arm64 | 474.3 / 543.0 | 865.1 / 984.8 | 1697.8 / 2013.6 |
| Ubuntu 24.04 x86_64 | 526.8 / 576.9 | 818.4 / 849.5 | 1455.8 / 1504.5 |

There was no macOS correctness failure. **A quantitative macOS latency/physical
memory non-regression conclusion remains unproven:** this run has no same-run
serial macOS control, and historical runs have substantial hardware/noise and
instrumentation differences. In particular, the macOS p95 above 500 ms here must
not be hidden or compared as equivalent to an earlier diagnostics-OFF p95.

As context, total validator begin→end p50/p95 in this diagnostic run is:

| Platform | Native verification ms | Snapshot verification ms | Restore ms | MariaDB init ms |
|---|---:|---:|---:|---:|
| macOS | 63.4 / 69.1 | 82.4 / 107.6 | 168.1 / 184.5 | 92.5 / 110.4 |
| Ubuntu | 57.4 / 57.8 | 100.8 / 101.3 | 220.3 / 228.8 | 89.7 / 102.9 |

Validator wall spans are computed directly from begin/end, not by summing
interleaved file events. Native logical read counters include manifest/sidecar
reads (81,101,005 bytes macOS; 89,792,373 Ubuntu); snapshot counters include its
manifest (144,887,991 / 144,887,987 bytes). Physical I/O is not inferred. These are
unpaired post-change phases; they do not causally allocate the paired savings.

### Final status and next boundary

- Hosted correctness/packaged regression: PASS on both supported platforms.
- Hosted Ubuntu end-to-end benefit: consistently positive in five jobs.
- Host CPU: small measured increase, not a CPU-saving claim.
- Sampled memory: no consistent material peak-RSS increase; physical attribution
  and precise short-interval guest CPU remain limited.
- Fixed-local 30-trial diagnostics-OFF p95 <500 ms: **PASS on the M1 reference**,
  417.7 ms p95; see [full identity/distribution](final-v02-local-reference.md).

The implementation pass stops here. Use the fixed-reference procedure above,
record machine/source/AOT identity and every trial, and evaluate p95 unchanged.
If the local result fails, report it; do not begin another optimization or
architecture change as part of this tranche.
