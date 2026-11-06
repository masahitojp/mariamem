# Issue117: connection-confirmation polling dominates this cleanup recipe

**Recommendation: continue to a small host notification candidate.** The fixed
observation found a recurring confirmation delay after the final session was
removed. It met the predeclared lead threshold in all three diagnostic processes.
This is a reason to test notification, not an adoption or measured-speedup claim.

The strongest limitation is applicability: this workload explicitly calls
WaitDisconnected for every child; ordinary Go fixture cleanup does not require
that recipe. The benefit cannot be generalized to all Fork users. Notification
also has correctness costs (lost wakeups, cancellation, failure/Close and multiple
waiters); retaining polling is preferable to weakening those contracts.

## What the observation separates

Connection/pool Close -> WaitDisconnected -> Database.Close.

The ordinary mode has phase stopwatches but disables detailed host observation.
The diagnostic mode records final session deletion under Server.mu, every Active
check, completed timer interval and successful zero observation. The timestamp
is taken immediately after the final clients-map deletion, before the same lock
is released. It is eligibility for Active()==0, not worker/mapping disposal.
No new connection is admitted by this recipe after retirement begins.

Both modes use the same experiment binary. Only ISSUE117_TRACE changes; no
notification implementation, shorter polling interval, direct-Close alternative,
guest change or setting override is applied. Added fields/conditional hooks and
phase timing mean ordinary mode is not a pristine shipping-binary benchmark.

## Fixed workload and source

- Product source: `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Measured harness: `1a2b5dc00f8f523a9f58c8fdd66065ff2d806eb0`.
- Parent harness: `3be0dd9ef3d9740bbd59fe32e03225f7cc717120`.
- Guest SHA256: `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Apple M1,16GiB,macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,GOGC100.
- Go Pipe,1,000 integer rows,48 children,4 workers,explicit cap4. Product defaults.
- Three fresh processes per mode, alternating ordinary/diagnostic order; one
  separate48-child warmup per mode; one diagnostic wrong-seed child. Nine total
  processes, zero added repetitions. Warmups are outside the144-child denominator.
- Root creation/Snapshot and final Snapshot.Close are outside batch timing, but
  all are executed and cleanup-checked. SQL/isolation, affected-row/value, cap and
  no remaining owned scratch checks pass. Wrong seed fails as intended and cleans.
- Commit identity/clean source checked before build. inputs.json binds exact
  binary, guest, buildinfo and before/after overlay hashes. Canonical product,
  guest, generated code and public API are unchanged; overlays are experimental.

## Result

Pooled per-child medians across144 children per mode, milliseconds. These are
independent phase medians and must not be added as an exact decomposition.

| Phase | Ordinary | Diagnostic |
|---|---:|---:|
|Connection/pool Close|0.0079|0.0081|
|WaitDisconnected|5.1937|5.2349|
|Database.Close|2.6890|3.1454|
|Complete child cleanup|8.0463|8.5526|

Diagnostic evidence:

- All144 children first saw Active()==1, completed exactly one5ms timer interval,
  then observed Active()==0. No early-zero or missing-idle sample.
- Wait entry -> final session deletion: p50 **0.0785ms**, p95 **0.2175ms**,
  max **0.6905ms**.
- Final session deletion -> successful Active observation: p50 **5.1067ms**,
  p95 **6.0370ms**, max **6.2212ms**. All these transitions occur inside the wait.
- Per-process median confirmation gaps: **5.0756 /5.1596 /5.0986ms**.
- Per-process median child wait/cleanup fractions: **63.5% /61.2% /62.7%**.
- Predeclared lead gate (median confirmation >=1ms, median wait fraction >=20%,
  in at least2/3 processes): **3/3**. This gate selects further work only.

The measured gap includes timer granularity and scheduling after a session is
already gone. It is not all time spent disconnecting or MariaDB work, and it is
not proven that a notification candidate will remove the entire5.1ms. Callback
work occurs after the final check; confirmation uses the check timestamp, not
callback return. Diagnostic timestamp/check collection still adds overhead.

## All primary processes and tails

| Mode / rep | Wait p50 ms | Cleanup p50 ms | Batch wall ms | Batch CPU/child ms | SQL block >100ms |
|---|---:|---:|---:|---:|---:|
|ordinary /0|5.1734|7.9814|1020.259|59.973|1|
|diagnostic /0|5.1580|8.4175|612.632|64.414|0|
|diagnostic /1|5.2578|8.7726|633.719|63.247|0|
|ordinary /1|5.1225|8.3924|634.270|64.100|0|
|ordinary /2|5.2310|7.9663|1222.756|59.054|2|
|diagnostic /2|5.2305|8.4647|649.531|64.395|0|

Ordinary SQL blocks over100ms were815.024ms (r0 child15),785.859ms (r2 child6)
and804.738ms (r2 child25); diagnostic primary had none. They remain in all data.
Warmup diagnostic had one long SQL block, also retained separately. This harness
does not split the SQL block into individual query timings, so those values must
not be labelled UPDATE durations. The observer may change scheduling; different
SQL tails prevent treating the two modes' batch times as a speedup or precise
observer-overhead estimate. Issue68 stays stopped. No tail was excluded.

Lifetime peak RSS is retained in raw process records, not presented as retained
child RSS. Batch CPU includes SQL/background/cleanup and is not Fork-only CPU.
This local cohort is not merged with older TCP/Pipe or pgmem measurements.

## Next bounded decision

A host event-notification prototype is justified for this entry path. It should
wait on connection-count change under the existing server lock, recheck state,
and preserve context cancel/deadline, database failure/Close, multiple waiters
and actual disposal/limiter lease boundaries. Do not merely decrease the timer
or return before guest-session cleanup. No product implementation is approved
by this report; choose the finite correctness/A/B plan before that step.

Ordinary fixture direct Close and pgmem discard/partly asynchronous disposal have
different completion boundaries. This result does not make those paths equivalent
or predict a suite-wide gain of48 times the per-child gap. Critical path and
parallel overlap still matter.

## Verification and reproduction

Observer unit plus existing WaitDisconnected tests pass: immediate zero and
live-session timeout; recorded success/idle state is checked. All nine runtime
processes satisfy their expected SQL/negative/cleanup outcomes. Analysis controls
reject incomplete process sets, failed oracle/cleanup, duplicate child ID,
missing idle observation, nonzero final Active and wrong timer count.

`python3 analyze.py --check` recomputes summary.json and children.csv read-only
from this directory; `PYTHONDONTWRITEBYTECODE=1 python3 test_analysis.py` runs
analysis controls. SHA256SUMS.json binds every retained file except itself. No
removed temp/build inputs are needed for replay.

For fresh execution, use the exact measured harness in a disposable workspace;
copy ../plan.json, ../build.py, ../run.py into evidence/ then run build.py and
run.py under the recorded toolchain/budgets. Dependencies/binary/overlay are
recreatable; reruns create new observations. The9-process protocol refuses to
restart after records.json appears. No heavy CI, main integration, qualification
or release was run. The observation stops here.
