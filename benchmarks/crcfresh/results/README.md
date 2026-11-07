# CRC follow-up: Fresh startup slowdown is not stable; small batch delta remains

The question was whether the prior Fresh slowdown came from the CRC replacement
or surrounding runtime/measurement variation. **The prior consistent startup-p50
slowdown did not reproduce under balanced order. A small whole-batch difference
remains, and its cause is not established.** This is not a universal
non-regression result and not proof that all differences are environmental noise.

Recommend retaining the CRC candidate rather than reverting it on this evidence.
Its earlier Fork benefit keeps its original source/measurement context. Carry
Fresh's approximately+17ms per48-child batch paired median into adoption review;
do not silently accept it or relabel it as zero. The next product decision is a
maintainable integration boundary and explicit treatment of this small unresolved
counter-result. This bounded follow-up ends here, without more repetitions.

## What changed in this investigation

The candidate computation, CRC table, range checks, checksum/LSN comparisons and
all non-CRC settings are unchanged from the prior prototype. A diagnostic overlay
adds counts at Fn18145 entry and immediately before its selected L23 CRC branch:

- Atomic process-lifetime totals, including preparation/root activity.
- Exact child ThreadPool-lifetime totals in the existing UNDO-owner record,
  including that DB's worker threads; no per-call timestamps or event logs.
- The actual process CRC mode in the report, independently checked against the
  requested arm. Fast-path count must equal CRC count only in the fast arm.

Process totals minus child sums expose unbound/root work. Counts are captured
after the suite timer/resource sample, and owner records are flushed under the
existing ownership/cleanup contract. Counter overhead is common to both arms;
these measurements must not be compared as absolute shipping timings.

## Balanced primary comparison

Apple M1,16GiB, macOS27.2 arm64, Go1.27.3; P1,48 Fresh children per process,
same binary/warm static-page experiment/schema/seed/Pipe settings. Owner logging
is on, detailed startup timing off. The fixed eight-process sequence is
**software, fast, fast, software, fast, software, software, fast**. Pair indices
are(0,1),(3,2),(5,4),(6,7): two orders each. No result-driven additions or exclusions.

Positive values below mean fast is slower:

| Pair | First arm | Startup p50 delta | Batch wall delta | Batch CPU delta | Close p50 delta |
| --- | --- | ---: | ---: | ---: | ---: |
|0|software|+0.6289ms|+38.588ms|+41.285ms|+0.1174ms|
|1|fast|−0.3787ms|−15.436ms|−29.675ms|+0.0754ms|
|2|fast|+0.0347ms|+18.711ms|+27.840ms|+0.0473ms|
|3|software|−0.1374ms|+15.396ms|+51.206ms|+0.0249ms|

Median paired startup-p50 delta is **−0.0513ms**. The prespecified replication
criterion (at least3/4 pairs >=+0.25ms and median >=+0.25ms) is not met: only1/4
pairs crosses that threshold. This is a bounded descriptive criterion, not a
statistical equivalence test. Startup means still increase in3/4 pairs, so the
p50 finding must not be used to erase upper-distribution or whole-batch costs.

Median paired batch delta is **+17.053ms**, about1% of a roughly1.74s batch;
CPU delta+34.563ms. Median paired suite delta, including setup/cleanup, is
+31.516ms. Pair3's suite delta+70.352ms exceeds its batch delta+15.396ms by
54.956ms, locating additional variation outside the child batch.

Medians of process batch values are1743.692→1754.729ms; these differ from the
median paired delta and should not be substituted for it. Seed p50 increases
in all four pairs (+0.045–0.202ms), as does Close p50. There is no clean finding
that CRC fixes all costs or Fresh becomes exactly neutral.

## The selected CRC path is rare in Fresh, but not absent

Across192 primary Fresh children per arm:

| CRC invocations over complete child lifetime | Software children | Fast children |
| --- | ---: | ---: |
|0|113|104|
|1|74|74|
|2|5|13|
|3|0|1|
| Child total calls |84|103|
| Preparation/unbound total calls |2|2|
| Entire process totals over four runs |86|105|

Every counted CRC covers16,380 bytes. The observed validator count equals the
CRC count in these samples. This is not an all-format invariant. The proposed
"CRC never executes anywhere in Fresh" explanation is **false**; the process
counter closes the root/preparation blind spot as well as child attribution.

However, most Fresh children never enter the selected calculation. Post-hoc
zero-CRC subsets still show startup p50 deltas+0.913,−0.267,+0.011,+0.008ms and
Close p50 deltas+0.319,+0.063,+0.042,+0.049ms. These are descriptive subsets,
not randomized independent controls: scheduling can affect CRC call count, and
prior/root activity can affect later children. They weaken the simple explanation
"the new CRC computation itself makes every Fresh child slower" without proving
an environmental cause or excluding indirect scheduling/GC effects.

Two four-child Fork semantic controls establish that the observer actually sees
CRC work and the selected mode: software children have415–416 CRC calls each;
fast children319–320, with exactly that many fast-path calls. Their SQL and cleanup
pass. **Whole-lifecycle call counts differ**, so do not claim identical total
engine work or attribute every whole-suite saving solely to faster computation
of an equal page count. The earlier diagnostic rseg-header interval separately
had128 calls in both arms. These small Fork controls are not a new Fork
performance campaign; the cause of their lifecycle-count difference is unisolated.

## Separate Fresh diagnostic pair

Two48-child runs enable existing startup instrumentation. They are excluded
from primary deltas. Relevant mean intervals:

| Interval | Software | Fast | Fast−software |
| --- | ---: | ---: | ---: |
| Host API/start interval |24.920ms|24.477ms|−0.443ms|
| Guest server initialization |20.603ms|20.482ms|−0.121ms|
| Common initialization |8.374ms|8.675ms|+0.300ms|
| All plugins |9.852ms|9.456ms|−0.396ms|
| InnoDB plugin, within plugins |5.898ms|5.692ms|−0.206ms|
| Buffer pool, within InnoDB |1.330ms|1.295ms|−0.035ms|
| InnoDB open/recovery, within InnoDB |0.777ms|0.749ms|−0.028ms|

Nested rows must not be added to parents. The reducer verifies complete original
stage pairs and accounting. Fresh rseg-header acquisition has one cache hit and
zero read-complete/CRC invocations in both diagnostic runs, while the broader
child-lifetime counter records18/16 calls. Thus header-only zero was never a
valid statement that the entire Fresh DB did zero CRC work.

This pair does not reproduce a slow InnoDB/read-completion interval in the fast
arm. Common initialization moves the other way, but one diagnostic pair cannot
explain the ordinary runs or identify a specific scheduler/allocator/GC cause.
We did not capture per-operation positions/durations for the rare Fresh CRC calls,
host scheduling/GC profiles, thermal state or independent background CPU load.

## Controls, identity and completion

Binary source_commit **`a6ebe27ddfdbeaeb490078f09e254203dc953643`**;
parent report **`e1fe6d448c5193a02cb5fa0f59ecdccbae631945`**.
Guest SHA256 **`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`**
unchanged, MariaDB12.3.3. `inputs.json` binds plan, overlay, binary and exact Git
identity. `counter-mapping.json` describes the new counts; `crc-mapping.json`
retains the unchanged candidate computation's mapping. `prior-analysis.json`
pins the previous summary hash and its phase-level findings.

One benchmark binary was built (8.3s after correctness-test compilation populated
the dedicated cache). CRC832-case equality and80-case actual validator corruption
checks pass again. Counter scope/concurrency tests and their race execution pass,
as do inherited observer and wave tests. No optimization or generated guest
regeneration was performed in this follow-up.

Fixed campaign:2 Fresh semantic pilots×4,2 wrong-seed controls×1,2 Fork semantic
positive controls×4,2 Fresh warmups×48,8 primary Fresh processes×48,2 diagnostic
Fresh processes×48: **18 processes /594 children**. SQL/state/isolation and cleanup
pass, negatives fail as expected, no retries/additional samples. All594 owner
logs remain untruncated,1,341,187 events. Final mappings/reservations/failure
counters and image FDs are zero. No child elapsed span exceeds100ms; all data
remain. Root/setup deltas remain visible rather than being deleted as noise.

Seventeen private-copy mutations are rejected, including actual-mode mismatch,
missing/negative/global-vs-child counter errors, missing positive detection,
wrong order, lost diagnostic stages, SQL, cleanup and owner failures. Retained
source/archives/checksums support replay after owned temp/build/worktree removal.
No product/main adoption, versioned release, Linux or parallel acceptance is claimed.

## Replay and remaining decision

```sh
python3 -B analyze.py . --check
python3 -B subgroups.py --check
python3 -B check_analysis.py
```

`summary.json` stores all children, stages, CRC totals, pair deltas and criterion
results. `subgroups.json` explicitly labels post-hoc lifecycle subgroups.
Original process/timing records and all owner logs are compressed with member
hashes, covered by `SHA256SUMS.json`. New runs use this exact binary-source
commit's `benchmarks/crcfresh/build.py` and `run.py`, not a later report SHA.

A strict no-Fresh-regression claim still lacks a stable reproduced mechanism and
phase-specific evidence for the rare CRC calls or surrounding host work. If that
claim is required before adoption, a concrete bounded follow-up is one build with
per-operation CRC counters and host GC/wait markers, four matched Fresh pairs,
and the same controls: approximately3–5min build plus under2min runtime, with
20–30min total implementation/analysis budget on this host, excluding CI.
That work is not silently appended here. Otherwise carry the measured small
Fresh whole-batch delta as an explicit review item while designing the permanent
CRC integration, rather than restarting an unbounded search for zero variation.
