# Host-owned public Live acceptance

This owner tests actual Snapshot.live()/Snapshot.Live, not the old Python TCP
relay. Django retains its process and endpoint with CONN_MAX_AGE=0. The authored
Go live-use variant differs from the original app only by MaxIdleConns(0), so it
retires idle physical sessions after requests. Both applications retain ordinary
SQL and browser actions. The original Go app/Fork three-process path remains a
separate control. Neither reuse route preserves SQL sessions across reset.

input-manifest.json pins the new Go variant and owner. native-input-pins.json
keeps every original native app/migration/UI file byte-identical to its reviewed
source. Native reference events in native-reference.json retain original3446b5c;
the new variant also requires fresh native MariaDB12.3.3 execution on the exact
candidate. native.py records both source and platform-specific binary identity.
Mac guest results can use the Ubuntu native observation: source identity must
match, while cross-platform binaries are deliberately different artifacts.

The numeric loopback HTTP-bind harness adjustment avoids the observed macOS
reverse-DNS startup stall. It does not change the application, SQL or readiness
timeout. Opt-in stack diagnostics remain available in child app logs.

Build Go1.26.10 executables for cmd/mariamem-host, e2e_native_control/goapp,
live_acceptance/goapp and live_acceptance/go_owner. Use a clean exact checkout;
linked worktrees may receive incorrect Go VCS identity. Install the fixed browser
requirements and Chromium with a dedicated PLAYWRIGHT_BROWSERS_PATH. Run:

```sh
python tests/live_acceptance/native.py --port NATIVE_PORT \
  --go-app build/go-live-orders --expected-source-commit FULL_SHA \
  --output build/live-native/reference
python tests/live_acceptance/run.py --host build/mariamem-host \
  --go-app build/go-orders --go-live-app build/go-live-orders \
  --go-owner build/go-owner --native-reference build/live-native/reference \
  --expected-source-commit FULL_SHA --output build/live-evidence/positive
```

Repeat into fresh outputs with --mutation skip-reset and --mutation restart-app.
Both actual defects must be detected on both public Live routes. Raw browser
suites deliberately contain one exact post-commit assertion failure; the parent
requires that signature and next-test isolation, not generic nonzero exits.
There is no silent skip or continue-on-error.

Real guest controls cover idle and transaction-held physical connections, new
handshake refusal, old-data preservation, parent Snapshot closure and explicit
recovery after a replacement failure. Fault injection is in a test-only Go probe
using the common endpoint engine and actual public Snapshot/Fork children; it is
not a product debugging command or a claimed public Python injection facility.
The probe verifies the retired original backend endpoint is closed. All normal
browser cases use the public Go/Python Live API.

installed.py builds an immutable candidate wheel, runs its default bundled host
from outside the checkout, and runs an external Go module with an exact local
candidate replacement. It is not publication or a downloaded released-module
smoke. The wheel uses current source version metadata; no version/release action
is implied. Its consumer venv and module are removed after preserving results.

The candidate workflow first obtains source-bound native reference receipts,
then both supported host OSes run canonical check/integration, new relay race
checks, both Python versions' public browser/real-defect controls, installed
wheel and external Go consumer. Receipt preservation and local workspace cleanup
complete the experiment lifecycle separately from hosted-CI execution.
