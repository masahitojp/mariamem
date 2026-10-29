# P1 implementation checkpoint

Local SDK/entry checkpoint source: e4b470034d56b50770452ec816e8f88fa837deb5, based on main
2ad041c. The final local results below supersede earlier candidate observations
without relabelling them. Required-host implementation and native-control CI are
confirmed below, with allocated-counter feasibility at executed source81cf7a4.
The complete P1 time/resource campaign remains pending; the later local three-time
source2fa14975 is a separate source-SDK checkpoint.

Implementation follows the conditional Human approval in decision commit
746ea5fb6306bb122659917681a2554a6a292e77, before any P1 product/helper code.
Reviewed proposal source: de860c4fc553907d237ad3a046ca6a6780ce0bb4.
This is an implementation checkpoint, not P1-complete or main-adoption evidence.

## Conditional approval mapped to the candidate

- PrepareCommand is a new public immutable declaration; None and callable,
  including ignored callback results, retain their existing meanings. Unknown
  values raise UsageError naming all three accepted inputs.
- env overlays a parent copy at execution. Descriptor argv/env are copied at
  declaration. PATH survives; actual connection JSON replaces an inherited
  reserved variable. Descriptor override of that key is rejected. No parent
  environment/cwd mutation, shell interpolation or automatic preparation routing.
- stdout/stderr are drained while retaining trailing 16 KiB per stream. Success,
  exit error, timeout and interrupt have truncation flags and dropped-byte counts.
  Error previews are limited to 2048 bytes per stream and labeled application
  output. Complete transcripts are not retained.
- A command owns its process group. Timeout/interrupt attempt bounded TERM then
  KILL and reaping; absent group and closed streams are required for confirmed
  cleanup. Temporary PermissionError queries are retried within that budget,
  never treated as absence. Persistent refusal retains errno and unconfirmed
  cleanup with the original operation error. Hard kill, escaped daemons and
  noncooperative Python callbacks have no new guarantee.
- Child/routing cleanup debt stops subsequent dependent admission in that worker;
  ordinary assertions with clean finalization continue. Remaining owner finalizers
  are attempted. The narrow preparation hook observes original exceptions;
  pytest setup/call/teardown remain authoritative. xdist sends bounded owner
  state to the parent for final summary, without sending command output/errors.
- docs/python.md documents the class and behavior change. The same change is in
  docs/release-notes/unreleased.md. Contract tests reject removal of either notice.
  No version, release ledger, guest/generated or wire change is included.
- check_fixture_design.py now requires scope_status
  APPROVED_G1_P1_WITH_DJANGO_NONBLOCKING and authorized_implementation_entries
  ['G1', 'P1']. It pins P1's reviewed design, decision commit, decision bytes and
  conditional definitions; negative mutations reject weakened approval. G1's
  original reviewed_design_commit remains unchanged.

## Verification owners

- tests/test_prepare_command.py uses real executables/output/process groups:
  overlay/copy/reserved target, literal argv/cwd, invalid inputs, multi-MiB output,
  exit 23, timeout/partial output, interrupt identity, TERM-to-KILL, combined
  cleanup error, transient/persistent permission denial and no false completion.
- tests/test_p1_pytest_entry.py uses real pytest and controlled owner interfaces,
  including real FD controls, original plus cleanup errors, no next child after
  debt, normal failure followed by a healthy child, routing teardown ordering,
  ignored callback-return descriptors, unknown inputs and xdist's other-worker
  independence/final summary. Controlled owners are not actual guest evidence.
- tests/test_p1_runtime.py runs the actual guest, public supplied fixtures and
  application routing. It reuses the authored users/addresses migrations and seed
  from tests/preparation_migration_acceptance, via a separate command or callback.
  It covers committed schema/data isolation, reverse order, four-case batch,
  two workers, ordinary failing test followed by independent children, original
  endpoint non-contact and actual final host/directory cleanup. The only app
  variant fixes its pool budget to max-open 2/max-idle 1. Migration SQL is not
  normalized or rewritten; this is not a new upstream-application claim.
- Existing Live jobs run new controls on both Python minors and required hosts;
  runtime checks reject a missing/wrong/dirty source stamp before source startup.
  Installed-wheel mode checks every Python module byte and rejects source fallback;
  CI isolates Python3.11/pytest7.0.0 and Python3.14/pytest9.0.2 consumers.
  No new required context is added.

## Still required before full P1 acceptance

The exact required-host/minor implementation CI results are retained below.
Finish the P1-specific
source-bound first/second-test and repeated-batch measurement campaign, retained
baselines 1/2/3, aligned RSS/available memory/FD/physical connection/temp counters
and actual guard/mutation controls. Retain installed-wheel consumer results for
this new public entry at their exact source and required hosts. Existing G1 resources or local fake-owner reports are not
substitutes. Existing native migration references retain their original source
and scope; a changed input/SQL needs its own fresh native control.

No setup-cost/cold-machine, complete P1/EP1/EG1, difficult-Django completion,
main adoption, Qualification or release claim is made. CI submission is an
implementation checkpoint, not a reduction of the agreed acceptance scope.

## Main update before CI submission

Latest main 2ad041c is merged, including its approved TEXT/worker-failure
repair, detection net and CI improvements. The [wire source reconciliation](v06x-p1-wire-reconciliation.md)
updates only the active file/source baseline; command/capability scope and
P1 approval definitions are unchanged. Earlier local receipts stay source-bound.
The merged candidate needs fresh canonical and installed-consumer verification.

Fresh native control for the command/pool variant remains a P1 full-acceptance
condition alongside the resource/time campaign. Reusing authored migrations
is not a claim that the new command path already has a fresh native receipt.

## Local verification at bcc2938

Exact source_commit `bcc29380f8f012404f44d557bea5586de6b3bb92` includes main
2ad041c. On observed macOS 27.2 arm64, canonical full check passed: source checks
31, Go unit/vet, Python1407 PASS /55 explicit SKIP /76 subtests, public-source
check5667 files. Python 3.11.17/pytest 7.0.0 focused gate passed89 tests.

The guarded native wheel builder passed deployment, source stamp, licensing and
archive checks. Installed-wheel P1 passed four configurations per profile on
Python 3.11.17/pytest 7.0.0 and Python 3.14.9/pytest 9.0.2: command serial, callback
reverse order, command two-worker batch and an ordinary failing test followed
by independent children. Each configuration ran six child cases. Each loaded
Python module matches source bytes; native execution uses the wheel's bundled
host by default, with its actual source stamp/hash verified. All observed final
hosts were reaped and session directories removed.

Negative preflight controls reject an unstamped/wrong-source host and a source-
tree import under installed mode before creating the consumer/source. The
[raw logs, wheel metadata and checksum-bound assessment](v06x-python-fixture-implementation-evidence/local-bcc2938/assessment.json)
retain this exact source. CI preserves the analogous wheel metadata as
build/live-evidence/p1-wheel.json and emits runtime summaries per minor.

The earlier bdda0cf/a81f91d local outcomes preceded the new main and are not
relabelled as this source. An initial diagnostic run used an unstamped worktree
host before admission verification and failed on missing Alembic; it is not
acceptance evidence. Final runs used a clean ordinary Git checkout, actual VCS
stamp verification and isolated fixed dependencies. A local sandbox signal
denial and a distinct dying-group query race were separated; the latter has
bounded retry plus persistent-denial/no-false-completion regression controls.

These are functional/cleanup observations, not the three-time/resource campaign
or required-host acceptance. Profiles overlapped, Go caches existed, acquisition
is not a clean-machine measurement. No P1 complete or main adoption is claimed.

## Expected-failure admission strengthened after the local checkpoint

The runtime controller now requires exact JUnit totals for every configuration:
six child tests, one assertion failure only in the deliberate-failure variant,
zero cleanup/setup errors and zero skips. This prevents an expected nonzero exit
from masking an additional final source/baseline teardown error even if its
physical owners happened to close. A real-pytest six-child control accepts the
ordinary assertion case and rejects the same case plus final source cleanup
failure. Its source/logs are kept separate from the earlier bcc2938 observations.

## Interrupt preservation through finalization

A real-process regression exposed automatic grouping of an interrupt arriving
only in output finalization. The runner now retains the original control
exception and bounded partial output with unconfirmed cleanup. If interruption
arrives while handling an ordinary operation failure, it remains the raised
control exception and retains that operation as its cause; a primary interrupt
is not replaced by an ordinary cleanup error. The same rule applies to owned
contexts. Dedicated tests cover finalizer-only interrupt and ordinary failure
plus cleanup interrupt, alongside the existing execution-time interrupt tests.
These are new candidate changes, not a relabel of the earlier bcc2938 receipt.

## Optional exception annotations cannot replace callback failures

Annotations/cleanup attributes are best-effort. The entry records stop/debt state
before enrichment and uses a final summary with next action when diagnostic
attributes are read-only. Cleanup falls back to explicit cause chaining if it
cannot attach cleanup_errors. Class-based private contexts avoid introducing an
extra contextlib traceback assignment. Direct read-only exception identity/cause
and a real-pytest callback restricting diagnostic metadata are regression controls.

A separate historical-fixture diagnostic confirms that fully frozen traceback
attributes already fail inside pytest's own contextlib capture path at de860c4.
That framework behavior is not patched or claimed fixed here; it is distinct
from P1 replacing the original failure while adding optional notes. No failing
required profile or existing oracle was relaxed to support this distinction.

## Final local candidate — e4b4700

- Canonical full check: PASS, source checks 31, Go unit/vet, Python 1413 PASS /55
  explicit SKIP /76 subtests; public-source check 5670 files.
- Python 3.11.17/pytest 7.0.0 focused gate: 95 PASS, including interrupt priority,
  read-only diagnostic metadata, strict expected-failure counts and other-worker
  independence.
- Python 3.11.17/pytest 7.0.0 and Python 3.14.9/pytest 9.0.2 installed wheel: four
  configurations each, six child cases each, JUnit errors/skips 0 and exactly one
  intended assertion only in the failure variant. Native host is bundled/default,
  not an external override; its actual VCS stamp/hash and all Python module bytes
  match this source. Every observed final host/session directory was retired.
- Unstamped host and source-tree fallback controls are rejected before consumer
  creation. Separate final-source raw logs preserve both expected negative exits.

The [final checksum-bound assessment and raw archive](v06x-python-fixture-implementation-evidence/local-e4b4700/assessment.json)
include full canonical output, both runtime/JUnit/event logs, wheel metadata,
host buildinfo, lower-bound tests and preflight refusals. The fully-frozen
traceback diagnostic is labeled historical-fixture/fake-owner characterization,
not old/new SDK acceptance. No initial unverified/failed run is a PASS receipt.

Only observed macOS 27.2 arm64 is locally proven. Both profile runs overlapped,
Go caches were warm and package acquisition was not a clean-machine test.
macOS15/Ubuntu CI, fresh native command/pool reference and the complete P1
three-time/retained-baseline/resource/guard/mutation campaign remain required.
No whole P1/main adoption/Qualification/release claim is made.

## Required-host implementation CI — run 40811260983

[Live run 40811260983](https://github.com/masahitojp/mariamem/actions/runs/40811260983)
attempt 1 and required gate 123256119608 succeeded. PR head bbfb6346 and executed
merge source_commit `3f8395b42ffd9fdeea3fc1d1bb30fe19244c8838` have identical trees.
The [saved assessment, metadata and checksum-bound raw P1 files](v06x-python-fixture-implementation-evidence/ci-40811260983/assessment.json)
verify both original GitHub ZIP digests before selecting P1 members verbatim.
macOS15 arm64 and Ubuntu24.04 x86_64 each passed Python3.11/pytest7.0.0 and
Python3.14/pytest9.0.2: focused95 PASS per cell; four installed-wheel runtime
configurations per cell. Each configuration has six child tests, zero extra
setup/cleanup errors or skips, the single intended assertion only where declared,
exact source/input binding and confirmed final host/directory cleanup.

Development [40811260990](https://github.com/masahitojp/mariamem/actions/runs/40811260990),
Django [40811260711](https://github.com/masahitojp/mariamem/actions/runs/40811260711)
and dump [40811260816](https://github.com/masahitojp/mariamem/actions/runs/40811260816)
also succeeded. Dump's duplicate development jobs were intentionally skipped;
the required Development check/integration ran successfully. These results do
not establish the P1-specific native command/pool reference or resource campaign.

## Next acceptance increment — P1 native control, execution pending

This section records the pre-execution increment; source5a9f317's later success
is recorded below without relabelling the earlier receipt.

`tests/fixture_entry_acceptance/native.py` adds a test-only control on the existing
disposable, digest-pinned MariaDB12.3.3 service. Both native Python jobs first run
the existing acquisition guard, then execute the same p1_migrate.py as a
PrepareCommand and as a callback. It refuses an existing app schema, checks
schema/seed/revision/constraints, FK1452 and subsequent SELECT, and observes two
distinct simultaneous physical connections under max-open2/max-idle1. Each owned
schema is removed; source, inputs, packages, observed table engine/collation and
final schema count are recorded. Preparation uses the unchanged pool1 input.
This tests the command component and authored SQL, not native Snapshot/Fork or
pytest ownership. Private command execution is test-only, not another public API.

Installed-wheel guest acceptance now requires the same-source/same-Python native
receipt and exact preparation input hashes before starting a source. Missing,
stale, failed, partial, wrong-data or unclean native references are rejected by
the gate. The existing Live artifact carries these new receipts; no new job,
required context, framework dependency or product change is introduced.
Actual execution is pending the next CI; run40811260983 predates this increment
and is not relabelled. P1 time/resource/retention/guard acceptance and separate
main adoption/Qualification/release remain unfinished.

### Main refresh after the native-control increment

While the implementation CI was running, G1 PR6 landed on main62d54c29. The
candidate incorporates that main update. Its active contract now uses main's
wire inventory/source437d74d and preserves the historical cc00ccd pin; all four
wire boundary files are byte-identical to the prior 2ad041c comparison. P1's
separate pre-code approval and G1/P1 authorization remain unchanged. The earlier
3f8395b CI receipt keeps its original source and is not a receipt for this merge
or the native-control increment. No G1 adoption decision is reopened.

## Native plus required-host correctness confirmed — run40829538394

[Live40829538394](https://github.com/masahitojp/mariamem/actions/runs/40829538394)
attempt1 and required gate123316058837 succeeded. Executed source_commit
`5a9f3172639f626b82a6e303a6de4942e0c42ace` and PR headde28c547 have identical
trees. The [saved receipt and raw archive](v06x-python-fixture-implementation-evidence/ci-40829538394/assessment.json)
verify all four original GitHub artifact ZIP digests, then retain host P1 members
and complete native references verbatim with inner/outer checksums.

Both native Python cells report PASS_P1_NATIVE_INPUT for command and callback,
matching schema/seed/revision/constraints, FK1452/recovery, distinct simultaneous
pool connections2, and schema_count_after0. Both macOS15 arm64 and Ubuntu24.04
x86_64 then pass Python3.11/pytest7.0.0 and Python3.14/pytest9.0.2: focused113 PASS
each; four installed-wheel configurations each; exact six-child JUnit counts and
confirmed host/temp cleanup. Their native-reference admission checks ran before
source startup. Development40829538446, Django40829538416 and dump40829538419 also
succeeded. These are correctness receipts, not the resource/time campaign.

## Resource-counter feasibility increment — required-host results pending

This section preserves the pre-execution plan. The later sourcebd3ab3f result is
recorded below; it does not retroactively qualify an earlier candidate.

G1 measures its own Go descriptors via fstat. P1's separate host process requires
an independently checked observer before the full measurement campaign. The
test-only resource_probe.py and test_p1_resource_probe.py use lsof's NUL-delimited
fields for explicit owned PIDs. They count numeric descriptors and deduplicate
FD-backed unlinked regular files by device/inode. Missing process/type/file
counters, truncated framing, inconsistent sizes and lsof warnings are errors,
never zero-valued successful observations. The tool hash, observation window,
source/dirty state, code hashes and raw output are retained.

A real child holds two descriptors to one unlinked1MiB file. The control requires
FD+2, bytes+1MiB only once, and baseline counters restored after both close; it
also requires child reaping. The new probe runs in both existing host/minor P1
unit cells and writes p1-resource-py*/ artifacts. lsof is required, installed on
Linux if absent; missing tooling does not silently skip the control. Local
observed macOS27.2 passed the probe on both Python boundaries; the full affected
unit/design/workflow set passed192 per minor. Required-host probe execution is
pending the next CI, not proved by run40829538394.

The byte counter is **logical size of FD-backed unlinked files**, not allocated
blocks, mmap-only storage or physical memory. This is feasibility evidence only:
no P1 workload, process-tree FD guarantee, RSS/available-memory sampling, retention
1/2/3, physical SQL-connection counts, first/second/repeated times or admission
guard acceptance follows. Those remain required in the full P1 campaign. These
probe counts must not be substituted for G1's allocated-block disk limit without
a separately justified accounting rule. No product/guest/API change is made.

## FD/logical counter and G1 correction CI confirmed — run40846147295

[Live40846147295](https://github.com/masahitojp/mariamem/actions/runs/40846147295)
attempt1 and required gate123375744109 passed. Executed source_commit
`bd3ab3f717ce5831e084dc782e8e7cb770e192ad` has the same tree as head e5350bc3.
The [saved assessment, metadata and raw files](v06x-python-fixture-implementation-evidence/ci-40846147295/assessment.json)
retain four digest-verified original ZIP identities and checksum-bound selected
P1/G1 and complete native data. G1's full validator was replayed against the clean
exact source on both hosts: all four modes and the resource/admission guards pass.
Ubuntu has two terminal zero-RSS observations whose exits were actually confirmed
by the new bounded wait. They are not included as live RSS measurements. The
original run40843725436 stays FAIL under its original source.

All four host/minor P1 cells pass125 focused tests, four installed-wheel cases
and the original FD/logical-size probe. Probe source/dirty/code hashes and raw
lsof records were checked. Both native command/callback cells also pass with
schema_count_after0. Development40846147290, Django40846147421 and dump40846147203
passed. This closes the required-host FD/logical-counter feasibility increment,
not the allocated-block observer or full P1 measurement campaign.

## Allocation observer increment — required-host execution pending

This section records its pre-execution state; the later source81cf7a4 result is
retained below without relabelling earlier local/CI receipts.

The test-only resource_probe.py now has an independent allocated-block observer:
Linux stats /proc/PID/fd; Darwin uses a small SDK-built fd_allocated_darwin.c tool
with proc_pidinfo/PROC_PIDLISTFDS and proc_pidfdinfo/PROC_PIDFDVNODEINFO. The SDK
vst_blocks field is compared with the child's independent fstat st_blocks; both
use512-byte units. This reads the existing process without adding a host command,
product dependency, SDK API, guest patch or instrumented mariamem binary.

The census is bounded to4096 FDs per explicit owned PID, with missing/partial/
changing data rejected. Device/inode deduplication prevents two descriptors from
doubling one file's bytes. Darwin builds require a checked clean commit, fixed
compiler flags and a30s timeout; observation has a10s timeout. Source/header/tool
and binary hashes, compiler/SDK versions and raw stat observations are retained.
The existing P1 probe test owner runs it on both hosts/minors; the workflow and
Go cache key are unchanged by this increment.

The first4MiB sparse candidate at d52fe0e2 allocated4MiB on the observed filesystem,
so its distinction oracle correctly failed. A fixed one-byte file instead reports
4096 allocated bytes locally. The final control requires allocation greater than
logical size, FD+2, only one allocation contribution despite dup, and restored
baseline after both descriptors close. No stat result or assertion is normalized
to make a control pass.

Clean source_commit `1fc771e868f71edb3ad3b38eb5349a77bbfd95e2` passed258 focused
tests on each Python boundary, including native compilation and the actual child
comparison on observed macOS27.2 arm64. The [local assessment and raw stat data](v06x-python-fixture-implementation-evidence/local-1fc771e8/assessment.json)
retain that source and the preliminary failed control separately. Required-host
execution is pending the next CI; run40846147295 predates this new code.

This remains counter feasibility for FD-backed regular files. It is not mmap-only
storage, an atomic process-tree census, RSS/available-memory observation, P1
baseline retention1/2/3, physical SQL connection counts, first/second/repeated
timing or admission-guard acceptance. The full P1 campaign remains required.

## Required-host allocation counter confirmed — run40856524755

[Live40856524755](https://github.com/masahitojp/mariamem/actions/runs/40856524755)
attempt1 and required gate123395867624 passed. Executed source_commit
`81cf7a4cbf35061cd91f6eed68e4491003a9d577` has the same tree as head30c9e2a0.
The [saved assessment, metadata and raw data](v06x-python-fixture-implementation-evidence/ci-40856524755/assessment.json)
retain four verified GitHub ZIP digests and inner/outer checksums. Four host/minor
cells each pass135 focused tests, four installed-wheel configurations and the
allocated-block control. Each control observes its own child's fstat allocation,
deduplicates the two FDs and restores baseline after close, with source/code/build
provenance. Both native references, Development40856524809, Django40856524889 and
dump40856524965 also passed. These are allocated-counter/correctness receipts,
not the full P1 time/resource campaign.

## Three-time checkpoint — local source2fa14975, required-host execution pending

The [orchestration plan](v06x-p1-time-campaign-plan.json) was fixed at c49336c7
before implementation measurements. `tests/fixture_entry_acceptance/time_campaign.py`
uses the existing authored application and PrepareCommand through the supplied
pytest fixtures, marker and routing. No migration SQL, native input or product
code changes. The existing installed-wheel CI owner automatically collects the
new `test_three_time_campaign` alongside its four prior correctness configurations;
the workflow and Go cache key remain unchanged.

- First setup writes the provided sample files and executes one committing test.
- The second edit adds only test_second.py and executes both tests. Before/after
  hashes reject changes to the existing application, first test, fixture or route
  configuration. The sample adds five lines and repeats no lifecycle wiring.
- Repeated execution runs workers1/2, four cases per batch, one warmup and three
  observed batches. Loadgroup slots and bounded filesystem barriers keep batches
  separate and prove overlapping SQL holds without sleep-based overlap oracles.

The observer records worker-local start/prepare/disconnect/capture/admission/case/
cleanup phases. Exact JUnit, per-worker preparation/child/owner census, distinct
host PIDs, original-endpoint non-contact, host reaping and directory cleanup are
required. Each worker has at most one child; held SQL connections are observed via
the actual child's status, reaching2/4 for workers1/2. Held connections are a
measured subset, not a census of every idle/transient physical connection.
Process execution is bounded to180s; peer barriers20s. Case phases include SQL,
assertions and test coordination; the final batch includes pytest scope teardown.
Nested/concurrent phases are retained separately and never summed as speedups.

Clean source_commit `2fa14975f7f54874f4198faf2066dca268485b8f` passed281 focused
tests per Python minor. Both actual-guest profiles then pass all five outer tests:
four existing configurations and the time checkpoint's four invocations
(1 first +2 second +16 serial repeat +16 parallel repeat child cases).
The [local assessment and raw evidence](v06x-python-fixture-implementation-evidence/local-2fa14975/assessment.json)
retain the exact stamped Go1.26.10 host, input/code hashes, raw JUnit, owner/time
JSONL and stdout/stderr. Earlier37db measurements retain their own source.

This local profile uses the source SDK on observed macOS27.2 arm64. The two Python
profiles ran sequentially. Existing package/toolchain/page caches were not reset;
acquisition and human authoring duration are unmeasured. First/second totals
include the declared file steps and pytest execution, not verification/provisioning
outside the checkpoint. It is not cold-machine cost or a Python-version speed
comparison. Same-source installed-wheel time data on macOS15/Ubuntu remains
pending the next CI. Full aligned RSS/available-memory/FD/allocated-temp and
physical-connection observations, retained baselines1/2/3 and actual finite
pre-admission resource STOP/mutations remain required before P1 acceptance.
