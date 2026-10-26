# Real browser guest/live comparison — local and CI results

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
| Ubuntu and Python3.14 on local candidate16eb116 | Not executed locally; later exact-candidate CI results below |

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


## Both-platform CI result on exactab085d3

[CI40304818129](https://github.com/masahitojp/mariamem/actions/runs/40304818129)
succeeds on exact source_commit
`ab085d3c432b6b1483b7b937500b775d4a3faf53`. Both jobs and all four interpreter/OS
combinations pass the bounded comparison, both actual lifecycle-defect injections
and real transaction/reset-failure controls. These receipts are new evidence for
ab085d3, not a relabeling of the original16eb116 local result.

| OS / architecture | Python | mysqlclient native library | Positive / skipped reset / restarted app |
| --- | --- | --- | --- |
| macOS15 arm64 | 3.11.9 | Connector/C3.4.9 | PASS / DETECTED / DETECTED |
| macOS15 arm64 | 3.14.7 | Connector/C3.4.9 | PASS / DETECTED / DETECTED |
| Ubuntu24.04 x86_64 | 3.11.17 | MySQL client8.0.46 | PASS / DETECTED / DETECTED |
| Ubuntu24.04 x86_64 | 3.14.8 | MySQL client8.0.46 | PASS / DETECTED / DETECTED |

The [saved receipt](v06x-e2e-guest-live-evidence/ci-40304818129/assessment.json)
contains original run/job/artifact metadata, losslessly encoded original ZIPs,
GitHub-verified archive digests and per-member/file checksums. Raw pytest XML and
lifecycle events were checked again using the exact candidate's positive assessor,
specific mutation row/PID signatures and SQL-control/cleanup observations. All12
campaigns record successful cleanup; their live controls each pass two tests.
Ordinary browser suites retain their one deliberately asserted failure.

The initial macOS16eb116 and diagnosticff1175e CI failures remain bound to their
original sources. The [diagnosis](v06x-e2e-guest-live-ci-diagnosis.md) records three
snapshots blocked in HTTPServer's reverse DNS lookup. The passing candidate uses
an explicit numeric HTTP SERVER_NAME only for its fixed127.0.0.1 child listener;
it preserves actual WSGI port/environment, application bytes, SQL and the30-second
readiness deadline. All passing Python app logs contain the harness adjustment
marker. This confirms the adjusted harness succeeds on observed hosts; it does
not establish the resolver's underlying environment defect. The original native
Ubuntu reference used its original startup behavior.

The useful E2E workflows now have bounded experimental evidence on both OSes.
The next design review concerns moving endpoint ownership/reset to the Go host
and defining the public Go/Python lifecycle API. The verified implementation is
still a Python test-only relay over existing Snapshot/Fork. Go-host live behavior,
public API adoption and productization have not been implemented or approved by
this CI result. Broader dogfood work remains as listed above.
