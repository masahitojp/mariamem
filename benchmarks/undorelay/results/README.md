# Issue68: UPDATE / purge / page-wait correspondence

**Short relay bound in two samples; no natural long UPDATE reproduced.**
The new observer binds the query's requested rollback-segment latch, purge's
held latch, its header page, notification and release ordering within the same
child instance. Both page-wait registration samples saw FOR_IO + WRITE_FIX.
This confirms the proposed relay for short samples, not the cause or duration
of the earlier355/367ms events.

## Recommendation / stopping point

Preserve this as a confirmed mechanism and stop this finite experiment. The
remaining uncertainty is what occasionally stretches notification to hundreds
of milliseconds. A future long event with this complete binding could locate
the responsible holder kind. I/O submission/execution/completion queue timing
remains outside this collector and is not justified as an automatic next step.
No parameter, shim, canonical guest or product adoption is proposed here.

The main objection to extending the inference is timing: owner is sampled at
background wait registration (before the query arrives in both linked samples),
not continuously throughout the overlap. No100ms owner sample fired. Do not
claim continuous I/O ownership over either query or retrospectively attach
these page IDs/owners to an older event. Instrumentation also changes timing.

## Source and protocol

- Measured harness: `2f679a14d45acf0dac98effc7172f38301f7a3b3`.
- Parent observer: `f678de708c7e376f53b6d021976fc7f17827e3e4`.
- Product: `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Guest input: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Exact binary, Go1.27.3 darwin/arm64 buildinfo and overlay before/after hashes
  are in inputs.json. Source identity and clean checkout checked before build.
- New generated anchors: Fn17010 slow rseg-latch acquisition; Fn17211
  post-acquisition, before/after successful unlock, end/abort. Existing Fn17227
  header scope and Fn18164 page owner hook now operate in the purge context too.
  ../layout.json binds generated hashes and exact labels/field offsets.
- Local Mac, P8/cap8, Pipe, GOMAXPROCS8/GOGC100,1000-row seed, same SQL sequence.
  Both buffer-pool load/dump OFF, commit1, O_DIRECT,16MiB/read1/write2/purge1.
- Same external20ms RSS sampler and ready/go/done handshake as the paired replay.
- Six processes total: root+eight-child settings, wrong-seed expected failure,
  one48-child warmup, three48-child primary batches. No extra repetition.
- Settings, SQL/value/affected-row/isolation and cleanup gates passed.
  The wrong-seed process failed as expected and cleaned up. No owned DB scratch
  remained. No CI, main adoption, qualification or release.

## Results

| Process | Children | Max UPDATE ms | >100ms |
|---|---:|---:|---:|
|Warmup (separate)|48|19.497834|0|
|Primary0|48|12.788375|0|
|Primary1|48|4.646417|0|
|Primary2|48|13.941916|0|

The trace captured53,760 completed purge latch scopes, zero purge scope aborts,
five query rseg atomic waits and eight background header-page atomic waits.
All eight page-wait entry samples were IO/WRITE_FIX. Two query waits overlapped
page waits while purge held the identical rseg latch; both have matching
releasing thread and the full recorded return/release/signal sequence. The
other three query waits are not assigned this chain. No trace was truncated:
maximum3,553events/child against the fixed8,192 limit.

| Bound sample | Query register->resume ms | Background page register->resume ms | Overlap ms | Entry owner |
|---|---:|---:|---:|---|
|Warmup child12|3.419583|7.951042|2.845500|IO / WRITE_FIX|
|Primary0 child11|0.316417|10.018959|0.287792|IO / WRITE_FIX|

Both use rseg address17881408, latch17881412, header space1/page3 **within their
own instances**. Same numeric addresses across different instances never form
a match. Query/purge thread identities and purge scope IDs are distinct and
recorded; the notifier thread matches that exact purge scope.

Relative to each query's atomic-wait registration:

| Event | Warmup child12 ms | Primary0 child11 ms |
|---|---:|---:|
|Purge acquisition observed|-5.108584|-9.734000|
|Background page wait registered|-5.105542|-9.731167|
|Query wait registered|0|0|
|Background page wait resumed|2.845500|0.287792|
|Page writer-mutex slow call returned|2.846958|0.290917|
|Header-page get returned|2.849708|0.298375|
|Purge unlock before|2.850208|0.299500|
|Purge unlock after|2.850333|0.299917|
|Query signal before|2.850666|0.315125|
|Query resumed|3.419583|0.316417|

Wait durations/overlaps use **resume**, not the later AtomicWait return. In the
warmup example that later return was7.437708ms after registration; it must not
be counted as7.44ms continuously asleep. Full raw timestamps are retained.
Client UPDATE durations for these two samples were7.789334ms and0.819958ms;
this is not an uninstrumented performance measurement.

## Binding and controls

Required match: same instance file, requested rseg == held rseg == page scope
rseg; query atomic-wait address == rseg+4; matching purge scope/thread;
observed held interval encloses page wait and overlaps query wait; actual page
ID equals scope's header ID. Full release-order classification additionally
requires header-get return before release-before/after, followed by notification
from that purge thread and query resume. No complete owner acquisition history
or transitive cause across unobserved intervals is inferred.

Collector units cover background IO binding, exact release sequence, wrong
rseg rejection, wrong-instance isolation, prior-context restoration and aborted
scope/timer lifetime. Existing owner classification/cancellation controls pass.
Focused observer race tests pass. Analysis mutation tests reject wrong child,
rseg, address, scope, thread, page and nonoverlapping/reversed intervals.

## Reproduction / retention

`python3 analyze.py --check` replays raw-evidence.tar.gz without extraction and
compares summary.json read-only. `python3 test_analysis.py` runs match-boundary
controls. SHA256SUMS.json binds the compact bundle; raw-SHA256SUMS.json binds
all archived members, including all six process outputs, controls, settings,
RSS samples, traces and test/build logs. Fast unmatched scopes are retained so
census and truncation claims remain independently replayable.

For fresh execution, prepare a disposable workspace with exact measured source
as worktree. Copy ../plan.json, ../build.py and ../run.py into its evidence/ and
run build.py then run.py under the recorded toolchain/budgets. Do not run these
from the report directory or repeat an already-started protocol. Build trees,
binary, caches and redundant uncompressed evidence are disposable after verified
archive/ref preservation.
