# P1 fixed exit and resource work placement

Human decision, 2026-10-30, after reviewing P1 delivery at
`e29f29f1f8ffebe93cd53e571689d83ab71fee08`.

The Human fixed P1's exit conditions and separated detailed resource work into
v0.7.x. Establishing the wire contract is the main v0.6.0 objective. This decision
supersedes earlier statements making the full resource campaign a P1 or v0.6.0
completion prerequisite. It does not declare P1 complete, waive observed defects,
change the public API, or approve main adoption, Qualification or publication.

## Fixed P1 exit

1. Preserve None/callable semantics, ignored callback return, existing fixture
   overrides and no-marker behavior. PrepareCommand retains its approved env,
   output bounds, invalid-input and worker-local cleanup-debt contracts.
2. Execute declared command/callback preparation once per worker; admit only after
   success. Verify exact schema/seed in independent children after committed
   mutations, reverse order and an ordinary failed test. Retain workers 1/2,
   four-case batches and the declared connection budgets; no new scheduler.
3. Cover invalid input, command start/exit failure, timeout, normal interruption,
   disconnect/capture failure and combined primary/cleanup errors. Preserve
   original errors, readable stage/admission/cleanup information and no dependent
   admission after preparation failure or unresolved cleanup debt.
4. Verify entry-owned child/source/baseline disposal, command-group termination,
   host reaping, connection/pool retirement and FD/temp cleanup at lifecycle
   boundaries. Preserve consumed/preserved and partial-owner failure controls.
   This is lifecycle correctness, not a process-tree peak-resource study.
5. Validate the installed-wheel entry on macOS15 arm64 and Ubuntu24.04 x86_64,
   Python3.11/3.14, with the fixed PyMySQL/SQLAlchemy application and native input
   reference. Bind receipts to executed source; existing results are reused only
   within their actual scope. Preserve the first/second-test and repeated-batch
   usability/timing evidence without adding cold-machine claims.
6. Document the public API, behavior changes, tested combinations and limits;
   reconcile these conditions against evidence, then submit one adoption review.
   Missing evidence is UNVERIFIED, never an inferred PASS.

No new completion condition is implied by difficulties in measurement tooling.
New blockers must identify a violated condition above or receive a separate scope
decision. Existing correctness failures cannot be dismissed as deferred resources.

## v0.7.x resource work

Retained baselines 1/2/3 with the 64-table diagnostic, aligned process-tree
RSS/available-memory/FD/physical-connection/allocated-temp census, detailed
resource guard/mutation campaigns, continuous monitoring and resource-model or
connection-capacity tuning belong to shared Snapshot/runtime characterization in
v0.7.x. They are not P1, other fixture-entry, or v0.6.0 release prerequisites.
The 16-session contract and entry connection budgets remain unchanged.

Keep existing code, fixed inputs and historical receipts under their original
source/scope. Deferred is not PASS. The experimental real-guest resource controls
require explicit `P1_RESOURCE_EXPERIMENT=1`; normal P1 CI does not select that
work. This opt-in preserves the controls, not authorization for a new campaign.
Cheap unit checks may still protect existing measurement helpers.

The earlier five-entry obligation, Django nonblocking exception, independent dbt
profile and existing wire exceptions are not otherwise changed by this decision.
First map existing evidence to this fixed exit; complete only concrete gaps,
then run candidate checks and request adoption review. Do not add more resource
infrastructure to close P1.
