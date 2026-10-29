# P1 implementation checkpoint

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

Retain the exact required-host/minor CI results, then finish the P1-specific
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
2ad041c. On observed macOS27.2 arm64, canonical full check passed: source checks
31, Go unit/vet, Python1407 PASS /55 explicit SKIP /76 subtests, public-source
check5667 files. Python3.11.17/pytest7.0.0 focused gate passed89 tests.

The guarded native wheel builder passed deployment, source stamp, licensing and
archive checks. Installed-wheel P1 passed four configurations per profile on
Python3.11.17/pytest7.0.0 and Python3.14.9/pytest9.0.2: command serial, callback
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
