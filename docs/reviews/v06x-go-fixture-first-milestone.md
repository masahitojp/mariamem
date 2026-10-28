# Go prepared-test entry — first-milestone design direction

2026-10-28. Human scope decision, not an implemented API or completed runtime test.
Continuing scope: [dogfood discussion](v06x-dogfood-scope-draft.md).

The required promise is that each admitted test starts from the schema/seed the
user declared, including after earlier committed writes or test failure. Reuse
preparation rather than asking every test to build and clean the lifecycle.

The ideal is a human-readable failure explanation: operation/stage, confirmed
cause, useful next step, original error and honest admission/cleanup outcomes.
If richer diagnostics require disproportionate machinery, the Human permits
first finishing a thin pgmem-style helper. Before the first implementation
commit, the design decision must fix diagnostic level, concrete feasibility
rationale and remaining work if choosing basic-first. It must
not quietly redefine the prepared-state guarantee or claim ideal diagnostics.

## Minimum first-milestone result

- User registers one preparation callback using ordinary SQL/migration code.
  Its success signal, command integration and cancellation contract must be
  explicit in the API design; callback success is not automatic validation of
  application-specific business correctness.
- Helper owns startup, preparation, pool closure, disconnect waiting and capture.
  Failed preparation/capture admits no tests and attempts disposal.
- Test asks the fixture for an owned SQL handle on a fresh prepared child.
  Sequential and bounded-parallel tests start from the same declared state.
- Pool closes before child; children finish before the fixture's final cleanup.
  The helper supplies standard Go test-lifecycle integration rather than making
  users duplicate t.Cleanup/defer wiring in every test.
- Original failures remain inspectable; cleanup failures are also visible.
  A short stage prefix plus ordinary Go errors/test output is an acceptable
  first diagnostic level. No automatic root-cause engine, global error bus or
  presentation framework is required for this first milestone.

The established upstream pattern is
[pgmemtest](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/pgmemtest/pgmemtest.go):
Prepare in TestMain, then fixture.DB(t), with per-test cleanup registration.
Go's natural preparation-sharing unit here is one test-package process, not a
baseline shared between every package in go test ./.... This refines the earlier
worker-local default for Go; no cross-process service is proposed.

## Existing mechanisms and the differences to preserve

[Snapshot/Fork](../../snapshot.go) already implement immutable prepared state and
independent children. [WaitDisconnected](../../mariamem.go) already exposes the
capture prerequisite. The current [Go example](../go.md#prepare-once-fork-independent-databases)
shows user-managed preparation/pool/child/baseline cleanup. The new work is the
supplied entry and focused acceptance, not a new isolation engine.

mariamem Snapshot consumes its source on success and may consume it after
accepted capture failure. It must not inherit pgmem's assumption that the
template server remains running after capture. Cleanup must respect the actual
consumed/preserved result. Errors.Join and testing cleanup can preserve errors
without adopting upstream's ignored cleanup return values.

The root module already pins go-sql-driver/mysql1.9.3. A helper exposing *sql.DB
can use that existing driver boundary; driver/options ownership and DSN versus
owned-handle alternatives still need the concrete API proposal. Existing callers
who use Start/Snapshot/Fork directly keep their current contract.

## Finite acceptance to design before implementation

1. Preparation executes once per fixture/test-package owner. Each test alone,
   normal/reverse order and a bounded parallel batch sees exact schema/seed.
2. Test1 commits a row/schema mutation and a later child still sees the original
   schema/seed. A deliberate failing test does not contaminate subsequent tests.
3. Startup, preparation, disconnect/capture and child acquisition failures stop
   dependent test admission and preserve original error identity.
   Capture failure has separate consumed=false and consumed=true oracles:
   for preserved rejection the source must still be alive before helper cleanup;
   for accepted/consumed failure the helper must not use the source again or
   repeat destructive backend disposal. Both admit no tests and retain the
   capture error plus any cleanup error. Count actual backend teardown calls,
   snapshot backing release, pool close and temporary removal, not just Close
   invocations. Include the successful-consume branch and partial backing unwind.
   Include invalid-but-not-disposed source: Closed() alone must not skip public
   idempotent source.Close, because invalidation also reports Closed. Verify
   actual backend/temp cleanup rather than treating a state flag as disposal.
   Root TestSnapshotFailures already covers the API's flag/error propagation;
   new helper tests must cover its own owner actions under both branches.
4. Cleanup ordering is observed, including partial construction and combined
   original/cleanup failures. Tests using assertions, Fatal and cooperative
   cancellation get honest failure/cleanup results.
5. Final fixture cleanup reports failures without turning a failing suite green;
   temporary owners and children are accounted for. Hard kill, machine loss,
   noncooperative callbacks and arbitrary caller-created pools are not silently
   given stronger guarantees than the actual implementation can provide.
6. Show a real first/second-test example using only user preparation and ordinary
   test SQL, with no repeated lifecycle assembly. Record both supported host
   results under exact source identities and retain existing wire/regression
   evidence at its actual scope.
7. Apply the parent draft's three-time/resource obligations. In the first
   campaign use MaxForks1/2, pool max-open2 (preparation1), four cases and
   -parallel1/4 with -p1. Observe actual permit, connection, memory and FD
   peaks/cleanup, including the bounded retained-baseline diagnostic. A third
   acquisition at limit2 must wait/cancel without starting another guest.
   Record all fixture/process multiplication; a test-runner parallel limit
   alone is not a DB or connection budget. Fixed default2 is a proposal pending
   measured/API review, not an existing adaptive resource governor.

Core fixture correctness and original error preservation are mandatory even at
the pragmatic stopping point. If readable diagnosis is straightforward with
ordinary Go errors and testing output, implement it there rather than deferring
it automatically. Broader explanatory categories and suggested remedies may be
reported as unfinished when their cost triggers the authorized first milestone.

The [concrete API/ownership/failure proposal](v06x-go-fixture-api-design.md)
and [acceptance contract](v06x-fixture-acceptance.json) are the next review inputs.
No helper, CLI command runner, new framework adapter, runtime/guest patch,
resource scheduler or external-project execution was implemented by this design
direction. The independent Oscar input stays an optional later workload for the
agreed experience, not the milestone's definition or an execution already begun.
