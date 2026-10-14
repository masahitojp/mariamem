# Temporary Snapshot direct-copy spike

2026-10-14. Decision state: **continue candidate; not approved for integration**.
The approved low-cost feasibility comparison is complete on macOS arm64.

## Human Review

The decision now is whether to spend one bounded follow-up on the large-fixture
reuse result before commissioning production implementation. **I recommend that
follow-up, retaining direct copy as the candidate.** In the ordinary measurements,
Snapshot took about half the time and preparation plus repeated Fork/SQL/cleanup
also became shorter. The saving happens once per prepared baseline; it does not
multiply with the number of tests.

The strongest objection is a separate resource-observed 100 MiB / 16 Fork run:
Snapshot became faster but the complete suite became **4.5% slower**. The extra
time was in the children, alongside more GC cycles. This does not establish a
repeatable regression or its cause, but prevents recommending immediate adoption
on the strength of the Snapshot result alone. The bounded follow-up below can
decide whether the whole-suite benefit survives; an inconclusive result means
retain the current implementation, not expand this investigation indefinitely.

No main integration or release preparation is authorized by this report.

## Question, scope and outcome

Question: can final temporary Snapshot files be written directly, preserving
corruption detection and independent Forks, and does that improve a test suite
that prepares once and reuses the result?

The approved design is preserved in the [previous review at 30dc34c](https://github.com/masahitojp/mariamem/blob/30dc34cac371f3a246d34370f6f8462e5d80a499/docs/reviews/snapshot-latency-residual.md).
This spike implements only its temporary **Go** Snapshot route. The existing
guest snapshot-copy, cold shutdown/source consumption, retained read-only file
descriptors and MAP_PRIVATE child storage remain. Persistent export, LoadSnapshot
and Python's cross-process route retain their original implementation. Python
was regression-checked; no Python speedup is claimed. A pgmem-style heap clone
would require a different storage/ownership design and is not evaluated here.

| Approved question | Result |
| --- | --- |
| Can materialization and source hashing share one pass? | YES in the isolated prototype. Final retained-file verification remains a separate pass. |
| Can existing ownership/integrity rules remain? | Targeted failure tests and real guest lifecycle/isolation tests PASS; no guarantee is removed. |
| Does preparation plus multiple Forks benefit? | All seven ordinary cell medians improve, by 1.6–25.2%; an additional resource run reverses that result. Universal improvement is NOT established. |
| Is the prototype ready for main? | NO. Resource reversal and production handoff/platform work remain. |

## Measured whole-suite effect

macOS 27.0.1 arm64, Go 1.26.8, GOMAXPROCS=2. Existing
`benchmarks/ownedprepared` harness, unchanged. One deterministic logical fixture,
one table, 1 KiB payload per row; payload 0 uses one row. Actual database files
include system data and metadata, so payload MiB is not Snapshot file size.
Separately created databases are not claimed byte-identical.

Each cell runs original/direct/direct/original: **two samples per mode**. No
sample was excluded. Timing runs have neither trace nor heap sampling enabled.
The complete suite includes Fresh startup, fixture SQL, Snapshot, every child
Fork, read/count/commit/rollback checks, child Close and Snapshot Close. It excludes
diagnostic probes and forced diagnostic GC. With four workers, the child phase is
elapsed wall time, not the sum of overlapping operations.

| Payload | Forks | Workers | Snapshot original → direct | Whole suite original → direct | Shorter by |
| --- | ---: | ---: | ---: | ---: | ---: |
| 0 MiB | 4 | 1 | 403.4 → 211.9 ms | 0.791 → 0.591 s | 25.2% |
| 0 MiB | 16 | 1 | 514.2 → 224.2 ms | 2.071 → 1.718 s | 17.0% |
| 10 MiB | 4 | 1 | 475.5 → 265.3 ms | 1.979 → 1.754 s | 11.4% |
| 10 MiB | 16 | 1 | 504.9 → 249.5 ms | 4.365 → 4.088 s | 6.3% |
| 100 MiB | 4 | 1 | 846.2 → 426.6 ms | 12.192 → 11.762 s | 3.5% |
| 100 MiB | 16 | 1 | 840.3 → 429.9 ms | 26.315 → 25.887 s | 1.6% |
| 10 MiB | 16 | 4 | 450.2 → 257.4 ms | 3.316 → 3.175 s | 4.2% |

These are medians of two, not confidence intervals or stable percentile estimates.
For example, whole-suite ranges are 1.825–2.316 / 1.591–1.845 s for 0 MiB / 16,
and 3.286–3.345 / 3.058–3.293 s for four workers: both overlap. All ranges and
phase medians are in [summary.json](snapshot-direct-copy-evidence/summary.json).

The primary Snapshot saving is about 0.19–0.42 s, once per preparation. For
100 MiB / 16 serial children, preparation alone is about 7 s and the child phase
about 18.4 s. This design does not remove those costs. Child-phase medians remain
similar; four workers are 2.114 → 2.162 s. This is not evidence that Fork itself
became faster. No Fresh-per-test comparison or arbitrary application workload
speedup is inferred from this prepared-suite measurement.

### Separate resource and trace runs, including contrary evidence

Resource sampling is separate from the 28 primary timing runs. There is one
original/direct pair per resource cell, in that order, with 25 ms heap sampling.
Peak RSS is process high-water RSS; cumulative allocation is Go TotalAlloc delta,
not retained memory. Values are MiB.

| Scenario | Suite original → direct | Cumulative allocation | Peak RSS | GC cycles |
| --- | ---: | ---: | ---: | ---: |
| 100 MiB / 16 / serial | **26.094 → 27.272 s** | 2336.5 → 2069.6 | 1128.4 → 1082.5 | 10 → 25 |
| 10 MiB / 16 / four workers | 4.136 → 3.415 s | 814.0 → 655.3 | 950.7 → 651.4 | 10 → 6 |

In the slower 100 MiB pair, Snapshot is 0.870 → 0.378 s, preparation about
6.93 → 6.92 s, and children **18.288 → 19.971 s**. The child increase exceeds
the Snapshot saving. More GC is an observation, not an established explanation;
sampling, scheduling, GC pacing and run variation have not been separated.
Neither the RSS reduction nor the reverse timing result is a repeatability claim.
Raw [original](snapshot-direct-copy-evidence/resources-p100-n16-w1-0-original.json)
and [direct](snapshot-direct-copy-evidence/resources-p100-n16-w1-1-direct.json)
records retain operation timings and probes.

All four resource runs finish with zero active linear mappings/reserved/RW bytes
and zero release failures. Benchmark FD counts are **5 → 6 in both modes**;
these runs do not establish return to the process's initial FD count. The separate
warmed repeated-lifecycle integration test returns FD 4 → 4 and goroutines 2 → 2.
The common one-FD benchmark difference is not attributed to a particular subsystem.

Two separate 100 MiB / 4 trace runs show public Snapshot **750.0 → 388.6 ms**.
The original has export 110.0 ms and publish 428.1 ms, plus the other existing
phases. Direct materialization plus source hash takes **205.6 ms**, and final
owned acquisition/verification **138.8 ms**; the remaining public interval is
about 44.2 ms. These are a different observed pair, not components to add to
the primary medians or the earlier 751.7 ms characterization. Read/hash CPU is
still combined; this experiment does not claim to separate it.

There are **34 successful runs and 376 child lifecycles**: 28 ordinary timings,
four resource runs and two trace runs. Every child executes the harness's SQL
assertions, including mutation and rollback. See
[campaign.json](snapshot-direct-copy-evidence/campaign.json) and the complete raw
per-run JSON files beside it. The disk guard scans at 5 s intervals in all modes;
its small common observer cost is not calibrated out.

## Ownership path and failure handling

1. The existing Snapshot preconditions and private destination creation run
   before source acceptance. An experiment-only marker conveys the destination
   to the handwritten runtime adapter. Failure before acceptance preserves the DB.
2. The unchanged guest performs snapshot-copy and exits; runtime worker join
   completes. Its stable `snapshot-out/data` MemFS becomes the source.
3. `MaterializeDirect` walks the exact inventory, writes final private files
   with exclusive creation, and hashes bytes during this same read/write pass.
   It rejects nonregular files and length changes/short copies. One 128 KiB
   buffer replaces whole-file transfer buffers on this path. A manifest records
   expected content; it alone does not confer trusted ownership.
4. The **unchanged `AdoptCreated`** opens read-only descriptors, removes path
   aliases and verifies the exact retained files against that manifest, including
   guest identity, inventory, sizes, hashes and zero link count. Only then can the
   public call return success. Subsequent Forks use the existing private mappings.

This removes intermediate host-file materialization/copy and one redundant
verification pass. It does not remove the final byte reread. The source digest
comes from the materialization stream; it is not recomputed from the destination
and then trusted without comparing the retained files.

Materialization failure removes partial output; adoption failure closes acquired
descriptors, and the public temporary-Snapshot owner handles directory cleanup.
After acceptance, failure consumes the source as before. No successful Snapshot
is returned on a failed final check. A nonempty destination is rejected without
deleting its preexisting content. The private marker and environment switch are
prototype coordination, not an adopted public API or storage format change.
External/persisted input continues through its existing copy/verification path.

## Verification and exact inputs

| Check | Result and evidence |
| --- | --- |
| Source identity before measurement | PASS: clean standalone clone, commit object resolved with `scripts/git_identity.py`; binary VCS identity checked before timing. |
| Guest, generated code, provenance, converter inputs and benchmark harness unchanged | PASS: identical Git objects to main; [unchanged-inputs.json](snapshot-direct-copy-evidence/unchanged-inputs.json). No guest regeneration needed. |
| Generated source verification | PASS; [generated-source.txt](snapshot-direct-copy-evidence/generated-source.txt). No guard/allowlist weakening. |
| Snapshot unit/failure tests with race detector | PASS; [snapshot-race.txt](snapshot-direct-copy-evidence/snapshot-race.txt). Checks content/size/inventory/alias/guest/manifest damage, short copy, read/write failure, partial cleanup and read-only ownership. Race-detector success is not a global mmap guarantee. |
| Host and handwritten runtime unit tests | PASS; [host-runtime-unit.txt](snapshot-direct-copy-evidence/host-runtime-unit.txt). |
| Full Go integration, direct and original routes | PASS both; [direct](snapshot-direct-copy-evidence/integration-direct.txt), [original](snapshot-direct-copy-evidence/integration-control.txt). Transactions, rejection preserving source, child-derived baselines, 35 mutating children, concurrent reuse, parent Close/live child, LoadSnapshot and repeated cleanup. |
| Standalone-clone integration subset | PASS; [clone-integration-direct.txt](snapshot-direct-copy-evidence/clone-integration-direct.txt). Confirms the correctly stamped build source. |
| Python original route | PASS: selected three owned creation/import/modified-child cases with correctly stamped host, Python 3.14.8; [receipt](snapshot-direct-copy-evidence/python-check.json). The prior full 18-case pass used a worktree-stamped host and is supplementary only. |
| Canonical `verify.py check` | **FAIL**: preexisting tracked `.log` publication-boundary violation on unchanged main. Source checks, Go tests/vet pass; Python reports 587 passed, 37 skipped, 18 subtests passed and one failed source-boundary test. [Full log](snapshot-direct-copy-evidence/canonical-check.txt), [independent clean-main reproduction](snapshot-direct-copy-evidence/preexisting-public-boundary.json). Not waived or represented as green. |
| Ubuntu x86_64 / release acceptance / broader ORM suite | SKIP: local low-cost spike; no CI or release qualification submitted. |

The preexisting failing file is
`docs/reviews/v050-startup-tail-source-fix-evidence/ubuntu/measurement.log`.
It and the publication guard are unchanged. It does not invalidate execution of
the measured SQL scenarios, but a clean full-check/adoption claim requires its
separate resolution.

Baseline `source_commit`: `2550bbe1ccf58f9cf65cf4cd801224907a7f9469` (clean main).
Measured `source_commit`: **`3341f99000246fc64ae17b4ea39118f55589de1e`**.
Prototype commits: `49f66b6` (route/tests), `5531d04` (handwritten owner and optional
backend dispatch), `3341f99` (direct trace events and conditional expectations).
The final report commit adds documentation/evidence only; it is not the measured
source. No release tag is used as source identity.

Guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`.
Benchmark SHA256: `fbf2582d7acc0aed2037a2ee25072b4e343e9e3623ebf24e1520cc92955646cf`.
Full toolchain, binary buildinfo and harness/provenance hashes are in
[measurement-inputs.json](snapshot-direct-copy-evidence/measurement-inputs.json).

Control and direct use the **same prototype binary**, switched with
`MARIAMEM_SNAPSHOT_DIRECT=0/1`; control takes the original path, including one new
negative marker lookup in the adapter. It is not an independently compiled
untouched release binary. This isolates path choice cheaply but limits attribution
against released builds.

Initial attempts are retained, not silently counted as passes: a missing optional
backend method failed compilation; placing the handwritten helper in a new
generated-directory file failed the inventory guard; old trace expectations
failed when direct copy correctly omitted publish/export. These were fixed in
the three commits above without relaxing ownership or source guards. Linked
worktree builds also embedded main's VCS identity even with `-buildvcs=true`.
That mismatch was caught **before measurement**; binaries were rebuilt from the
clean standalone clone and verified. No mistagged binary contributes timings.

## Reproduction and bounded next step

The [evidence README](snapshot-direct-copy-evidence/README.md) gives the replay
layout, commands and archive hashes. The benchmark/harness is unchanged, scripts
are preserved, and the exact tested commit remains reachable on
`experiment/snapshot-direct-copy`. Reproduction should build that commit, not the
later documentation commit. Local caches, binaries and disposable clone/worktree
are removed after evidence commit/push under the experiment-workspace policy.

**Recommended follow-up, not run in this spike:** only 100 MiB / 16 serial Forks,
eight whole-suite runs: original/direct/direct/original without resource sampling,
then the same four with it. Keep fixture and GOMAXPROCS fixed, retain every sample,
compare Snapshot, child window, complete wall/CPU and GC/allocation observations.
Approximately four minutes of workload execution plus review; budget **30 minutes
after binaries are available**. Rebuilding removed caches is additional setup,
not concealed in that estimate. Do not add profiling or new workload cells unless
the Human separately agrees.

Exit judgment: if the direct child-time penalty repeats and erases preparation
savings, recommend deferring adoption and offer a separate bounded GC/lifetime
investigation. If both ordinary and resource-observed pairs show suite benefit
without a repeatable child penalty, recommend production implementation followed
by the normal boundary verification. If mixed/inconclusive at this fixed limit,
retain the current implementation; uncertainty is not permission for an endless
campaign. Small counts remain a feasibility judgment, not a tail guarantee.

Production work, if later selected, includes replacing the prototype marker/env
coordination with an explicit internal handoff, deciding the Python cross-process
owned route, retaining these failure oracles, checking native Ubuntu behavior,
and resolving the separate existing publication-boundary failure. Those tasks
and their implementation cost are not part of this completed cheap spike.
