# G1 remaining acceptance: physical cleanup and external Go consumer

This follows the approved Go entry design and source-bound time/resource receipts.
It implements the two remaining acceptance mechanisms. Both-host completion
receipts are now confirmed at executed source cccd12c9; see the follow-up below.
Human acceptance/main adoption, Qualification and release remain separate.

## Physical ownership controls and diagnostic correction

The added root TestSnapshotPhysicalOwnership runs the real Database.Snapshot/Close
and snapshot.Owned resource paths with a controlled backend. It checks preserved
and consumed failure, success, invalid-but-not-disposed source, backing-close errno
and source-close errno. It observes real unlinked FD closure (EBADF), source temp
removal and backend teardown counts. The backend is controlled, not a claim that
every generated-engine I/O failure was reproduced. The added helper physical tests
exercise the fixture owner policy with controlled database/baseline interfaces
that own real files/directories. The existing real-guest schema/row/failing-test
and resource controls remain separate anchors.

A new regression initially failed: a capture error containing internal backing
cleanup failure still displayed cleanup=completed when the helper's source owner
closed successfully. The minimal product change now distinguishes completed
helper-owner finalization from unverified capture-internal cleanup, preserving
all original errors. Generic capture failure no longer automatically suggests
that the DB was busy. No new public method, guest hook or engine patch is added.

The test controller applies eight temporary Go build overlays, leaving checkout
bytes unchanged: omit source Close, omit partial baseline Close, bypass source
idempotence after consumption, omit partial backing release, leak permit, bypass
cap, drop original error, drop cleanup error. Every named oracle must pass on
the unmodified candidate first, then fail semantically for its own mutation.
Build failures, unrelated test failures and stale anchors cannot count as a
detection. The required gate replays raw positive/negative JSON logs and verifies
overlay hashes against the exact source, rather than trusting DETECTED labels.

## External supplied-entry consumer

The repository-authored consumer runs outside the checkout, resolves the candidate
from an exact-byte private Go module ZIP and checks the downloaded library file
inventory. It rejects replace, workspace/repository resolution, wrong module or
missing/changed helper source. GOWORK/GOENV are disabled and compiler 1.26.10 is
pinned. The source-content private version is not a public tag/release; existing
Go caches are reused and explicitly not called cold acquisition.

The real public Run/DB(t) path prepares via a separate executable migration
command using the supplied DSN. Normal and shuffled package runs verify once-per-
process preparation, prepared SQL, committed DDL/data isolation, same-test pool
reuse, bounded parallel cases and pool budget. An intentionally failing child
package must exit 1, then demonstrate a healthy prepared child and no extra helper
cleanup error. Migration command failure preserves exit 23 and stderr; canceled
preparation admits no fixture and leaves no owned named temp directory.
The consumer binary runs with GOPROXY=off after build, and no native/runtime
bundle overrides are inherited. This proves the installed candidate helper
boundary, not a published-module download or universal application compatibility.

## CI and receipts

The existing both-host Live jobs run scripts/go_fixture_completion.py after the
resource campaign, placing receipts under the same G1 artifact's completion
subdirectory. The same Live required gate validates both the resource receipt
and completion receipt for the same executed source. Missing host/control/log,
mutation escape, wrong module/source or checksum mismatch fails acceptance.
No additional required context or parallel host matrix is introduced.

Local verification (not the new both-host receipt):

| Boundary | Exact source | Confirmed result |
| --- | --- | --- |
| Full canonical check after the SDK diagnostic change | 845b8f1 | PASS: source/inclusion, Go unit/vet, 22 source Python tests plus 1244 PASS/47 explicit SKIP/76 subtests; existing shadow_maria warning; public source PASS |
| Root/helper component race gate | 845b8f1 | PASS for . and ./mariamemtest; no full-guest race claim |
| Existing four-mode resource campaign after diagnostic change | b75fb7d | PASS with the accepted guards; original source retained |
| Final completion and external consumer | 50f9817 | PASS: 14 required baseline oracles, 8 semantic defects detected, normal/shuffle public helper consumer with actual target darwin/arm64 |
| Final focused policy/receipt/module/workflow suites | 50f9817 | 185 PASS |

The later source 50f9817 changes controller/template/tests only; its production Go
bytes match 845b8f1. The final [local assessment and raw archive digest](v06x-go-fixture-completion-evidence/local-50f9817/assessment.json)
keep source 50f9817 and observed macOS 27.2 arm64 / Go 1.26.10. No old receipt is
relabelled as this source. A valid Linux receipt is explicitly tested to be
accepted for Ubuntu and rejected as a Mac substitute. Completion records bind
both actual Go fault target and the consumer binary's runtime GOOS/GOARCH.

The historical successful resource receipt at b594527 and failed attempts stay
at their original source/attempt IDs. The new candidate must obtain fresh both-
host receipts before closing G1 acceptance. No P1/EP1/EG1 or optional D1 completion
is implied. Adoption and release remain Human decisions after the evidence review.

## Both-host CI confirmed — run 40751031818

[Live 40751031818](https://github.com/masahitojp/mariamem/actions/runs/40751031818)
and required gate 123078686977 passed on attempt 1. Executed merge source
cccd12c9b586b960cfa4f71d0005316ddc1b2e89 has the same tree as PR head f58eebc.
Both resource matrices and completion validators passed on macOS 15.7.9 arm64
and Ubuntu 24.04 x86_64. Each host supplied 14 required baseline oracles, all
8 semantic defect detections and the normal/shuffled external public helper
consumer, with matching native/runtime targets and complete temporary cleanup.

The [checksum-bound receipt](v06x-go-fixture-completion-evidence/ci-40751031818/assessment.json)
includes official ZIP digests, metadata, raw archives and commit/tree identity.
The [acceptance review](v06x-go-fixture-acceptance-review.md) recommends accepting
G1 evidence under the stated fault/cold-acquisition limits. This closes the new
both-host evidence gap; Human acceptance/adoption and other required entries
remain separate. Earlier local and CI receipts retain their original sources.
