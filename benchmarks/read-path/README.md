# Read-path residual after Go async Close adoption

**Conclusion:** saved P8timelines finish on writer work in all15runs (5sync,
5async,5PG); readers finish earlier. Current GetOrder-only CPU profiles still
show OS pipe Write/syscall as a major cost. Eliminating read bodies changed whole
suite wall by paired median−23.020ms/−5.263%(4/5faster), but contemporaneous
samebinaryAA abs median9.307% is larger, range−27.113..+9.307%. Therefore this
campaign cannot establish that optimizing reads will deliver the25ms needed for
a10% gap. Read optimization remains plausible, not a proven critical-path fix.

Recommendation: keep the reader body and internal-transport hypotheses distinct.
Do not repeat the rejected4KiB host response-buffer trial (#185). If another
spike is authorized, require a bounded request/transport intervention with same
SQL/results/failure semantics, query-level latency/CPU plus full-suiteAA/AB.
Do not implement a new transport or engine change from this profile alone.
No automatic additional campaign is started.

## Fixed scope and historical reconciliation

Product source_commit6558ee8fb2211313a8aa0ea6070ac5256767811a, same runtime as
fixed benchmark7e6437656a3e1c4d555aacb367bc43275db6ee05. Diagnostic harness
source_commit25dfdf98 (full in inputs.json), Go1.27.4/macOS arm64/CGO0,
GOMAXPROCS8/GOGC100, MaxForks16, syncClose, interpolation enabled,
SUM/audit with UPDATE OF status and matched preaggregate revenue SQL retained.
NoPG rerun. Main/workspace user changes were untouched; isolated experiment only.

Historical modelcase-sql-cost-20261113 used0f5b26f3 and observed GetOrder raw
syscall59%, guest writeVec36.1%, host writeAll9.6%; its short profile included
fixture/setup. PREPARE avoidance and revenue rewrite are already in the current
harness. #185's fixed4KiB host buffer cut underlyingReads2→~1/frame but P8wall
worsened (+3.852% paired), so it was not adopted. The earlier mixed-iovec empty
Write skip was also an unadopted experiment per #185, not assumed present here.
Current base.writeVec still delegates every iovec; no new measurement of empty
Write frequency in this investigation. No claim that zero-write removal was
lost from an adopted product or that its old benefit applies now.

## Saved timeline: readers vs writers

saved-timeline.json recomputes read/write completion from all15P8traces, not
just medianruns. Sync readers finish39.3–90.9ms before the lastwriter body;
async14.2–81.4ms,PG13.0–62.3ms. Lastwriter types vary. The trace's testbody end
is before that testcase's cleanup; suite end is after cleanup. This identifies
who finishes last, not which activity consumed CPU or caused the lastwrite to
run late. Readers can contend for scheduling/CPU and affect writers indirectly.

## Same-binary intervention

5comparisons of fullbaseline with SKIP_READ_BODY=1, interleaved5samebaselineAA,
2warmup+20main=22suiteprocesses. Five read-scenario t.Run bodies still call
fx.Read (t.Parallel, same shared sampleload), then return before SQL/assertions.
All20writer bodies and assertions are unchanged. Each run still records70spans,
20writerForks. This is an intentionally incomplete reader workload diagnostic,
not a PASS of all70applicationassertions or an alternative production benchmark.
Sameabsolute binary/path/args/env withinAA; labels onlyrunner. Alternating pair
order/jobshuffle seed119. No drop/repeat/adaptive sampling; no concurrent build
or profile while suite timings run. SharedMac/5pairs; thermal/placement uncontrolled.

AB deltasms: +3.471,−8.894,−93.558,−26.502,−23.020.
AA deltasms:−49.587,+13.229,+37.725,−150.390,+36.298.
AB independent suite medians434.522→408.020ms (different from paired delta).
Baseline/skip writer-body end medians429.589→404.506ms; readend369.207→347.569ms.
CPU independent medians2199.054→2103.978ms; diagnostic removes actual work,
so this does not quantify a deployable optimization. No noise subtraction or
confidence interval. The largestbaseline AA554.677ms is an ordinary subsecond
slow observation retained, not the historical69second recurrence.

## Query-only CPU probe

After sharedfixture and samples load, profile4000GetOrder calls in one test,
no parallelwriter. EachGetOrder executes two SELECTs (orders header/items),
so8000SQLrequests; the official read testcase fetches4orders,8SELECTs. Source
inspection verifies interpolation and Process.Call framing over the two OS
pipes; no new requestcounter/syscall tracing was added. The80SELECTs in the
10GetOrder testcases are not the thousands of prepared INSERT calls in sampleload.

Three probes GETORDER4000_MS1044.867/1028.421/1030.331: about0.257–0.261ms/order
under serialprobe, not the concurrent suite's2.54ms per4order testcase.
CPU profiles cover1.11–1.13CPU seconds perprobe. rawsyscalln flat64.29–71.17%;
os.File.Write cumulative61.61–66.67%; guestFd_write/writeVec53.98–58.04%;
hostwriteAll3.57–9.91%. Runtime condition signal/wait/kevent are also visible.
These cumulative percentages overlap and must not be summed. Short100Hz
samples include runtime/engine background activity during thequerywindow,
exclude fixture load before profiling, and are not percentages of querywall.
Maria queryexecution is not bypassed or timed independently. Therefore no
exact engine-vs-communication wall decomposition is established, nor an upper
bound on wall savings. Small engine CPU samples do not prove zeroenginecost.

## Evidence, exit and remaining question

All22suite processes and3profiles completed successfully within the diagnostic
scope; originalwrite assertions and Closeerrors remain. Earlier69second problem
did not recur; no new recurrenceIssue. Allrawsuite traces/logs,3CPUpprof files,
rawstack text,source/binary identity and runner are retained. Regenerate using
PLAN and run.py with an owned workspace (temp/evidence exist); compiler output
and caches are disposable. No new product code, release or main integration.

What is known: writer work ends last; read execution can consume shared CPU;
current GetOrder's CPU is strongly concentrated in pipeWrites/runtime wakeups.
What remains unknown: a deployable transport/query change's end-to-end gain,
causal syscall counts/bytes on current source, and whether it can recover25ms.
A future bounded candidate must retain correctness and repeatAA/AB; merely
shortening GetOrder or reducing Read count does not answer the whole-suite goal.
