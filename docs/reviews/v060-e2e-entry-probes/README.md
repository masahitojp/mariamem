# E2E adapter probes — result and next decision

Recommend continuing with the [proposed entry design](../v060-e2e-entry-design.md)
and implementing its bounded entry cores after Human approval. The two probed
mechanisms work in controlled owners: Go case leases survive parallel suspension
and Goexit; early registration makes partial app handles available for cleanup.
The strongest objection is the gap from these models to real app/Live/browser
ownership. Keep the full proposed native/actual guest/failure/resource campaign;
these probes close adapter uncertainty only and do not qualify an SDK candidate.

## Exact observation

Executed source_commit: `03b90c17f558d6ab3f9d0f376fa50db9435261fb`.
Design/base: `ca3d3937c9dcc12c536bcedf75cb5b9ad090bb6c`.
Observed macOS27.2 arm64, Go1.26.10 with race instrumentation. Python3.11 and3.14
both ran five controlled registration cases successfully; the system Python3.9
also ran them, but is not a product-support target. The Python3.9 controller
only launches probes. No mariamem host, native DB, browser or hosted CI was run.

| Probe | Observation |
| --- | --- |
| Go active lease across t.Parallel | Grouped subtest suspends while owning lease; sibling acquisition rejected before a second reset; original resumes without changed state, cleanup releases once; next case succeeds. Four healthy top-level controls repeated20 times; race detector emitted no DATA RACE |
| Go t.Fatal / runtime.Goexit path | Deliberate body failure gives expected process exit1; t.Cleanup releases once; following subtest acquires and cleans normally. Exact raw failures are the parent and intended child, with `GOEXIT_CLEANUP_OK` |
| Debt / independent owners | Cleanup debt blocks later acquisition; two independent parallel owners acquire successfully |
| Early-release mutant | Deliberately release after t.Run returns while child is suspended: exit1 with `overlap admitted before active case cleanup`, proving the probe distinguishes that unsafe design |
| Go late-registration mutant | Omit registration before readiness error: exit1 with `partial handle not stopped` |
| Go immediate partial registration | Simulated stop error retains readiness and cleanup messages and still records Live/baseline cleanup attempts |
| Python partial registration | Real temporary FD/file closed after readiness failure; original error remains; stop failure also retained; duplicate rejected without double stop; interrupt identity retained; all registered handles attempted |
| Python late-registration control | Unregistered FD remains outside registry ownership; probe observes stops=0 and explicitly disposes it afterward, keeping the probe itself leak-free |

[Assessment](evidence/assessment.json), raw logs and SHA256SUMS bind this source
and the exact input files. A preliminary run at `e247f70d8510afcbc858d0e935e51f1e2c7be4f0`
used only system Python3.9; this final source adds both supported minors and
reruns all controls. The final receipt is not relabelled as later report commits.
No cold-machine, performance, supported-host matrix or universal cleanup claim.

## Consequences and remaining controls

- Keep Go Case(t) lease release at t.Cleanup, not t.Run return. The acquired lease
  must be registered before body execution; errors and Goexit cannot bypass it.
- Register partial handles before readiness can fail. Hooks own the small gap
  before registration. Prefer simple adapters that make registration the next
  operation after allocation; do not advertise detection of unregistered work.
- These models do not implement actual Reset/drain, stage diagnostics, application
  process-group termination, cooperative cancellation/timeouts, partial Live
  creation, concurrent/reentrant Close or all error identity operations. Python
  FD disposal is real, but app processes and Go stops are controlled interfaces.
  Repeated complete-registry Close/idempotence and production app cleanup remain
  implementation controls. Python private-registry tests are not pytest adapter
  or installed-wheel acceptance.
- Retain finite acceptance for hook order, physical idle sessions, registered
  delayed jobs, partial creation, failure composition, exclusive owners, fresh
  browser contexts, native comparison and installed consumers at exact source.
- Retain first/second/repeat time/resource and retained-baseline observations;
  no part of those campaigns was replaced by these probes.

## Reproduction and storage

From a clean ordinary checkout containing these files:

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/experiment_disk.py --work-dir build/e2e-entry-probes \
  --min-free-gib 4 --budget-gib 1 --timeout 240 -- \
  python3 docs/reviews/v060-e2e-entry-probes/run.py
```

Requires installed Go1.26.10 and `python3.11` / `python3.14` on PATH; no Python or
Go module dependencies are downloaded by the probe. The runner builds only this
nested standard-library Go module. Raw expected failures must remain failures;
the controller requires their exit/status and named semantic markers. Logs were
also inspected to exclude unrelated fatal failures. Output/caches are confined
to build/e2e-entry-probes and disposable after reducing evidence. Guard budget:
1GiB owned output,4GiB free reserve,240s. Actual owned peak was below0.1GiB.

Next Human decision: approve bounded SDK implementation of this design, retaining
the acceptance conditions. The probe task authorizes neither main integration nor
release; [#18](https://github.com/masahitojp/mariamem/issues/18) remains open.
