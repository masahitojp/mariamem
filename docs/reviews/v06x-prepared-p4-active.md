# P4 active EXECUTE exits — candidate, actual guest acceptance pending

Baseline source_commit54b9332c27c4e2db5fcc6972eee5ea1c5fbc9732 preserves the
[LONG_DATA/native metadata PASS at fba09f6](v06x-prepared-long-data-pass.md).
This next authorized P4 slice adds active-query exit/cleanup evidence. It does
not reopen guest/converter design or complete the remaining P4/P5/P6 scope.
The guest8f617762, exact binding, canonical guest/source.patch, experimental
guest patch and all13 converter patches remain unchanged.

## Finite matrix and execution witness

Each actual guest case creates a baseline from migrated/seeded DB state, two
independent Forks in the same shared host, and a later recovery Fork. The target
procedure changes a row inside an explicit transaction, acquires a named lock,
then runs bounded SLEEP(5). The observer must see the actor's CONNECTION_ID owning
that lock and still see the old row value7. Only then may the controller act.
The actor must still be pending. Missing evidence fails rather than silently
converting this into an idle-disconnect test. Polls observe a condition; no delay
is used to presume execution started. SLEEP is cooperative, finite test work;
this does not establish forced stopping of non-cooperative SQL/workers.

| Case | Native12.3.3 control | Product requirement / actual guest result |
| --- | --- | --- |
| Ordinary procedure SIGNAL |1644/45000, exact ERR packet, DB usable | Same packet; DB remains usable; statement count0. PENDING |
| Explicit Go context cancel | context.Canceled; pool open0; server cleans statement/transaction | Same driver cause/pool result; target DB unusable. PENDING |
| Go context deadline | context.DeadlineExceeded; pool open0; server cleanup | Same driver cause/pool result; target DB unusable. PENDING |
| Active TCP shutdown/EOF | Native connection/statement/transaction cleanup | Target DB unusable; other Fork/baseline survive. PENDING |
| Active reset-requested TCP close | SetLinger(0)+Close; invalid connection; pool/server cleanup | Known transport failure; target DB unusable. PENDING |
| Host query deadline | Not the same server feature; product-only | Retained deadline cause, unusable/closed, no new SQL admission. PENDING |
| Explicit DB.Close during EXECUTE | Product lifecycle; no native DB-object counterpart | Idempotent close, no new SQL admission, reader exits, isolation/cleanup. PENDING |

The [fixed native control](v06x-prepared-p4-active-evidence/native.json) passes
all5 applicable cases using the fixed Linux/arm64 MariaDB12.3.3 container on a
macOS arm64 host. It is not a macOS-native MariaDB build. For all active native
cases, Prepared_stmt_count returns0, the named lock is released, the uncommitted
update rolls back to7 and the observer remains usable. Ordinary-error control
checks unchanged value7, not a transaction rollback that never occurred.
The Go consumer uses explicit Tx.Prepare even with interpolation enabled and
checks the actual context cause. Its final native build is race-instrumented;
this instruments the consumer, not the guest's mmap/assembly accesses.

RST means an owned Go TCPConn has SetLinger(0) and Close applied after the witness;
there is no packet capture proving each kernel packet. EOF uses socket shutdown.
An initial probe incorrectly treated the driver's expected post-reset
ErrInvalidConn from cleanup as an unexpected leak. The initial failure is saved;
only that explicitly induced reset mode now accepts that known error, while
retaining cleanup errors/stderr and asserting pool connections0. Unknown cleanup
errors and a successful interrupted EXECUTE still fail. No production driver or
runtime cleanup behavior was weakened to pass it.

## Native and product dispositions are intentionally different

The existing [Go](../go.md#lifecycle-cancellation-and-errors) and
[Python](../python.md#connections-timeouts-and-failures) contracts invalidate the
**target DB** on active query timeout/cancel/disconnect. Native MariaDB retains
its server/other sessions after one client is lost. The probe asserts both,
compares stable shared outcomes (ERR packet, context/transport failure, pool
count), and records that disposition difference. It does not label two different
lifecycles as complete native wire equivalence.

For each product case, the target's private log is removed while the shared
lineage directory remains alive for its baseline/healthy sibling. The healthy
Fork must keep value7; a new Fork must execute a prepared SELECT successfully.
After **all** DB/baseline owners close, the shared directory must disappear.
A failed target cannot expose its engine statement counter; do not substitute
native count0 or sibling count0 as a measurement of that inaccessible counter.
The observed product properties are invalidation, admission refusal, completed
Close, removed private log/lineage storage and surviving independent consumers.

## Bounded control error-classification repair

Source inspection found an existing shared-control inconsistency relevant to
the host-deadline row: status wrapped the fatal deadline without an explicit
unusable classification, and replyError unconditionally changed any retained
deadline cause to timeout. Public Python docs promise unusable/closed for the
invalidated DB. A request timeout and a permanently invalidated DB are different
user recovery actions.

The candidate wraps a status failure explicitly as diagnostic unusable and
preserves that explicit code through replyError. The original context cause
remains unwrap-able. Bare request cancellation and startup deadline classification
retain timeout. No wire capability, public API or engine behavior changes.
The pure precedence rule lives in the existing diagnostic package, with a
focused Go race test for both cause types versus ordinary/startup timeouts.
Replaying the original unconditional precedence in that owner fails the test;
the fixed source is restored byte-exactly. The workflow adds internal/diagnostic
to its permanent race package set, alongside the existing three packages.
Actual host-deadline behavior still requires the new both-OS runtime row.

## Local evidence and next gate

The fixed native5-case capture PASS and focused probe/reference controls PASS
are separate from actual guest acceptance. Unit mutation controls reject wrong
execution witnesses, rollback/count/context/pool/ERR packets, wrong DB disposition,
new admission, loss of siblings/baseline and leaked lineage storage. Their
synthetic product records only test the oracle; they are not measured guest PASS.
The canonical source inventory check concerns the unchanged old canonical runtime.
Exact input/toolchain/binary identities and final local test outcomes are stored
in the evidence receipt. The diagnostic Go race suite PASS is the new owner check. A broader local
control-package attempt was interrupted during compilation of unchanged
canonical generated code and is SKIP, not PASS. The exact endpoint/status wiring
is checked by the mandatory both-OS active guest cases; no runtime gate was
removed. Full new-guest execution is not claimed locally.

CI on the next prepared-product candidate must run source/units, formal new-guest
installation/compilation, existing binding20 mutations, P1/all72 P2/all14 P3,
first7 P4 lifetime cases, all25 LONG_DATA cases, then all7 active-exit cases with
the fixed native control. No guard/oracle or prior matrix row is removed.
Stop after submitting the exact candidate. Main adoption, target version,
Qualification and release are separate decisions.

P4 still has the remaining failure/resource matrix after this active-exit slice.
P5 real consumer acceptance and P6 canonical/reproduction/J1/provenance/guards
remain unfinished. Do not infer full P4 or production readiness from this slice.
