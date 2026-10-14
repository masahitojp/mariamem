# Direct-copy whole-suite reversal: bounded follow-up

2026-10-14. **Requested eight-run follow-up COMPLETE. Recommendation: retain
the current implementation; defer adoption of this prototype.**

## Human Review

The decision now is whether this candidate has enough whole-suite benefit to
commission production implementation. **I recommend retaining the current path
for now.** Snapshot is consistently shorter, but preparation plus 16 reused
children is 2.2% slower in the ordinary measurements and 2.9% faster with resource
observation. That mixed result does not establish stable whole-suite benefit.
The extra GC during child use also recurs, so the previous adverse run cannot be
dismissed as simply a memory-observer artifact.

The strongest argument for continuing is concrete: Snapshot still saves about
0.43 seconds, cumulative allocation falls about 264 MiB, and both resource-observed
pairs finish sooner. Those results support the copy-reduction idea, but do not
resolve its value in the large prepared suite. The agreed mixed/inconclusive
exit condition is therefore met: retain the existing implementation, complete
this investigation at eight runs, and do not extend measurements automatically.
This is deferral of the present prototype, not a finding that direct copying
cannot be useful for smaller suites or a rejection of the original ownership design.

The [original spike](snapshot-direct-copy-spike.md) remains the ownership/failure
test reference. This follow-up changes no runtime, guest, converter, API or
measurement harness. Main integration and release preparation are not performed.

## What was checked

User authorization: confirm only the previously adverse **100 MiB / 16 serial
Forks** condition. The agreed schedule is original/direct/direct/original without
resource sampling, then the same four with sampling: two trials per mode in
each group, **eight successful runs / 128 child lifecycles**, no exclusions.
No additional workloads, profiling, fixes or platform expansion were introduced.

Same clean source commit `3341f99000246fc64ae17b4ea39118f55589de1e`, MariaDB 12.3.3
guest, unchanged `benchmarks/ownedprepared`, one table and CRUD workload as the
previous spike. Native macOS 27.0.1 arm64, Go 1.26.8, GOMAXPROCS=2. GOGC,
GOMEMLIMIT, GODEBUG and GOFLAGS were unset in the parent environment. Both paths
use one exact prototype binary, switched by `MARIAMEM_SNAPSHOT_DIRECT=0/1`.
Resource observation retains the existing 25 ms sampler and phase probes; ordinary
trials have neither resource sampling nor trace enabled.

The entire suite includes Fresh start, fixture SQL, Snapshot, all child Forks,
reads/counts, mutations/commit/rollback assertions, child Close and Snapshot Close.
It excludes diagnostic probes/final diagnostic GC, using the existing
`suite_product_seconds` boundary. CPU is the harness's suite CPU boundary; it is
recorded separately and is not numerically interchangeable with product wall time.

## Results

Medians of two, seconds. Differences are direct minus original; positive means
longer. The entire observed min/max range is retained below and in
[summary.json](snapshot-direct-copy-recheck-evidence/summary.json).

| Observation | Phase | Original | Direct | Difference |
| --- | --- | ---: | ---: | ---: |
| Ordinary | Prepare DB/fixture | 6.561 | 6.874 | +0.313 |
| Ordinary | Snapshot | 0.880 | 0.453 | **−0.427** |
| Ordinary | All children | 17.682 | 18.337 | +0.655 |
| Ordinary | **Whole suite** | **25.128** | **25.671** | **+0.543 / +2.2%** |
| Ordinary | Suite CPU | 32.914 | 33.469 | +0.555 |
| Resource-observed | Prepare DB/fixture | 6.887 | 6.811 | −0.076 |
| Resource-observed | Snapshot | 0.853 | 0.428 | **−0.425** |
| Resource-observed | All children | 18.459 | 18.214 | −0.244 |
| Resource-observed | **Whole suite** | **26.204** | **25.457** | **−0.747 / −2.9%** |
| Resource-observed | Suite CPU | 34.266 | 33.489 | −0.777 |

Both ordinary ranges overlap: original 24.245–26.011 s, direct 25.322–26.020 s.
Resource-observed ranges are original 25.760–26.648 s, direct 25.365–25.548 s.
These small samples do not establish significance, repeatability of a percentage,
or a tail distribution. Phase medians need not add exactly to the whole median;
Snapshot Close is included in whole-suite cost.

| Group/order | Prepare | Snapshot | Children | Whole suite | CPU |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary 0 original | 6.275 | 0.889 | 17.076 | 24.245 | 31.687 |
| Ordinary 1 direct | 6.501 | 0.397 | 18.416 | 25.322 | 33.158 |
| Ordinary 2 direct | 7.246 | 0.509 | 18.259 | 26.020 | 33.780 |
| Ordinary 3 original | 6.847 | 0.871 | 18.289 | 26.011 | 34.142 |
| Resource 0 original | 6.728 | 0.822 | 18.204 | 25.760 | 33.892 |
| Resource 1 direct | 6.552 | 0.400 | 18.411 | 25.365 | 33.499 |
| Resource 2 direct | 7.070 | 0.455 | 18.018 | 25.548 | 33.479 |
| Resource 3 original | 7.046 | 0.883 | 18.713 | 26.648 | 34.639 |

In the first ordinary pair the saving is erased: children are 1.340 s longer,
fixture preparation is 0.226 s longer, and the whole suite is 1.077 s longer.
The reversed ordinary pair is effectively equal (+0.009 s). Resource pairs both
favor direct, by 0.395 s and 1.100 s. Thus **an unfavorable whole-suite comparison
also occurs without memory sampling**, but a consistent causal regression is not
established. The particularly fast first original run and the variation in fixture
preparation are retained; neither is silently removed or attributed to a cause.

## GC/allocation observation and interpretation

| Resource metric | Original range | Direct range |
| --- | ---: | ---: |
| Cumulative Go allocation | 2335.6–2335.8 MiB | 2071.4–2073.0 MiB |
| Process peak RSS | 1077.2–1177.0 MiB | 1044.7–1075.9 MiB |
| Total observed GC cycles | 10, 10 | 27, 25 |
| GC between Snapshot phase probe and children-closed probe | **0, 0** | **18, 16** |

The phase probes make the GC shift more specific than the earlier total alone:
original is at cycle 9 after Snapshot and still 9 after children; direct is at
cycle 8 after Snapshot and 26/24 after children. All runs include one later
diagnostic GC in the observed totals, outside product wall time. Extra cycles
therefore occur during ordinary child use, not just in final diagnostic cleanup.

Observed heap allocation after Snapshot is about 698 MiB original versus 544 MiB
direct; after all children, before diagnostic GC, about 1094 MiB original versus
14 MiB direct. These are Go heap allocation counters, including uncollected
objects, not proof of a live-memory leak, retained storage or complete mmap usage.

**Confirmed:** fewer allocated bytes, shorter Snapshot, and a different GC
distribution in the resource-observed runs. **Inference:** reduced preparation
allocation may alter GC pacing during reuse. **Unresolved:** its causal contribution
to wall/CPU cost versus fixture/run/scheduling variation. GC count is not GC cost;
the faster resource-observed direct trials also have more GC. No allocation-lifetime
profile, forced-GC variant or runtime redesign was performed to settle that cause.
The earlier 4.5% adverse resource result remains valid historical evidence;
it was not reproduced in these resource pairs, and is not dismissed or pooled
with ordinary samples to manufacture a favorable result.

All SQL assertions PASS. Resource trials finish with zero active linear mappings,
zero reserved/RW mapping bytes and zero release failures. FD counts remain
5 → 6 in both modes, as in the original benchmark. They establish no new
mode-specific leak and do not establish exact return to initial FD count; the
earlier warmed lifecycle tests own that separate claim. mmap and sampled heap
counters are not global correctness or safety proofs.

## Inputs, evidence and checks

Measured `source_commit`: `3341f99000246fc64ae17b4ea39118f55589de1e`.
Prototype's baseline `source_commit`: `2550bbe1ccf58f9cf65cf4cd801224907a7f9469`.
Documentation starts at `3f358fb95e5b010bf0ed5b9db51e9b0e0b8661a0` on
`experiment/snapshot-direct-copy`; the follow-up report commit is not measured.
Before build, `scripts/git_identity.py` resolves the source as a commit and the
runner asserts exact clean HEAD. Before timing, `verify_go_binary` checks its VCS
revision and unmodified status. Standalone clone avoids the earlier worktree
stamp mismatch. [inputs.json](snapshot-direct-copy-recheck-evidence/inputs.json)
records buildinfo, script/harness/provenance/guest hashes and environment.

Binary SHA256: `084e1ba11edcb36188284ee64a8b70b133ee0d0bf42978d639d24a50f0c14660`.
Guest SHA256: `7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`.
The binary hash differs from the prior build in another source directory;
same source identity is verified, binary byte identity is not claimed.

| Check | Judgment |
| --- | --- |
| Exact-source build and binary stamp | PASS |
| Eight successful 100 MiB / 16 Fork scenarios, SQL assertions | PASS; [campaign](snapshot-direct-copy-recheck-evidence/campaign.json), all per-run JSON alongside it |
| Whole-suite adverse case exclusively caused by memory observer | NOT SUPPORTED: unfavorable ordinary comparison also observed |
| Stable whole-suite improvement/regression attributable to direct route | INCONCLUSIVE at the agreed fixed sample limit |
| Extra child-phase GC in observed mode | CONFIRMED; direct 16/18 cycles, original 0 |
| GC increase proves slowdown | NOT ESTABLISHED: observed direct pairs were faster |
| Ownership/failure tests and canonical checks | Not rerun: exact unchanged runtime; prior spike owns results, including its preexisting publication-boundary FAIL. No full-check PASS claimed. |
| Ubuntu / release qualification / Python speed comparison | SKIP: outside this authorized local follow-up |

The first attempted scenario was blocked by sandbox localhost bind permission,
before fixture creation. Its failure is archived under `sandbox-attempt/`, never
treated as a performance sample. The successful eight-run campaign used approved
localhost access. The initial build's stat-cache permission warning is retained;
build completed and subsequent cached build/binary identity checks passed.

The [evidence README](snapshot-direct-copy-recheck-evidence/README.md) records
reproduction and normalization. No generated Go edit/regeneration or guard
weakening occurs. Reports/evidence and runner are committed/pushed; disposable
clone, worktree, compiler cache and binary are removed after preservation.

## Stop and subsequent scope

The earlier review precommitted to retaining the existing implementation if these
eight runs were mixed/inconclusive. This report follows that condition. It does
not convert the sample limit into proof of speed or broad safety, and it does
not leave this follow-up open until some future favorable result appears.

If the Human later chooses to continue this performance candidate, the separate
question is **whether changed allocation lifetime/GC pacing explains a real child
cost that can be reduced without losing ownership and cleanup guarantees**.
That needs an explicit bounded design/investigation scope and estimate; no such
repair or larger measurement campaign is commissioned by the current result.
The production/Python/Ubuntu work already listed in the original review remains
pending rather than silently included here.
