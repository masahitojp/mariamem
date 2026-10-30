# v0.5.3 → v0.6.0: bounded local latency comparison

**Small workloads became slightly slower; the measured 10 MiB Go suites did
not show a comparable whole-suite regression.** Recommend retaining this release
baseline and treating small Fresh startup as the next bounded performance
question, rather than starting a broad runtime optimization. The strongest
limitation is one local machine and six pairs: the consistent Light Fresh and
medium Python increases are observations, not universal regression rates or
attribution to a particular feature.

## Fixed inputs and scope

| Release | source_commit | tag_object_sha |
| --- | --- | --- |
| v0.5.3 | `4f7b18bfc00965974fcbb16ac49cbf00d9fb2b0e` | `70bdb3d87e9358cb45e54a875d95e7971ca9ac85` |
| v0.6.0 | `b3b3b46a8807482ad3f96725af86e031fe369b01` | `b57183b08d48884840111e8b53daa500734337f0` |

`git_identity.py` inspected the annotated tags and verified typed release pins
before compilation. Clean independent checkouts were built with the same
Go1.26.10, CGO_ENABLED=0, `-p 1 -trimpath -buildvcs=true`; actual embedded
revision/modified=false and binary hashes were checked. These are same-toolchain
source comparisons, not timings of the originally published wheel binaries.
Both releases use MariaDB12.3.3. Exact guest/harness/binary identities, machine
and Python versions are in [inputs.json](v060-latency-evidence/inputs.json).

Existing Go OwnedPrepared and Python sharedhost workloads are byte-identical
across the two release sources. Go uses four instances per suite: Light,
10 MiB/eight tables serial, and 10 MiB/eight tables/four workers, each Fresh and
Fork. Python uses the existing two-table users/orders schema, 100×256-byte or
10,000×1-KiB users payload, and two independent children with commit/rollback.
These are different language workloads, not a Go-versus-Python speed ranking.

Go has one separate warmup pair and six measured pairs per cell. Python has six
ordinary pairs per scale and one additional resource-observed pair per scale;
the latter is excluded from latency summaries. Execution order alternates.
Build/acquisition time is excluded. Python's ordinary first-use samples are
retained, not silently labelled warmup or removed. Normal OS activity remains.

The fixed [plan](v060-latency-evidence/plan.json) caps active work at two hours,
measurement tooling at30minutes, workspace16GiB, free reserve16GiB and each
guarded execution at30minutes; heavy CI submissions are zero. No100MiB,
Ubuntu/cross-platform, cold-installation, helper/E2E/dump-specific performance or
resource-model campaign is included. There is no matched old-version equivalent
for newly introduced features.

## Whole-suite latency

Milliseconds, median of six ordinary samples per version. Positive change is
slower. Go reports existing `suite_product_seconds` (parallel intervals are not
summed); Python reports full prepare→children→Close wall time. Resource sampling
does not run in these ordinary cells.

| Workload | Mode | v0.5.3 ms | v0.6.0 ms | Change | Slower pairs |
| --- | --- | ---: | ---: | ---: | ---: |
| Go Light / four instances | Fresh | 213.5 | 226.7 | +6.2% | 6/6 |
| Go Light / four children | Fork | 252.9 | 255.5 | +1.0% | 3/6 |
| Go 10 MiB serial | Fresh | 2688.4 | 2684.1 | −0.2% | 2/6 |
| Go 10 MiB serial | Fork | 1147.5 | 1149.0 | +0.1% | 3/6 |
| Go 10 MiB / four workers | Fresh | 895.2 | 894.7 | −0.1% | 1/6 |
| Go 10 MiB / four workers | Fork | 806.2 | 806.6 | +0.04% | 2/6 |
| Python small / two children | Prepared | 221.8 | 233.0 | +5.0% | 4/6 |
| Python medium / two children | Prepared | 3083.6 | 3136.1 | +1.7% | 6/6 |

Raw distributions, min/max and phase medians are in
[summary.json](v060-latency-evidence/summary.json) and
[summary.csv](v060-latency-evidence/summary.csv). No few-sample p95 or performance
PASS threshold is inferred.

## Where the observed difference lies

- Go Light Fresh increases about13.2ms per four-instance suite. The summed four
  Start intervals have median135.1→143.2ms, about2ms per DB. Setup increases
  28.4→31.8ms and Close33.9→35.2ms; point-use time is4.10→4.04ms. Phase medians
  are independent statistics and must not be added into an exact decomposition.
  This gives a specific startup/setup question, not proof of its root cause.
- Go Light Snapshot remains about2.48→2.41ms. The serial10MiB Fresh Start sums
  also increase132.2→141.0ms, while lower preparation time offsets that in the
  whole-suite median. Thus a flat suite does not prove every operation is flat.
- Python medium increases about52.5ms; migrate/seed medians are2900.6→2951.0ms.
  Snapshot is2.53→4.66ms, an approximately2.1ms absolute difference. Child-start
  medians pooled over both children are36.35→35.96ms. The measured increase is
  mainly associated with preparation, not a large child-start penalty.
- Both versions' first small Python sample has an approximately1s preparation
  Start: whole-suite1240.2/1193.4ms versus subsequent roughly215–237ms. The cause
  and tail frequency are unknown. These observations remain in the main table;
  excluding the first pair as a sensitivity check gives220.8→230.5ms (+4.4%).
  This is not a new v0.6.0-only tail or cold-machine evidence.

The separate single resource pair observed host RSS about120/119MiB (small)
and165/166MiB (medium). These sparse sampled peaks establish neither a memory
regression nor its absence and are not latency observations.

## Correctness, preparation failures and cleanup

The completed campaign has84 Go executions (12warmup,72ordinary) and28 Python
executions (24ordinary,4resource). Existing exact-value, COUNT, transaction,
independent-child and Close oracles passed. Python also checked reaped host PIDs
and empty owned scratch. This is bounded workload correctness, not release
qualification or a general leak guarantee.

Two preparation mistakes are preserved separately and excluded from results:

1. The first linked-worktree build lacked an embedded VCS revision and was
   rejected before measurement. Switching to independent `.git` checkouts
   resolved it; a caller-supplied SHA was never substituted for binary identity.
2. The wrapper initially added an unsupported exact FD equality requirement.
   A successful candidate warmup reported5→6 and was rejected by that wrapper.
   The original harness treats FD delta as an observation, so the added condition
   was removed. All completed measured Go runs in both releases report the same
   +1 process FD delta. Its ownership was not attributed and this is not proof
   of no FD leak. Original SQL/Close assertions were not modified.

Only compact raw JSON, reproduction/analysis scripts, identity pins and checksums
are retained. Build/compiler/module caches, binaries and cloned source are
disposable; storage cleanup is recorded separately. Reproduction: prepare the
documented workspace layout, place `run.py` in its `evidence/`, execute it through
the existing disk guard, then run `analyze.py`. This rebuilds both pinned releases;
the archived attempt failures are not instructions to reproduce those mistakes.

Further profiling or a performance repair is not part of this result. If pursued,
start with the roughly2ms/DB Go Fresh difference using these same fixed inputs;
do not reopen the deferred100MiB/resource campaign without a new scope decision.
