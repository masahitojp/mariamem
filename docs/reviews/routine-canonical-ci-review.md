# Routine canonical candidate — Human adoption review

**Decision now: adopt the routine/text candidate into main. Recommendation: yes.**
The approved procedures/functions and bounded DEFINER scope now has matching
independent source builds, exact generated-Go reproduction and actual consumer /
isolation / failure-oracle PASS on both supported platforms. The strongest user
limitation is unchanged: definer-sensitive privilege tests can pass here while a
real grant-enforcing server rejects them. This was explicitly accepted as the
bounded contract, is stated in the public candidate guides, and is not expanded
into an authentication/authorization compatibility promise.

This review does not approve a target version, binary prepared implementation,
final Qualification or publication. Main adoption still requires the Human's
separate decision. No main integration has been performed.

## Reviewed object and primary evidence

- Tested candidate: `03184a61a63b1977a1d05ed378404f59d57cf68e`.
- Base: `de0e08a9c4248969a7522abebfdee8aea6ef9657`.
- Artifact: [canonical adoption report at the tested SHA](https://github.com/masahitojp/mariamem/blob/03184a61a63b1977a1d05ed378404f59d57cf68e/docs/reviews/routine-canonical-adoption.md).
- [CI39406398732](https://github.com/masahitojp/mariamem/actions/runs/39406398732):
  [guest118573263844](https://github.com/masahitojp/mariamem/actions/runs/39406398732/job/118573263844),
  [macOS118578460407](https://github.com/masahitojp/mariamem/actions/runs/39406398732/job/118578460407),
  [Ubuntu118578460489](https://github.com/masahitojp/mariamem/actions/runs/39406398732/job/118578460489)
  all completed successfully on that exact SHA.
- [Saved evidence index](routine-canonical-ci-evidence/files.json) records artifact
  IDs/API digests and original/stored file hashes. Home prefixes alone are scrubbed;
  the resulting stored sizes and hashes are distinguished from original text.
- [Validated receipt](routine-canonical-ci-evidence/validated.json): transferred
  guest bytes were hashed again, and the existing `generated_release.verify_build`
  guard was independently applied with each native regeneration receipt.

Evidence/ledger follow-up lives on `experiment/routine-canonical-review`, based
on the exact tested candidate. It changes documents and the source-build ledger
only: normal Go, generated provenance, guest inputs, converter inputs, tests and
workflow content remain identical to the tested SHA. Keeping a receipt branch
avoids rerunning source builds for an evidence-only update. The tested branch is
unchanged. Do not relabel CI as having tested the follow-up commit or any future
merge commit.

## Previously accepted conditions

| Condition | Judgment and evidence |
| --- | --- |
| Procedures/functions IN; packages OUT; events OUT; DEFINER bounded | Satisfied. Scope decision/public candidate guides agree. No package execution test was added. Events remain1235; actual routine/DEFINER cases passed on both OSes |
| Product-managed proc structure; no restored-schema repair | Satisfied. Runtime suite covers three incompatible restored structures, repeated failed Fork cleanup and healthy sibling survival; [Go receipts](routine-canonical-ci-evidence/ubuntu/go-routines.json) retain counters |
| Canonical source.patch and converter13 patches unchanged | Satisfied. Candidate owner diff and manifest; experimental.patch absent, build guard passed |
| Independent same-input source regeneration | Satisfied. [guest receipt](routine-canonical-ci-evidence/guest.json) has two equal observations: guest976bbc58… / linkedf58eb48f…; downloaded guest bytes match976bbc58… |
| Exact canonical generated source and source/license guards | Satisfied. Each native [regeneration](routine-canonical-ci-evidence/macos/regeneration.json) binds99 files including provenance; source/check and existing build guard passed on both platforms |
| Existing J1 failure oracle retained | Satisfied. Both OSes reproduced unprotected heap/mmap canary165→1 with controls PASS, then protected heap/mmap with and without race PASS; [six-case results](routine-canonical-ci-evidence/ubuntu/j1-results.json) and raw transcripts retained |
| Default Connector/Python26.7.0 on Python3.14 | Satisfied, no SKIP: [macOS](routine-canonical-ci-evidence/macos/connector-regression.json) CMySQLConnection; [Ubuntu](routine-canonical-ci-evidence/ubuntu/connector-regression.json) MySQLConnection |
| Normal SQL/transaction, Snapshot/Fork, isolation and cleanup | Satisfied. Both integration wrappers PASS; Python32 tests / no SKIPs and Snapshot33 checks; Go default/integration/memory traps and focused race suite PASS |
| Existing ORM consumers | Satisfied. Per OS GORM4 runs /32 cases and installed-wheel SQLAlchemy4 runs /44 cases PASS |
| No implicit binary-prepared or prototype-limit adoption | Satisfied. Real wire test still rejects COM_STMT_PREPARE; approved prepared production requirement remains separate |

Full source checks report22 early source tests plus630 passed /41 existing
opt-in/environment SKIPs per OS. Those SKIPs are not converted into PASS.
Required real-guest runtime32 cases did not skip. Bounded DEFINER covers16 Fresh
cases and the same results/definitions in two Forks on each OS; mapping counters
return to zero after the Go lifecycle/failure cases. This supports the stated
scope, not all SQL/MariaDB compatibility or general shared-memory correctness.

Linked Wasm bytes are not retained by the normal canonical builder; its digest
is recorded during each build, and both records agree with the existing canonical
linked hash. This review rehashed the downloaded final guest, not an unavailable
linked artifact. It does not invent independent linked-byte custody.

## Missing-things scan and remaining boundaries

No unmet adoption condition, ownership/inventory drift, obsolete changed-path
comment, or public-guide contradiction was found in this bounded review. The
source-build ledger's former pending state is now replaced with the actual
03184a6 two-build receipt, not duplicate copies of the earlier local observation.
The old adoption report remains a historical pre-CI checkpoint.

The remaining boundaries are explicit:

- Account/privilege equivalence, packages and events are outside the accepted
  support scope. Unit/routine PASS is not used to erase those differences.
- Binary prepared productization remains open. This result does not satisfy that
  separate one-line-switching requirement. No full dump importer is added.
- Candidate CI is not final Qualification, Product Validation, a benchmark, or
  release approval. No new speed/performance assertion is made here.
- The complete candidate workflow is branch-specific. Main's normal integration
  runs the new routine/text cases, but its Connector test is optional unless the
  required flag/dependency is supplied, and the full six-case J1 fixture is a
  candidate gate rather than an every-main-push gate. Existing whole-body binding,
  mutation tests and generated/runtime tests remain; repeated candidate coverage
  should not be claimed for every future main change. This does not invalidate
  the actual both-OS evidence for this fixed candidate.

Existing CI detects wrong source/patch identities, changed generated inventories,
wrong source overlay/build records, failed runtime/consumer oracles, and incompatible
restored proc structure. Scope wording, target-version choice and authorization
remain Human/document review concerns, not properties proved by a green badge.

## Next action

After Human approval, integrate the smallest reviewed candidate plus this
receipt/ledger follow-up. Preserve the published-release/candidate distinction.
Do not choose a release version, merge main, start Qualification or publish as
part of this CI-result review. Performance expansion, general shared-memory
investigation and prepared implementation were not redone in this review.
