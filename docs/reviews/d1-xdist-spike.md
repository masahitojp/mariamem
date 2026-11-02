# D1 pytest-xdist worker-local spike

**Recommendation: continue with productizing local worker-owned D1, while
keeping serial as the default.** The approach works in this bounded real-SDK
probe:2 and4 local workers each acquire their own host and prepared baseline,
without cross-process SDK handle sharing or engine/framework patches. Main
still rejects xdist; this experiment is not adopted support or a merge-ready PR.

The strongest objection is duplicated preparation and host cost: -n4 prepares
migrations/seed four times and retains four simultaneous hosts. It does not turn
preparation into one globally shared Snapshot. That tradeoff should be explicit
and opt-in. It does not invalidate feasibility, but speedup is unknown: the
probe uses overlap barriers, not a timing benchmark or representative large app.

## Pinned inputs and bounded change

Main base source_commit: `f09d5167172f091ccc0b20f78b817fe870d3cadf`.
Executed spike source_commit: `7a1df33f715b640ed0921b9110b644b5dcc51fc1`;
all seven final collectors recorded a clean source checkout and input hashes.
The only product-source difference is removing the numprocesses/workerinput
refusal in the Django pytest plugin on `experiment/d1-xdist`. Remaining guards,
Django's DiscoverRunner, the SDK, guest, generated code and workflows are unchanged.
The serial main test that expects numprocesses refusal remains unchanged; it is
intentionally not a success criterion for this opposite experimental behavior.

Environment: macOS27.2 arm64, Python3.11.18, Django5.2.8, pytest9.0.2,
pytest-django4.12.0, pytest-xdist3.8.0, execnet2.1.2, mysqlclient2.2.7,
Connector/C3.4.11. The authored orders model/two migrations and existing D1 raw
SQL/commit cases are reused. pytest-django's existing worker suffix fixture runs
before D1's recursive setup override; the resulting names are test_mariamem_gw0,
test_mariamem_gw1, etc. No upstream patch is needed.

The host is reused from the published0.6.0 wheel, source_commit
`b3b3b46a8807482ad3f96725af86e031fe369b01`, host SHA256
`b467baece270d6d3cb0770781695c1960de2c0d9c4bd536d6aac2c14f37c1e2a`.
Wheel hash `0c49fcd9f571851d8d37c6ec0fd089fad45609b281dc4fb0e8479819752e1519`
and embedded clean Go1.26.10 revision were checked. Go/guest inputs are unchanged
between that release and the main base. This is source-entry evidence with a
reused host, not installed-spike-wheel or new guest qualification.

## Results

| Case | Workers / scheduler | Original pytest result | Parent oracle |
| --- | --- | --- | --- |
| Healthy | 2 / load | 12 PASS | PASS |
| Healthy | 4 / load | 12 PASS | PASS |
| Reverse order | 2 / load | 12 PASS | PASS |
| Class grouping | 2 / loadscope | 12 PASS | PASS |
| Failure after real commit | 2 / load | 9 PASS,3 expected FAIL | PASS |
| Only gw0 prepare fails | 2 / load | 3 PASS,9 expected ERROR | PASS |
| Deliberately reuse changed child | 2 / load | 8 PASS,4 detected FAIL | PASS_FAILURE_DETECTED |

Each active worker prepared once, had one distinct host PID/source endpoint,
used its own worker-marker SQL row, and Forked only within its own host lineage.
The controller started no host. Preparation/body barriers observed all required
hosts alive concurrently; the4-worker case reached those boundaries in all four
workers. Both migrated schema and non-model SQL/DDL state were restored between
admitted tests. Atomic class data ran once in each worker that received that
class, not once globally. Real transactional writes were visible to independent
connections before child retirement. Captures consumed their sources.

After a committed test failed, all12 bodies still reached correct fresh starting
state. When gw0 preparation failed, it admitted zero bodies/captures while gw1
ran its assigned tests; both hosts were reaped. Removing restoration made the
real seed/DDL oracle fail; original failing results are retained, not rewritten
as successful tests. Normal finalization retired every recorded host. Cleanup
also confirmed all observed worker/controller processes had exited.

Existing serial regression: all20 manage.py/pytest D1 scenario assessments PASS,
including repeated invocation, original failures and no-DB suites. Component
checks excluded only the intentionally obsolete numprocesses-refusal parameter;
all other selected ownership/API policy cases passed:39 PASS,1 deselected.
Additional offline JUnit checks confirm the exact three PREPARED_BODY_FAILURE
messages with three independent commit observations, nine gw0 preparation
errors and four genuine empty-seed/changed-sentinel assertions in the negative
control. These are saved in failure-identities.json; no unexpected failure was
classified as the intended fault.

## Conditions before product support

- Make local xdist mode explicit and tested; retain independent per-worker
  preparation and prohibit process sharing of SDK owners. Serial stays default.
- Replace the old refusal expectation with positive worker controls while retaining
  all unrelated guards. Do not merge exploratory history wholesale.
- Cover idle/database-free workers and worker termination/restart/cleanup-debt
  behavior. This spike disables restarts and does not test hard kills, automatic
  worker count, remote gateways, every scheduler, tox combinations or xdist
  repeated inside one interpreter. Do not infer those supported.
- Run the installed entry on macOS15/Ubuntu24.04 × supported Python minors through
  the existing Release Django path. No new workflow or extra build is justified
  by this feasibility result. Existing serial receipts are not parallel receipts.

Django --parallel remains rejected and untested. Resource tuning stays separately
owned; no FD/RSS census or speedup was measured. A finite product acceptance
increment is needed before updating the public support guide; the user decides
that next implementation/adoption step.

## Reproduction, budget and preservation

The initial budget was2h active, at most30min tooling, no heavy CI. The initial
pilot was followed by the seven fixed cases above in one budget/disk-monitored
workspace run, then a manually supervised existing serial regression. No heavy
CI or runtime build was submitted. Tooling remained the small diagnostic
workload/collector, not a product framework or new measurement infrastructure.

Commands and dependencies are in [the spike README](../../benchmarks/d1-xdist/README.md).
The [evidence](d1-xdist-evidence) preserves clean-source input hashes, aggregate
and per-worker events, JUnit and original expected failure output. Worktree/home
prefixes and trailing whitespace are normalized; raw/saved hashes are retained.
Barrier coordination files and duplicate pilot data are not acceptance evidence.
Code and results are pushed on the experiment branch; recreatable venv, host
copies and completed worktree are disposed after preservation. Parent checkout's
four pre-existing tooling/development edits are preserved.
