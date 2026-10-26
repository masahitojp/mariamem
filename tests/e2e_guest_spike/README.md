# Browser E2E over real mariamem

Experimental consumer source only. Python keeps one Django process, HTTP address
and TCP database endpoint while replacing the child with a fresh Snapshot Fork.
Go uses its actual public Snapshot/Fork API and a fresh app process per child.
The business applications, migrations, browser interactions and browser version
are byte-identical to native reference source3446b5c; `input-pins.json` enforces
that boundary. `native-reference.json` contains the normalized rows from verified
native CI40286173347, not a new native-server run on the guest candidate.

The relay rejects new connections during reset, waits for all existing physical
SQL sessions to close and refuses reset on a busy timeout. A failed replacement
blocks test admission until explicit recovery. This is not SQL-session continuity,
connection-pool migration, a Django test-runner adapter or a public live API.
Django uses the reference's `CONN_MAX_AGE=0`; Go retains normal pooled/prepared
connections inside each app. Native reference and guest use the same browser
checks: committed order, deliberate failure after commit, then baseline only.

## Reproduce

Use a clean standalone checkout at the exact candidate SHA (a linked worktree's
Go VCS stamp may identify its parent). Install the pinned requirements from
`tests/e2e_native_control/requirements.lock.txt`, the platform's mysqlclient
build prerequisites, and Playwright's pinned Chromium headless shell. Set
`PLAYWRIGHT_BROWSERS_PATH` to a dedicated directory before installation and runs.
Build all three binaries with Go1.26.10:

```sh
python scripts/git_identity.py inspect HEAD
go build -p 1 -trimpath -o build/mariamem-host ./cmd/mariamem-host
go build -p 1 -trimpath -o build/e2e-go-orders ./tests/e2e_native_control/goapp
go build -p 1 -trimpath -o build/e2e-go-owner ./tests/e2e_guest_spike/go_owner
python tests/e2e_guest_spike/run.py --host build/mariamem-host \
  --go-app build/e2e-go-orders --go-owner build/e2e-go-owner \
  --expected-source-commit FULL_CANDIDATE_SHA --output build/e2e-guest/positive
```

Run again into distinct fresh output directories with `--mutation skip-reset`
and `--mutation restart-app`. The parent validates exact intentional-failure
signatures, rows, process identities, child generations and full cleanup; a raw
pytest nonzero exit is not itself a successful control. Every campaign also runs
real guest transaction/busy, handshake refusal and replacement-failure controls.
The SDK is loaded from exact source, not from an installed published wheel.

The workflow runs both Python3.11/3.14 on macOS15 and Ubuntu24.04. It builds the
unchanged runtime once per OS. It is experiment CI, not main adoption or release
Qualification. Disk guards bound campaign storage/time; workspace teardown is
separate. Baseline source is consumed, each child is closed, the app/browser and
host are reaped, and the host's temporary directory must disappear.


The child harness explicitly uses numeric HTTP SERVER_NAME for the fixed
127.0.0.1 listener. Diagnostic CI40301522009 found macOS runserver blocked in
stdlib reverse DNS before readiness. This opt-in startup adjustment preserves
WSGI SERVER_PORT/environment and other bind behavior; native application files
and SQL remain byte-identical, while the old native Ubuntu startup reference did
not use the adjustment. See the CI diagnosis and its original artifact receipt.
