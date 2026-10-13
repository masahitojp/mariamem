# v0.5.0 Product Verification — paired final configuration

**Approved scope COMPLETE.** All 80 measured cells and eight warm-up pilots
completed; unchanged SQL/commit/rollback/isolation oracles passed.
No functional failure or unbalanced linear-memory reclamation was observed.
I recommend accepting this candidate as the v0.5.0 basis and proceeding to
integration/release preparation. Human release approval remains separate.
The [Human Review](../docs/reviews/v050-human-review.md) owns that decision.

The main adverse observation is **Go four-parallel Fresh median 0.953→1.763 s**.
Python's corresponding median moved 1.835→1.030 s. Both versions show the
existing approximately one-second startup tail. Phase records explain where
the suite time went; three trials do not establish an increased or decreased
tail rate. The recommendation accepts the already documented startup-tail
behavior, not a promise that every workload is equally fast.

## Fixed inputs and finite scope

- Released v0.4.7: tag_object_sha
  `c201bf577440440253155e665def9c25ac5064f0`, source_commit
  `e0be06f3a20c72cbb5a9be27971280c80a3ec357`.
  [Typed release pin](../release/baselines/v0.4.7.json) and
  [verified identity](v050-product-evidence/verification/baseline-identity.json).
- Qualification-tested candidate source_commit
  `bb637c49e6d6b50ec6761dead172a35f0b051f7e`; its
  [both-native Qualification](../docs/reviews/v050-final-qualification.md)
  precedes this campaign. Guest/runtime inputs were not changed for measurement.
  Python SQL reports 13.1.0-MariaDB-embedded / 12.3.3-MariaDB-embedded respectively.
- Observer/runner source `f24bc942628eeabe391cfcbc6300bcb175157b17`.
  Both fixed clean runtime worktrees have identical Go main/resources and
  Python workload bytes. No observer copy or runtime patch was necessary.
  [Build receipt](v050-product-evidence/verification/build-pair.json) retains
  actual sources, tree/guest/provenance identities, binary hashes and flags.
  Benchmark binaries deliberately use `-buildvcs=false`; they are bound by
  checked source and hashes, not relabeled as release artifacts.
- Apple M1, 16 GiB, macOS27.0.1 arm64, Go1.26.8 with switching disabled,
  Python3.14.8, fixed existing Python dependency pins. Go builds use
  `CGO_ENABLED=1 -p 1 -trimpath -buildvcs=false`, as the previous campaign.
  One campaign at a time, no competing build/test; preparation/compilation excluded.

The approved existing Go/Python Fresh/Fork matrix has Light, 10 MiB/8-table
serial, 10 MiB/8-table four-parallel, and 100 MiB/8-table serial. Four tests per
suite; n=3 for normal cells, n=1 for the large supplement; alternating paired
order. Fresh charges preparation per DB. Fork charges preparation/Snapshot
once and creates independent children. Eight one-test pilots are retained
separately and excluded from all tables. Native container anchors were not
part of this approved comparison; no broader workload or engine-speed ranking
is introduced.

Each cell retains the existing two-connection/count/payload/commit/rollback
oracle, and errors stop the campaign. The disk budget was 24 GiB with 20 GiB
free reserve, 900-second cell timeout, five-second disk samples. Peak owned
usage was 2.201 GiB, minimum free space 76.455 GiB. No budget stopped a cell.
The 8 GiB completed-Go-cell RSS stop is a sampled safeguard, not a hard RAM quota.

## User-visible suite time

Seconds, baseline→candidate. n=3 medians are descriptive; n=1 is a single sample.
The complete ranges/interpolated p95 and individual results remain in
[cells](v050-product-evidence/cells.csv),
[summary](v050-product-evidence/summary.csv) and
[paired comparison](v050-product-evidence/comparison.csv).
No slow sample is removed.

| Case | Mode | n | Go wall (s) | Change | Python wall (s) | Change |
| --- | --- | --- | --- | --- | --- | --- |
| Light | Fresh | 3 | 0.383→0.399 | +4.2% | 0.374→0.481 | +28.4% |
| Light | Fork | 3 | 0.706→0.731 | +3.6% | 0.811→0.794 | −2.1% |
| 10 MiB serial | Fresh | 3 | 2.908→2.870 | −1.3% | 2.991→2.992 | +0.03% |
| 10 MiB serial | Fork | 3 | 1.675→1.681 | +0.4% | 1.806→1.803 | −0.2% |
| 10 MiB four-parallel | Fresh | 3 | 0.953→1.763 | +84.9% | 1.835→1.030 | −43.9% |
| 10 MiB four-parallel | Fork | 3 | 2.376→1.301 | −45.2% | 1.354→1.286 | −5.1% |
| 100 MiB serial | Fresh | 1 | 25.699→25.447 | −1.0% | 26.286→26.254 | −0.1% |
| 100 MiB serial | Fork | 1 | 10.231→9.994 | −2.3% | 10.218→10.226 | +0.07% |

### Strongest adverse result and phase evidence

Go parallel Fresh individual suite times were baseline
`[1.796, 0.936, 0.953]` and candidate `[1.763, 1.808, 0.961]`.
Their maximum ready times were baseline `[1.126, 0.133, 0.151]` and candidate
`[1.110, 1.118, 0.165]`. The slower observed suites coincide with ready tails;
Close remained around 7–14 ms. This locates the measured delay without proving
its cause or a population tail-rate change. The median +0.809 s is real for
these samples and must not be described as “no slowdown.”

Python parallel Fresh has the opposite suite-tail placement: baseline has two
ready-tail suites, candidate one. Go has baseline one, candidate two. This is
supporting evidence against treating either language's three-sample median as
a stable speedup/slowdown estimate, not proof of equivalent tail rates.
Go parallel Fork baseline's slow suites include 1.113/1.166 s prepare-start;
candidate's three prepare-start values were 0.050/0.117/0.050 s.
Python Light Fresh's +0.106 s median coincides with a slower first ready sample
in two candidate trials versus one baseline trial; later ready samples are
approximately 53–61 ms in both. Those adverse observations remain in the table.

[Selected exact phase observations](v050-product-evidence/verification/startup-observations.json)
and [all Go phases](v050-product-evidence/phases.csv) support this assessment.
The existing [startup-tail characterization](v047-product-validation.md) is
historical context, not replacement measurements for this candidate.

CPU also has adverse cells: Python parallel Fresh median 3.771→4.187 CPU s
(+11.0%), Python Light Fresh 0.424→0.459 (+8.1%), Go Light Fork
0.689→0.717 (+4.0%). Go parallel Fresh is 3.752→3.308 (−11.8%).
No causal attribution to J1 alone follows from a whole guest/runtime upgrade.
The recommendation accepts the measured costs; it does not guarantee zero
overhead or claim a general performance improvement.

## Resources and cleanup

Go Peak RSS median/single-sample changes range from −4.0% to +2.4%.
The highest observed process Peak RSS across both versions is 1,207.7 MiB.
For example, parallel Fresh is 822.5→789.6 MiB; large Fresh is
1,141.8→1,169.1 MiB; large Fork is 1,207.7→1,206.3 MiB.
Peak sampled Go heap in parallel Fresh is 994.3→1,012.2 MiB; it is a distinct
measure from RSS. Cumulative Go allocation is close in every case (e.g.
parallel Fresh 1,183.5→1,184.6 MiB); it is not retained RAM.

All 40 measured Go cells ended with zero active mappings/reserved/RW bytes,
zero release failures and exact expected creates/releases: 180/180 in total.
All final heap samples after the existing diagnostic GC were at most 568,616
bytes. FD +1 is the existing one-time network poll initialization; goroutine
+1 is the still-running observer, both identical across every Go cell.
[Invariant evidence](v050-product-evidence/verification/resource-invariants.json)
does not infer general leak freedom or forced cleanup from these bounded suites.

Physical footprint/RSS can retain process arenas/pages after Close/GC; they
need not become zero. Prepared mapping extent is virtual, not unique/resident
memory. Python host resource samples are after SQL, not peaks. Go CPU includes
observation overhead; Python CPU includes runner and reaped hosts/helpers.
Parallel phase CPU/overlapping memory counters are not summed. These are the
same observer meanings as the approved previous campaign.

## Completion, limits and next decision

| Item | Judgment |
| --- | --- |
| Approved 80-cell matrix and 8 pilots | COMPLETE / PASS |
| SQL/transaction/separate connections/child isolation | PASS in unchanged workload oracles |
| Go bounded cleanup/resource invariants | PASS |
| Identity, identical observers and evidence reduction | PASS |
| Performance outcome | Mixed; adverse cells disclosed, startup-tail placement is material |
| Native Ubuntu product measurements | SKIP: campaign uses the approved same-Mac comparison; Ubuntu Qualification passed separately |
| Wider workload/long-run statistical or leak/race guarantee | Not a claim of this finite campaign |
| Main integration, tag, publication | Not performed |

I recommend candidate adoption: both-native Qualification and the agreed
corrective investigation are closed, product SQL/resource boundaries pass,
and the measurements do not expose a new functional/resource blocker. The
strongest objection is the specific slow Go parallel-Fresh median above.
I assess it as non-blocking under the existing approximately-one-second startup
tail contract, while retaining the actual samples and making no tail-rate claim.
If a tighter startup/throughput requirement is desired, define its target and
a separate bounded tail-rate comparison; do not reopen the completed memory
compatibility investigation without a concrete new failure.

[Recipe and retained evidence](v050-product-evidence/README.md),
[raw/saved hash manifest](v050-product-evidence/evidence-manifest.json) and
SHA256SUMS preserve reconstruction. The initial single-use workspace runner
refused a second run after the build had completed; the documented disk-guard
route then executed the campaign with task-owned scratch. No cell/oracle was
skipped or retried to hide a failure. Report commits are distinct from the
exact qualified/measured runtime source; future release CI owns final-source
qualification and publication.
