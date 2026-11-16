# Read residual investigation

Outcome: choose whether read optimization can materially reduce the25ms P8
suite gap to a10% reference. Product6558ee8f, same matched fixture as7e643765.
First analyze all15saved P8timelines; compare read/write completion without
summing overlapped phases. Allfinish on writer; read contention stillpossible.
Finite intervention: same Maria binary, P8, syncClose, MaxForks16, matched SQL,
audit UPDATE OF status/preaggregate as before. baseline vs SKIP_READ_BODY=1:
50reader cases still share/load fixture but return before query/assertions.
All20writer tests/assertions unchanged. This is a diagnostic, never a semantic
PASS for70tests or a deployable variant. Sync baselineAA mixed with AB skip,
5pairs each, alternating order, shuffledseed119,2warmup+20main=22suiteprocesses.
Retain external/internalwall, CPU,RSS and allspans. No adaptive sampling.
Separate query-only CPUprobe:4000GetOrder operations after fixture/sample load,
no parallel writers,3runs. Record setupoutsideprofile; profile includes engine
backgroundthreads during query window. It is not a syscall/wall causal fraction.
Inspect current host↔guestcall count from source; do not replace transport or SQL.
NoPG rerun, no resource tuning or engine patch. SharedMac/Go1.27.4/CGO0/P8.
Stop after onecohort+profiles; report unknowns/recommendation. Recurrent69second
observation requires Issue per Human direction. Budget10GiB/free12GiB/timeout1800.
