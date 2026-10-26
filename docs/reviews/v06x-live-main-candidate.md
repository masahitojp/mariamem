# Selected Live main candidate

This branch prepares the bounded stable-endpoint API for a separate main adoption
decision. It has not been integrated, qualified or released. Fresh CI must pass
on this candidate; previous experiment receipts do not qualify the correction.

The stable base is `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Selected files come
from `a1baaad83922d9ac6ff7fe46d64db3fbfcde542f` (experiment/live-host); that ref
and [CI40349469630](https://github.com/masahitojp/mariamem/actions/runs/40349469630)
remain unchanged. The [adoption review](https://github.com/masahitojp/mariamem/blob/c718344/docs/reviews/v06x-live-host-adoption-review.md)
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
