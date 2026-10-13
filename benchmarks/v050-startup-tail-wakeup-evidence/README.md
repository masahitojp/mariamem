# v0.5.0 startup-tail wakeup evidence

The [spike report](../v050-startup-tail-wakeup-spike.md) owns interpretation.
`SHA256SUMS` checks every file here except itself. The original v0.5.0 source
commit/tag, current guest hash, diagnostic/candidate/release binary hashes,
workload and stop rule are in `inputs.json` and `comparison-*-inputs.json`.
The pinned MariaDB file is fetched from its exact source commit in the report;
it is not duplicated here.

`observations.jsonl` records four diagnostic suites. `trace-000.json` through
`trace-003.json` are complete per-process event logs, with zero dropped events.
`ordering-summary.json` is the output of
[`analyze.py`](../spikes/startup-tail-v050/analyze.py), which demands all
four startup instances and checks the early empty-list signal/timeout order.
`excluded-pilot.json` records why the initial broad event trace cannot be
classified. It was not pooled with the narrowed traces.

`comparison-go.jsonl` and `comparison-python.jsonl` hold 30 balanced blocks
each, one JSON line per four-DB suite. `comparison-summary.json` is the output
of [`reduce_compare.py`](../spikes/startup-tail-v050/reduce_compare.py). The
runner [`compare.py`](../spikes/startup-tail-v050/compare.py) checks exact
baseline/candidate binary hashes, process success, four ready samples, and
Python's completed SQL/version oracle before writing a record. `candidate-smoke.json`
is a separate successful four-DB candidate run, not one of the paired samples.
No failed trial was silently retried. Go ready ends at Start; Python ready also
includes the first connection and `SELECT 1, VERSION()`.

The experiment branch's generated-code instrumentation is for event ordering
only. `capture.py` stopped at three slow Starts in four suites. The comparison
binaries were built without instrumentation from the clean v0.5.0 source and
one disposable generated-code candidate. `make_candidate.py` records the exact
targeted delta and produces `guest/experimental.patch` from the pinned MariaDB
file. The script and file hashes in the report permit an independent check;
the candidate binary is not a canonical guest rebuild. The used build flags
were `GOTOOLCHAIN=go1.26.8 CGO_ENABLED=1 go build -p 1 -trimpath -buildvcs=false`.
