# Issue94 bounded pipeline spike — adoption decision pending

Decision now: adopt a finite read-ahead policy for production implementation.
Recommendation: continue to productization with a1,048,581-byte pending-input
bound per physical connection, serial execution/responses, and instance abort
on overflow. The decisive evidence is28/28 existing Prisma Client/Live cases
passing at default pipelining, alongside retained ordering and failure behavior.
The strongest objection is that a valid larger burst can now trigger an abort;
this is a deliberate finite profile, not arbitrary/unbounded pipeline support.
If abort-on-overflow is unacceptable, revisit flow control before productization.

This recommends a policy and next implementation step. It does not approve
merging this experiment, release qualification or publication.

## Pinned object and scope

Runtime source_commit: `31daa96905730e63242f01fca75f7bb36bb14c88`.
Stable main base: `82f96435777079f38d01f5f2012eda3cb2329cda` (Issue95 integrated).
Issue93 is an experiment-only overlay from original commits
`d861c91584e2029dfb3953478647f6d8da45e7f6` and
`c7a0e97feb942763b4920a10f29060918ab9bcaf`, replayed asf18d49fa/913adcea.
PR102 is not merged; no main change was made by this task.

[Runtime hash](runtime.json), [validation/versions](validation.json),
[fixed plan/budgets](plan.json). Actual clean Go1.26.10 VCS stamping is in the
[Prisma matrix](prisma-matrix.json); the report commit is later and not the build.
Darwin arm64, Node24.22.1, Prisma/client/official MariaDB adapter7.10.1 and
mariadb3.5.4. Prior locked Prisma probe source is
`604a0c588f0a602bf6ea67d811b97bae2748c3ea`.
No guest/generated/VFS/SDK/API/version or upstream patch change is involved.

## Evidence against Issue94 conditions

| Prior condition | Result and evidence |
| --- | --- |
| Choose false-only versus finite pipeline support | Finite option is now feasible; Human policy adoption remains pending |
| Ordinary Prisma create/transaction acceptance | Client27 + same-process Live Reset1:28 PASS/0 FAIL, including nested create, duplicate-key handling and transaction commit/rollback/array; [CSV](results.csv) |
| Preserve disconnect/stop/timeout and independent DB | [Real TCP controls](transport.json):5 PASS for serial side effects/responses, EOF after queued data, overflow, cooperative query timeout and Close with queued input; independent root still answers SQL after each failure |
| Observe actual default-driver send order |47 header observations show PREPARE22 with EXECUTE23 already queued before the PREPARE response; compact selected headers in matrix JSON |

Complete mysqlwire/preparedproto package tests pass. New barrier controls cover
multiple frames/sequence, partial next header, EOF behind partial/full pending
input, overflow, allocation capacity, timeout reader join and invalid sequence.
Existing selected Python wire/timeout/multiclient checks:20 passed. These include
an opt-in cooperative SLEEP timeout-disposal diagnostic; this does not expand
forced-reclamation guarantees (see scripts/verify.py:132–136).

The old default-mode experiment had1/28 passing; this combined93/94/95 candidate
passes28/28. Do not attribute that entire difference to94 alone. CLI/shadow,
other driver/ORM versions, Linux, installed artifacts and timing/RSS were not
rerun or measured. This is not full upstream Prisma or generic Node support.

## Why the monitor remains bounded and observes disconnects

[wire.go:113](../../../internal/mysqlwire/wire.go#L113) reads future raw bytes
while SQL runs, with capacity capped at one maximum accepted command frame
(1MiB payload budget plus command/header). A full buffer still performs a1-byte
read: EOF aborts the guest, and an additional byte aborts with a bounded-input
error. Merely stopping reads at capacity would hide an EOF behind queued input.
The bound is logical pending bytes/capacity, not a measured whole-process RSS cap.

[wire.go:171](../../../internal/mysqlwire/wire.go#L171) retains the existing guest
context deadline and abort/join behavior. On completion it interrupts and joins
the receiver before the dispatcher can read the buffered stream. This uses the
existing [net.Conn deadline contract](https://pkg.go.dev/net#Conn), including
interrupting a blocked Read. No second command is executed concurrently.
[wire.go:48](../../../internal/mysqlwire/wire.go#L48) still validates frames and
calls the admission gate before dispatch, including buffered input.

The header observer atwire.go:157 is experiment-only, guarded by an environment
variable and records no SQL/parameter values. Its outputs are not performance
measurements, a full packet capture or global queue peak evidence.

## Gaps before production/integration, with detection coverage

| Gap | Existing detection / required next work |
| --- | --- |
| Human has not selected the overflow policy | No CI can decide this; adopt the finite limit or revisit flow control |
| Experiment trace/helper naming and missing public limit documentation | Ordinary CI does not prove compatibility wording or absence of this trace. Remove observation code, retain focused regressions and document the new limit/fatal behavior; rerun28 without instrumentation |
| Active fixture wire inventory still pins the stable source | Confirmed detector: test_current_contract_never_claims_runtime_acceptance_or_new_authorization fails with wire source drift for wire.go. Reconcile inventory to the final candidate; do not relax/delete the guard |
| Race and Ubuntu/platform execution unverified | Existing Release integration owns mysqlwire race coverage (scripts/verify.py:109–111), but the real pipeline failure probe is currently manual. Move relevant new TCP controls into the existing wire acceptance owner for both hosts, with no new job |
| Buffered input versus stop/quiescence admission deserves permanent coverage | Current read path retains Begin and real Close/Live Reset passed; existing ordinary busy/closed-parent controls do not specifically cover queued admission. Add a focused queued-admission regression during productization |
| Main lacks Issue93 | Existing prepared regressions and five zero-parameter Client cases detect omission. Integrate the reviewed prerequisite through normal protection; do not silently merge this combined experiment history |

Whole-process memory/throughput are unmeasured, not zero or a speedup claim.
No new resource campaign is proposed. No contradiction was found in the current
version-gated usage guides for stable main, which this task leaves unchanged.
No generated-source ownership or release-baseline change is required.
No existing failure oracle was removed or weakened to produce these outcomes.

## Next actions and reproduction

After policy adoption: extract the smallest production change, remove diagnostic
trace, add permanent queue/stop controls and usage wording, reconcile active wire
inventory, then run canonical daily checks and submit normal PR CI. Heavy release
qualification remains the existing workflow responsibility; no new CI jobs or
heavy CI submissions were made for this spike. Do not merge this branch wholesale.

For reproduction, check out the exact runtime SHA in a disposable workspace and
inspect it with scripts/git_identity.py. Build a clean stamped host with
`go build -trimpath -buildvcs=true`; a standalone clone was used for Go VCS
stamping. Restore the pinned prior Prisma spike into workspace temp/prisma,
run npm ci with its lock and prisma generate. Copy [prisma_matrix.py](prisma_matrix.py)
and [transport_probe.py](transport_probe.py) into workspace evidence and execute
from the source worktree with its Python SDK. They expect sibling temp/evidence,
a host attemp/mariamem-host and a fresh evidence/matrix-final directory.
[Python dependency freeze](python-requirements.txt) reconstructs the small test env.
Raw logs stay local; this report keeps only compact source/hash/CSV/JSON evidence.

The initial collector needed Python-env/log-location/output-directory repairs;
these harness failures are not counted as database outcomes. The final receipts
above come from complete fresh-directory runs against the pinned host.
