# Issue65 step3B — native concurrent I/O and admission

Human authorized continuation after3A and asked whether progress is healthy.
Question: can a thin byte transport keep per-session serial native MySQL execution
while other sessions/control progress under output stalls, deadlines, EOF and stop?
Base source_commit712e45edc1464e2ca9f4a41290d046168364fd6b; MariaDB12.3.3
83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e; fixed Linux/arm64 image from3A.
Budget: active2h from2026-11-05 05:53 UTC, measurement tooling30min, CI0,
owned6GiB/free8GiB. Reuse3A native build and packet-client helpers. No3C/3D,
WASIX/generated-Go build, actual Snapshot/Fork/Live, adoption or release.

Implement the proposed private binary DATA/control mux over pipes, per-session
bounded queues/offset acknowledgements, fixed16 slots with epoch/generation checks,
authoritative native-worker command leases and atomic TRY_QUIESCE. Native Vio
callbacks do no MySQL parsing. Upstream NET still owns framing; one pre-allocation
native header policy guard enforces1MiB+1 even after buffer growth. Real THD kill
and condition wakeup implement cooperative native deadline/EOF abort; all workers
join before slot reuse/engine shutdown. No releasing live-worker resources.

Required observations: real concurrent sessions; slow output isolation and control
progress; blocked output/partial input/SLEEP deadlines; bounded1048581 pending input
and65536 outstanding output; EOF behind queued input and overflow poison instance;
serial pipeline/no-response command behavior; busy/transaction quiesce rejection
keeps sessions usable; no queued SQL after fence via deterministic admission hold
and a fixed read-only engine oracle;16 slots/17th reject/reuse after join; late
session/frame/timer messages fail closed; native sequence/warm-buffer length guard.
Capture real SQL/packets/events, original failures, source hashes, profiles, costs
and limitations. Test-only hold/oracle controls are not a product API. A successful
native control spike is not acceptance of the Go/TCP adapter or file capture.
Stop with named missing evidence/cost if this is too broad for the initial budget;
do not substitute mocks or claim absent controls passed. Cleanup owned state.
