# Human Review — v0.5.0 startup tail

**Decision now:** whether to authorize a bounded page-cleaner wakeup *experiment*
after this investigation, or defer startup-tail optimization. **I recommend
authorizing the experiment.** In the released v0.5.0 workload on one Mac,
four-parallel Fresh contained an approximately-one-second ready delay in
34/60 Go suites and 42/60 Python suites; the same fixture run serially had
7/60 and 2/60. The delayed suites took about 0.65 s more in Go and 0.84 s
more in Python by conditional median. That is a real test-suite cost worth a
focused attempt to reduce.

**Strongest objection:** the current guest's exact notification order has not
been captured, so changing a condition wait now could exchange a startup tail
for a deadlock or another correctness defect. This objection rules out a
product fix today. The proposed experiment starts by capturing that order and
stops without a repair if the suspected missed wake is not demonstrated.
Approval here is for an experiment branch, not integration, a release gate,
or an assertion that MariaDB 12.3.3 introduced the tail.

The [bounded investigation](../../benchmarks/v050-startup-tail.md) and its
[raw evidence](../../benchmarks/v050-startup-tail-evidence/) establish the
requested wait interval and frequency on macOS arm64. All 41 slow diagnostic
Go Starts placed the second inside `mysql_server_init`; a separate one-shot
stack found `buf_flush_wait` and its page-cleaner thread in an approximately
one-second timed wait. The same guest function map is pinned to the released
Wasm hash. The former 13.1.0 guest had a similar tail, so no matched-version
evidence attributes its origin or a frequency increase to 12.3.3.

If approved, keep the next experiment finite: capture signal, waiter
registration and timeout/return order in the current guest for at least three
slow Starts, or stop after 60 four-parallel suites and report the missing
evidence. Only if a specific correctable ordering is observed, prototype one
minimal guest/host change, verify SQL/commit/rollback and startup/cleanup, and
compare it against the released binary in the same balanced Go/Python workload.
Do not merge a candidate on latency alone. If the event order stays unproven,
recommend deferring the optimization with the v0.5.0 tail characterized here.

No broad MariaDB upgrade comparison, all-guest race census, or general Wasm
correctness work is proposed by this decision. The investigation changed only
an experiment branch; main and the published v0.5.0 artifacts remain unchanged.
