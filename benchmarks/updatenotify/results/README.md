# Same-wait notification tracing: long UPDATE not reproduced

**Conclusion to the host-shim question:** the previously captured355ms UPDATE did not recur in this fixed three-process diagnostic. We cannot attribute that long case to late guest notification or delayed host wakeup from this run. Fifteen shorter natural query waits were linked to their exact notifications/resumptions; six have the rollback-page scope. These show no unconditional hundreds-of-ms shim delay, but do not exonerate the shim in the unobserved long case.

Recommend stopping this finite run and retaining the ready collector. Further repetitions need a separate finite decision; do not expand a parameter sweep or treat non-reproduction as a fix. Original355ms capture and its source correspondence remain unchanged.

[Notification timeline](report.html) · [All joins/distributions](summary.json) · [Per-process CSV](processes.csv) · [Fixed plan](plan.json)

## Observations

| Natural process | Parallel | Children | UPDATE maximum ms | UPDATE >100ms |
|---|---:|---:|---:|---:|
| natural-0 | 8 | 48 | 29.176 | 0 |
| natural-1 | 4 | 48 | 4.495 | 0 |
| natural-2 | 8 | 48 | 16.293 | 0 |

Exactly3 processes/144 natural children,P8/P4/P8. No extra natural repeats,no excluded samples,no new tuning settings. Result **NOT_REPRODUCED**, not CAUSE_PROVEN or FIXED. No natural slow stack was captured. Observer/trace hooks alter scheduling,so absence is not a cure or frequency estimate.

For all15 signaled natural waits, the measured channel-close-to-resume upper bound has median0.012792ms,max2.679583ms. Notify-attempt-to-close upper bound max0.067875ms. Six rollback-page-scoped waits have close-to-resume upper bound max0.601208ms. These are instrumented Go scheduling/trace-inclusive bounds,not pure kernel wake costs or population limits.

A concrete **short** page wait, natural-0/P8/child21:

| Component | Measured value |
|---|---:|
| Registration → wait function return | 14.350875ms |
| Registration → channel-close bounds | 14.342792–14.343250ms |
| Channel close → resume bounds | 0.007000–0.007458ms |
| Notifier call → close upper bound | 0.000583ms |

In this observed14.35ms page wait, nearly all elapsed time precedes the notification. That result applies to this short case, **not** to the previous355ms UPDATE. The prior case has no matching notify timing and must not inherit these numbers.

All six page-scoped short waits expose space_id1/page_no3 through current Fn17227 rollback-segment fields. This corroborates that the intended current rollback-header page path is being instrumented. The355ms case did not record a page number; its exact identity remains unknown. Raw mutex addresses and futex EAs are distinct guest addresses (pthread condition internals can wait on another address),and can be reused across instances. Joins require child/instance namespace plus wait/channel ID and EA,not numeric address equality across DBs.

## What the collector measures

Experiment-only overlays retain the existing both-OFF/commit1/inherited O_DIRECT profile and all25 original arguments. Current generated function numbers remain bound to guest6d744220 and exact input/source hashes. No old guest map is reused.

- Existing Fork context binds each module ThreadPool to its actual child index. Root is not admitted to this child collector.
- Current Fn5853 marks only the explicit fork_probe UPDATE. Fn17227 adds rollback page scope; Fn16621 adds mutex slow-path begin/end. The prior source-correspondence receipt is retained with a prior- prefix,not relabelled to the new source.
- AtomicWait records actual parked-channel registration,resume and return. The wait ID is unique within that instance.
- ThreadPool.wake records timestamps immediately before/after closing the **same registered channel**,with a notify ID and notifier guest-thread identity. This binds observed signals directly rather than inferring a signal from nearby timestamps.
- Notify attempt/return bracket park-mutex/wake work. Matching-notifier caller stacks are captured only for wait registrations lasting100ms or more,and only after parkMu has been unlocked; stack walking is outside the wake critical section, but can still affect scheduling and the observed close/resume interval. There was no such natural case here,so no natural late-notifier C path is identified.
- Owner acquisition is not comprehensively instrumented. A notifier thread/path is not automatically the original page-lock owner.

The before/after timestamps bracket channel close. A waiter can resume before the after timestamp is observed; lower bounds are clamped at0 and upper bounds use the before timestamp. This avoids claiming a negative or falsely exact notification latency. All pairs require matching wait/notify IDs,EA,thread/query context and successful wake count. Recorded event timestamps are reduced by identity/time,not assumed append order.

## Controls and fixed boundaries

One M1/16GiB/macOS27.2,Go1.27.3 arm64,CGO0,GOMAXPROCS8,GOGC100,Pipe,1,000 rows,cap=P. Three natural processes plus one8-child effective-setting preflight,one SQL-side200ms SLEEP control,one wrong-seed rejection:6 processes. Positive SQL/pristine seed/independent update/cleanup PASS. The control has a usable actual-Exec child-bound profile; artificial SLEEP is not natural-cause evidence. Wrong seed fails before UPDATE/no captures/cleanup PASS.

Focused host tests exercise real AtomicWait/AtomicNotify: another instance with the same address and wake-count0 do not wake the target; the correct notifier wakes exactly one and joins the right registration,close,resume and return. Tests cover child binding and the8192-event cap. The truncated flag is mandatory rather than silent dropping; actual traces are untruncated. Selector and prior observer label/Exec-window controls also PASS. Readonly reduction rejects missing processes,wrong signal EA and missing matching notify-return.

Trace timestamps,registry locks,allocations and the existing threshold profiler add overhead and can alter rare interleavings. This is not performance A/B evidence. Do not generalize the normal15 waits to all host scheduling,all futex races or the previous long UPDATE. No internal queue depth,owner-held duration or I/O completion delay is asserted without its corresponding trace.

## Outcome and concrete remaining work

Known: exact notifications/resumptions can be paired; observed short rollback-header waits resume quickly after close; the prior355ms query was parked in an untimed guest notification wait by current source correspondence. Unknown: why the long case delayed,which owner/task held the lock,when it notified,and whether the old COUNT thread-pool clamp explains this UPDATE.

The next cause evidence remains a **natural long page wait** with this same wait/channel/notify binding and matching notifier path. One further finite collection could reuse these committed hooks and collector; choose a cap before running,and retain NOT_REPRODUCED if absent. No further repeats or product fix start automatically here. If a notifier is late,its caller path/queue ownership must then be verified against current source before choosing a correction; if actual channel close is early but resume late,the host scheduling/shim path becomes the focus.

## Source and retention

Product source_commit `1862f4a89397bddfa1820d835106d3437a438cf7`; measured harness source_commit `cbf0022c69d2f9ff95d2199b159823d85ebc7019`; parent94ab0a54. Clean identity verified with scripts/git_identity.py before build. Binary SHA256 `b56434781ade4181d18e1e52e13cfa20859f75a65bc5fb5f8b434e986f7d5e55`. Origin guest SHA256 `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe` identifies the unchanged generated input,not a new canonical WASM. This is an UNQUALIFIED diagnostic argv/host/generated-code overlay; source additions are confined to benchmark tooling. The overlays are not merged into canonical product,guest,public API or generated source.

Each original/overlaid file is bound by before/after hashes in inputs.json. Disk6GiB/free12GiB and120s process guards did not trip. Ubuntu/native parity/canonical qualification and release NOT RUN. No CI dispatch,adoption,main integration,version or release-ledger change.

receipts.zip retains all process/control/child traces,profiles,metadata,logs,unit receipts,input/plan hashes,prior source context and build/run/reducer scripts. Extract into an empty directory and run python3 analyze.py --check for readonly exact6-process joins/JSON/CSV and negative mutation controls. Rebuild new diagnostics from clean measured source with archived build.py/run.py in evidence/temp/source layout. SHA256SUMS.json covers published files. Reproducible source clone,probe and private caches are removed after preserving compact knowledge and pushed refs.
