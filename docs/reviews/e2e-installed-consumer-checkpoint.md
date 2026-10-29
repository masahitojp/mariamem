# Owned E2E installed-consumer verification

The first candidate's Live CI40833174501 passed the owned component and actual
application step on macOS15 arm64 and Ubuntu24.04 x86_64, Python3.11/3.14.
PR head `9ca37cd28650aad653ed1cad8d0b8ed7f21b8a6b` differs from actual executed
merge source `bc7fdb49565b9a62b9686c5c31b036e59868b04d`; its parents are main
`62d54c29fed95c76ba9833c4e6174f9de803a1d6` and that PR head. Git identity and
both owned-step conclusions were checked. Existing check/integration, Django,
dump/worker and required Live gate also passed. PR #28 remains unmerged.

The next work is `scripts/e2e_installed.py`: use the same fixed applications and
case oracles from a staged checkout-external consumer, with the SDK installed
from an exact candidate wheel or private Go module ZIP. The controller rejects
wrong/missing wheel source receipts and different SDK bytes; verifies the installed
package inventory and bundled host before resource creation; removes SDK/source
runtime overrides and checks exact case counts without hidden errors/skips.
The Python example's host override is removed so it uses the default bundled
host. Application inputs/diagnostics are copied as explicit fixture inputs.

Python uses a temporary venv with inherited fixed application dependencies, then
installs the wheel without dependencies or index access. SDK imports must come
from that venv and match all wheel files. This is not a clean-machine dependency
acquisition test. Go uses the existing content-addressed private module fixture
from G1 (same bytes/cache), with GOWORK off, no replace and complete source-file
comparison. No remote tag or release is created.

Existing Live jobs run consumers on both hosts and both Python minors after
wheel construction. All raw consumer outputs, JUnit, source/module receipts and
checksums are retained under live-evidence/owned-installed-py*. Temporary consumer
workspaces/venvs are removed after receipt collection; failures remain failures
and cleanup uncertainty is recorded. Six pure boundary controls cover staging
anchors, default-host selection, environment overrides, wheel/receipt mismatch
and incomplete/failed/skipped Go case censuses.

This checkpoint adds verification only. It does not complete installed acceptance
until the new exact-source runtime results exist. Time/resource, full hook-fault
campaign and main adoption remain tracked by #18. Prior CI receipts are never
relabeled as the new controller source. Native input/SQL files are unchanged;
no new native or performance conclusion is inferred.
