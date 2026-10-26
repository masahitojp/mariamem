# Real browser guest/live comparison — local result and CI handoff

The bounded local comparison passes on exact candidate
`16eb116d8056581364f3a609f9b97f885796e040`, branch
`experiment/e2e-guest-live`. It demonstrates the first useful E2E workflows:
Python keeps the application process and its HTTP/database endpoints while each
browser test gets the prepared initial database; Go uses existing public
Snapshot/Fork with a separate app per test. This is experimental consumer code,
not a new public live API or main adoption.

The Human authorized continuing from the native reference and implementing live
where the E2E use requires it. The candidate adds a test-only TCP relay around
existing Python Snapshot/Fork and a Go public-API owner for the same business
apps. Product SDK/runtime, guest/generated code and release inputs are unchanged
from main `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Native app/migration/UI files
are byte-identical to reference source3446b5c, enforced by a hash manifest.

## Observed result

Local platform is macOS arm64, Python3.11.17, Go1.26.10,
Django5.2.8/mysqlclient2.2.7 (Connector/C3.4.11), Playwright1.56.0 and actual
Chromium141.0.7390.37. The source SDK and all three source-stamped Go binaries
identify the exact candidate. This is not installed-wheel acceptance.

| Control | Result |
| --- | --- |
| Django migrations, seed, consuming Snapshot | PASS |
| Python same app PID, HTTP address and DB port; three fresh children | PASS |
| Go public Snapshot/Fork, three children and app PIDs | PASS |
| UI save/commit, intentional failure after commit, next baseline-only test | PASS, both apps |
| Reset while a real transaction remains connected | Busy refusal; original generation retained |
| New handshake during drain or failed replacement | Refused |
| Replacement failure, original cause and explicit recovery | PASS |
| Actual skipped-reset defect | DETECTED by leaked committed row |
| Actual unnecessary app-restart defect | DETECTED by PID/lifecycle evidence |
| Browser/app/relay/child/host cleanup | PASS; no forced relay clients, host directories removed |
| Focused tests including evidence-corruption negatives | 26 PASS |
| Ubuntu and Python3.14 on guest candidate | Awaiting experiment CI; no local PASS claimed |

Each ordinary browser invocation deliberately produces two passes and one
specified assertion failure. The parent checks that exact failure, the committed
rows, the next clean baseline and teardown; it does not equate any nonzero exit
with success. Real SQL busy/failure controls pass separately. Each of the three
campaigns checks both apps and those controls. Initial source710ab35 also passed;
its raw evidence retains its own identity rather than being relabeled.

[Assessment](v06x-e2e-guest-live-evidence/assessment.json),
[checksums](v06x-e2e-guest-live-evidence/SHA256SUMS.json) and the losslessly encoded
raw archive retain result JSON, pytest XML, app diagnostics and lifecycle events.
The native comparator is the previously verified Ubuntu
[CI40286173347](https://github.com/masahitojp/mariamem/actions/runs/40286173347)
observation on3446b5c, with original artifact digest recorded. It was not rerun as
native MariaDB on this new guest candidate. This comparison establishes matched
application results, not matched-platform timing.

## Boundary and next evidence

The application must release physical SQL connections before reset. Django uses
the unchanged reference setting `CONN_MAX_AGE=0`. Go retains ordinary pooled and
prepared connections for each app lifetime, then closes the app before the child.
The relay does not preserve physical SQL sessions, replay protocol, move active
transactions or invalidate application caches. A replacement error blocks the
next test; it does not silently use a possibly modified old database.

The experiment workflow runs macOS15 and Ubuntu24.04, each with Python3.11/3.14;
it builds the unchanged runtime once per OS and repeats the positive and actual
mutation campaigns. Existing native receipts remain bound to their original
source. Once those candidate receipts are available, review the useful public
shape of live/fixtures and any remaining lifecycle hazards. Productization,
main integration, version inclusion and release require their own decisions.
General Django runners, background workers and parallel-worker acceptance remain
later dogfood work. No performance/setup-cost claim is made.

Reproduction and the bounded implementation contract are retained on the exact
[candidate](https://github.com/masahitojp/mariamem/tree/16eb116d8056581364f3a609f9b97f885796e040/tests/e2e_guest_spike).

The disposable worktree, standalone build checkout, binaries, browser, venv and
Go caches were removed after evidence preservation (about2.04GiB). The cleanup
helper reports no retained large paths or cleanup debt in this experiment; the
exact candidate branch and compact receipts remain.
