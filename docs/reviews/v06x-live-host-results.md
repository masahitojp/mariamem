# Go-owned Live candidate — implementation and local verification

The approved Go-host design is implemented on experiment/live-host at exact
source_commit `ca74140090d74ff118d0c902fc3bb96410573978`, based directly on stable
main `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Local public Go/Python Live,
actual browser comparison, real fault controls, canonical check, race tests and
installed consumers pass. Both-platform candidate CI and canonical runtime
integration are the next receipts; no main adoption or release is claimed.

[Candidate source](https://github.com/masahitojp/mariamem/tree/ca74140090d74ff118d0c902fc3bb96410573978)
implements the Human-approved
[design](https://github.com/masahitojp/mariamem/blob/fdca312a3b4640da09f45f7c009840eb31c28e3a/docs/reviews/v06x-live-host-design.md).
The candidate branch contains selected source against main, not the earlier
exploratory history. The old Python relay is removed from the new candidate;
required native inputs/observations and child startup diagnostics are maintained
by tests/live_acceptance. The earlier experiment ab085d3 / CI40304818129 remains
its original source and result, not verification of this implementation.

## Implemented behavior

The common Go endpoint engine owns a stable loopback listener, reserves clients
before outbound connection, bounds transport admission by backend capacity,
serializes reset/close and forwards both byte streams with half-close handling.
Reset drains all physical sessions, starts a private Fork, retires the previous
backend and atomically publishes the next generation. Busy preserves old data;
replacement failure refuses SQL until explicit recovery or Close. Cancellation
before/after commit is deterministic. Unresolved cleanup retains its owner and
error; create-cleanup failure may return a closed cleanup-only Go Live owner.

Go exposes Snapshot.Live and Live connection metadata/DSN/status/reset/close.
Python exposes Snapshot.live and Live connection_info/status/reset/close through
additive shared-host live-v1 operations. Capability refusal preserves ordinary
use with old protocol2 hosts. Control cancellation and Python abandoned/late
replies collect Live handles, and EOF/shutdown account for them. Python context
cleanup preserves the application's original exception together with a cleanup
failure. Parent Snapshot closure does not kill the current child, but prevents
later reset; callers keep the baseline open while resets are needed.

New root Go source files are explicitly included in scripts/check_public.py;
the first local full check caught their missing allowlist entries and the
candidate corrects them without broadening to arbitrary unknown files. Guest,
internal/guest, internal/generatedgo, canonical patches, release ledgers and
version metadata are unchanged. The 0.5.3 wheel is an unpublished candidate
build of current source, not a replacement published release.

## Source-bound local observations

Local application host is macOS arm64, Python3.11.17, Go1.26.10; fixed browser
and Django/mysqlclient inputs match the retained application manifest. Native
MariaDB12.3.3 runs as Linux amd64 under Docker Desktop emulation. This is not a
native macOS server or an observed Ubuntu host. The Linux acquisition helper
correctly rejects this Darwin host; the original FAIL is retained. Image,
container-image binding, native program version/architecture/hash and startup
query independently match the pinned image profile. Fresh native application
comparison on the exact candidate is a separate observed result.

| Boundary | ca74140 local result |
| --- | --- |
| Fresh native Python and Go live-app variant | PASS_NATIVE_CONTROL |
| Python public Live, one Django PID/HTTP/DB endpoint | PASS_PUBLIC_LIVE |
| Go public Live, one Go app PID/HTTP/DB endpoint | PASS_PUBLIC_LIVE |
| Original Go per-test Fork/app path | PASS control |
| Actual skipped-reset and unnecessary-app-restart defects | DETECTED on both public Live routes |
| Idle-held and transaction-held session drain, handshake refusal, old-data preservation | PASS |
| Closed parent preserves current child and refuses reset | PASS |
| Real Go common-engine injected replacement failure, admission block, recovery and retired endpoint closure | PASS; test-only fault probe, not a product hook |
| Canonical verify.py check | PASS: Go tests/vet, generated ownership,22 source guards;1028 Python passes,45 explicit skips,76 subtest passes |
| Race: internal/live, internal/control, public API | PASS on exact clean source, count1 |
| Installed candidate wheel/default bundled host | PASS_INSTALLED_PYTHON_LIVE; host reaped/temp removed |
| External Go module with exact local candidate replacement | PASS_EXTERNAL_GO_LIVE |
| Both host OSes / Python3.11+3.14 and canonical runtime integration | Await candidate CI; no local cross-platform PASS |

Normal browser suites intentionally have one exact post-commit assertion failure;
the parent requires that signature and the next test's fresh baseline. Mutations
have their exact row/PID/setup-error signatures, not generic nonzero exits.
All three final campaigns retain Go Fork control, four real SQL/lifetime/failure
controls and successful resource cleanup. Original26bc82f observations retain
their own SHA. Its initial public-source inventory failure and local Linux-host
guard failures are preserved with causes; none are relabeled PASS.

The Go reused-app variant changes only MaxIdleConns(0) from the fixed original
business app, explicitly retiring physical sessions after requests. Its fresh
native execution records source and platform-specific executable hashes. The
candidate CI repeats that source-bound native reference before running either
guest host OS. Cross-platform executable hashes are different and are not
compared as identical artifacts.

[Assessment](v06x-live-host-evidence/local-ca74140/assessment.json),
[checksums](v06x-live-host-evidence/local-ca74140/SHA256SUMS.json) and losslessly
encoded raw observations preserve both source cohorts, stdout/XML/events,
checks/race output, original acquisition limitations and immutable wheel build
metadata. Only compact knowledge is retained; rebuildable binaries/wheels,
browser, venv and Go caches were removed with the completed worktree. Cleanup
removed 4,465,917,952 bytes of owned state with no remaining cleanup debt.
Synthetic pytest Git histories and dirty fixture files were preserved in a small
archive before removal; existing project history remains in Git refs. The task
container, anonymous volume and downloaded native image were also removed.

## Remaining gate and capability boundary

The candidate workflow runs a fresh native reference on Ubuntu for both Python
versions, then macOS15 arm64 and Ubuntu24.04 x86_64 run canonical check/integration,
new relay races, both Python versions' public Live/Fork/browser/real-mutation
controls and installed Python/external Go acceptance. This is a candidate
verification operation; the Human reports its result after CI handoff.

Application requests/jobs must finish and pools must release physical sessions
before reset. Transport draining cannot identify old jobs that open fresh
connections after the next generation begins. Session/prepared-handle continuity,
automatic application-pool retirement, background workers, parallel tests sharing
one Live and performance/setup-cost claims remain outside this boundary. The
routing marker and explicit preparation settings remain unchanged. Product
adoption review follows new candidate receipts; Qualification/release remain
separate decisions.
