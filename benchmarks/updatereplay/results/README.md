# Issue68: original versus owner-observed UPDATE replay

**A natural366.797ms UPDATE recurred in the owner arm's separately retained
warmup. The predefined primary comparison had zero >100ms UPDATEs in both arms
(240children each).** Do not summarize the whole experiment as NOT_REPRODUCED.

The new long event was a real query wait: actual Exec366.292ms, a matching guest
stack inside Exec, and a matched364.481ms atomic wait. At least363.424ms preceded
channel-close notification; resume followed close by about1.057ms. The observed
wait is upstream of the page-owner probe, so this event does not identify a page
latch owner as IO.

## Recommendation and original question

The elapsed-time symptom remains real, and the current instrumentation does not
invariably suppress it. Keep the investigation open with this concrete event;
stop broad natural repetitions. The releasing path and concurrent background
stack provide a narrower source question if work continues: why was undo
history cleanup waiting for a page latch before it notified the waiting UPDATE?
This is a next investigation target, not a proven root cause or product fix.

The strongest limitation is that the long event occurred in a predefined
warmup, not the primary comparison. It is legitimate mechanism evidence from
ordinary SQL, but must not be moved into either primary denominator or treated
as proof of a warmup/cold-start cause. The primary comparison gives no evidence
that either harness consistently suppresses the symptom. The restored external
RSS sampler is not proven causal: it was enabled for both arms and has no
counterfactual arm in this experiment.

## Identities and fixed conditions

- Controller source: `c22fe184` (full identity in inputs.json).
- Product: `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Original harness: `549fd3ba4fdc92b407534bd2b4ce844951fbd4df`.
- Owner-observed harness: `f678de708c7e376f53b6d021976fc7f17827e3e4`.
- Guest SHA256: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Both rebuilt binaries are byte-identical to their earlier recorded binaries;
  inputs.json binds full binary hashes, overlay hashes, buildinfo and commits.
- Both harnesses differ from the product only under benchmarks/. Runtime
  instrumentation is a diagnostic Go overlay, not a product or canonical guest
  patch. No main adoption, API change, CI, qualification or release.
- Local macOS arm64, Go1.27.3, GOMAXPROCS8, GOGC100, P8/cap8, Pipe,48children.
- Same1000-row schema/seed and COUNT/SUM -> UPDATE v=-1 -> affected1 -> SELECT
  -> connection retirement/WaitDisconnected/Close sequence.
- Both buffer-pool load/dump OFF, commit1, O_DIRECT,16MiB buffer pool,
  read1/write2/purge1. Root plus eight-child effective settings matched exactly.
- Same original external20ms libproc RSS sampling and ready/go/done handshake
  on both arms, with3GiB per-process RSS guard. Current owner hooks/watchdog and
  labels enabled only for owner. Historical host load, mixed-variant campaign
  history and thread schedules cannot be restored.

## Results

Five fixed pairs: original/owner, owner/original, original/owner,
owner/original, original/owner. No additional run was made.

| Population | Children | UPDATE p50 ms | Max ms | >100ms |
|---|---:|---:|---:|---:|
|Original primary|240|0.573438|24.187625|0|
|Owner primary|240|0.765646|76.485833|0|
|Original warmup (separate)|48|0.405542|13.395666|0|
|Owner warmup (separate)|48|0.727834|366.797334|1|

Controls: two eight-child settings processes and two expected wrong-seed
failures. Both warmups and ten primary processes completed SQL/isolation,
affected-row/value and cleanup assertions. All16processes completed with no
owned DB scratch left. Selector/observer units passed before runs. No data was
dropped; processes.csv includes controls and warmups. No population frequency
estimate or performance-adoption claim is made.

## Long event: what is actually bound

Owner warmup child12 (not first wave), ordinary UPDATE with no artificial sleep:

| Interval | ms |
|---|---:|
|Client UPDATE wrapper|366.797334|
|Actual Exec call|366.292125|
|Registered wait -> resume|364.481041|
|Registered wait -> immediately before channel close|363.423916|
|Immediately after close -> resume|1.056750|
|Profile collection within Exec|3.756666|

Profile began102.266ms into the operation and ended106.023ms; it cannot alone
account for the preceding wait. Its scheduling effects are not assumed zero.
Wait22/query21 at address17881412 is paired with notify25 in the same child
instance, with before/after-close bounds. The before-close lower bound accounts
for99.71% of registered-to-resume time. The notifier's generated call chain
includes Fn17211, not merely a generic host wakeup. This supports late
notification over a long post-notification Go scheduling stall for this event.
It does not establish why the releasing thread was delayed.

## Source correspondence, with limits

Current generated code plus pinned MariaDB12.3.3 source support:

- Query Fn17010 -> Fn16626 acquires a rollback-segment latch at rseg+4 before
  undo assignment. This differs from the old355ms query stack, which reached
  Fn17227 -> Fn18164 -> Fn16621 and waited on the header page itself.
- The matching notifier Fn17211 unlocks a rollback-segment latch and calls
  wake_all. Its128-entry/128byte-stride loop and header access match
  `purge_sys_t::iterator::free_history/free_history_rseg`.
- At the snapshot, a same-child background stack in that purge-like path
  was itself waiting in Fn17227 -> Fn18164 -> Fn16621, a page writer-mutex wait.
- The C path holds rseg.latch across free_history_rseg, which accesses the
  header page. A relay (UPDATE -> history cleanup -> page latch) is therefore
  a concrete candidate supported by the simultaneous stacks and notifier.

**This is structural correspondence, not a complete recovered symbol map.**
The snapshot does not record the background page ID, its owner, or its rseg
index/thread-ID binding. The notifier address binds the release to the query's
latch, but not every earlier ownership interval. Do not claim all363ms were
spent behind that one background page wait, or that the unseen page owner was
IO. The recorder intentionally attaches owner samples only to the query's
page scope; background page waits are outside it. Nine observed page waits
across the protocol were short; none supplies the missing long-event owner.

See long-wait-assessment.json for raw bounds, generated file hashes, immutable
upstream URLs/hashes and exact correspondence limits. The two selected stacks
are included alongside the full saved profile in the archive.

## Reproduction / retention

`python3 analyze.py --check` replays all records from raw-evidence.tar.gz
without extraction or evidence mutation. The top-level checksum manifest and
raw-member checksum manifest bind the complete compact bundle. Build inputs,
settings, controller plan, all16process outputs, RSS samples, controls, traces,
profile and unit/build logs are preserved. Build trees/caches are disposable.

For fresh runs, use a disposable workspace with the controller checkout as
worktree and clean exact original/owner checkouts as temp/original and temp/owner.
Copy ../plan.json, ../build.py and ../run.py to evidence/; execute build.py then
run.py with recorded toolchain and budgets. Do not rerun a started protocol or
relate a rebuilt source to these receipts without verifying its identities.
