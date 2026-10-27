# Selected Live main candidate

This branch prepares the bounded stable-endpoint API for a separate main adoption
decision. It has not been integrated, qualified or released. Fresh CI now passes
on exact candidate 6edcd29; previous experiment receipts remain separate.

The stable base is `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Selected files come
from `a1baaad83922d9ac6ff7fe46d64db3fbfcde542f` (experiment/live-host); that ref
and [CI40349469630](https://github.com/masahitojp/mariamem/actions/runs/40349469630)
remain unchanged. The [adoption review](https://github.com/masahitojp/mariamem/blob/c71834493ad2742100e1ee96da853b237c5b4abe/docs/reviews/v06x-live-host-adoption-review.md)
contains the original F1–F3 conditions and bounded evidence.

The selection includes public Go/Python Live, the internal endpoint and control
adapters, source-publication inclusion, unit/oracle tests, native reference and
browser/installed acceptance owners, the Live workflow and guide. It excludes
all experiment review/history files and their project-status edits. Independent
Django adapter and standalone examples studies remain on their own branches.
The machine-readable [selection](v06x-live-main-selection.json) lists the original
paths and exact source identity. No exploratory commits are merged.

F1: Live E2E now selects main pushes and main pull requests, as well as this
candidate branch and manual dispatch. Paths include the SDK, all internal runtime,
commands, guest/generated inputs, scripts, tests and release inputs. It still
requires fresh native MariaDB12.3.3 reference execution for both Python versions,
then macOS arm64/Ubuntu x86_64 public Go/Python browser routes, actual defect
controls and installed consumers. A mutation-tested workflow contract detects
missing main/PR triggers, dependency paths, source binding and adapter race gates.
Branch-protection policy is not configured by this candidate.

F2: Live's private child adapters retry actual backend/log/removal disposal;
public Database.Close and Live.Close keep their original errors. A previously
closed child may reach private Close again during recovery; only confirmed
successful disposal permits publication of a new generation. Repeated endpoint
Close retries retained children without erasing its first result. Manager EOF
cleanup retains the same ownership/error behavior. The Go adapter tests inject a
lower backend shutdown error through the actual private wrapper, checking reset
recovery, close retry and stored public error. The shared-host test uses a real
nonempty log-path directory to force removal failure, then manager cleanup to
verify retry after descriptor closure. This is bounded adapter fault coverage,
not arbitrary engine or OS failure recovery.

F3: Current-source guides are linked from README and both language guides, and
explicitly exclude published v0.5.3. Historical reviews/receipts stay on the design
branch under their original identities. There are no guest, generated, dependency,
version or release-ledger changes. Caller quiescence, closed physical sessions,
sequential reset and parent Snapshot lifetime remain required. Session continuity,
automatic pool retirement, delayed-job fencing and parallel shared Live cases
remain outside this candidate.

Local verification and fresh CI results must be recorded against their exact
source after execution. A passing matrix permits a new Human main adoption
review; it is not publication approval.

## Local verification on df3e683

Exact source `df3e68393ca5734cfc73e1837013d30bb620e7d1` has
[checksum-bearing local evidence](v06x-live-main-evidence/local-df3e683/assessment.json).
Both Python versions pass 63 focused tests. Live/control/public Go race tests pass.
Three overlays restoring the old Go adapter, shared adapter and endpoint Close
are all rejected by the new tests; those deliberate test failures remain raw
failures in the archive. Full canonical check passes 22 source oracles and 1040
pytest cases, with 45 SKIPs, 76 subtests and the existing shadow_maria warning.
The initial repo-local TMPDIR attempt failed 3 unchanged benchmark-tool tests;
external-TMPDIR rerun passes without changing those tests or their validation.

Full local integration is **FAIL**, with an independently reproduced environment
blocker: local Python3.14.9/OpenSSL4.0.3 cannot import fixed Connector/Python26.7.0
because ssl.PROTOCOL_TLSv1 is absent. No ssl aliases, driver patches, exception
relaxation or new native profile were introduced. All canonical Go runtime/race
and integration groups, Python SQL/lifecycle 31 PASS/1 SKIP and Snapshot 33 checks
finish before that blocker. Routing separately passes its full control, 6 defect
oracles and 4 pytest cases on local Python3.11.17/OpenSSL3.6.5. The Python3.14
routing attempt retains its import failure (its 4 pytest cases do pass).

These are local candidate results, not a full integration PASS or both-platform
Live evidence. Fresh CI must satisfy the unchanged full canonical integration,
fixed prepared-consumer native profile and all Live/browser/native/installed
conditions. The later documentation/evidence commit does not alter executable
source from df3e683. No previous CI receipt is rebound to this candidate.

## Fresh CI on 6edcd29

[CI40417099015](https://github.com/masahitojp/mariamem/actions/runs/40417099015)
passes all four jobs on exact source_commit
`6edcd29e65d3a669d5be6520abf6be2e61fa3445`. The
[saved assessment](v06x-live-main-evidence/ci-40417099015/assessment.json) and
[receipt validator](v06x-live-main-evidence/ci-40417099015/validate.py) verify all
four original ZIP digests, API source/job binding and uncompressed member hashes,
then re-apply candidate predicates to raw XML/events. No guest was rerun to
collect this receipt; no old receipt was relabelled.

| Observed host | Python | Live/browser/defects | Installed scope |
| --- | --- | --- | --- |
| macOS arm64 | 3.11.9 / 3.14.7 | PASS both interpreters | Python3.14 wheel + external Go PASS |
| Ubuntu x86_64 | 3.11.17 / 3.14.8 | PASS both interpreters | Python3.14 wheel + external Go PASS |

Fresh native application controls pass for both Python versions on Ubuntu with
MariaDB12.3.3. Each guest host passes canonical check (1040 PASS/45 explicit SKIP/
76 subtests), full integration including the fixed prepared-consumer tripwire,
and Live/control/public Go race suites. There are 8 positive public Live routes,
16 actual lifecycle defects detected, 12 Fork control campaigns, 48 real SQL
controls and 212 focused test passes. Raw browser tests intentionally retain the
exact post-commit assertion failure; it is required by the isolation oracle.
Passing CI is not a claim that all raw subprocesses exited 0.

This supplies the fresh candidate evidence required by F1/F2; F3's selected diff
is still the main-adoption review object. The local Python3.14.9/OpenSSL4 failure
remains FAIL; passing CI establishes only its recorded environments. No main
integration, version inclusion, Qualification or release decision is made here.
The experiment/live-main-candidate ref stays fixed at 6edcd29; this documentation
branch preserves the receipt without changing that tested implementation.
