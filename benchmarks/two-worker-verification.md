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
implementation's measured end-to-end result. New results are pending. Unit/race
checks cover complete item visitation, two-worker limit, ordered failures and
existing corruption/mutation checks. Packaged macOS/Ubuntu lifecycle acceptance
and paired measurements are delegated to the existing CI path.

## Hosted CI interpretation

`guest-build-boundary.yml` with `fresh_runner_latency=true` measures five fresh
Ubuntu jobs. Each builds the unchanged serial control at `2e631cd` and the new
production runner, then uses the **same verified frozen AOT archive** for both.
`final_latency.py --production-only --comparison-runner ... --runs 30` alternates
control/production order per round, retaining 30 independent children per side
plus two labelled warmups. Binary hashes and child Go build revisions distinguish
sources; outer environment identifies the supervising candidate checkout.

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

The fixed-local acceptance has **not yet been run**. If it fails, report NOT MET
separately and stop; no additional architecture/performance work belongs here.
