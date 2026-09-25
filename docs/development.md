# Building and testing

The repository is self-contained: no files from an earlier investigation workspace
are required. Downloaded inputs and all build products live under ignored `build/`.

## Requirements

- macOS arm64 for the initial native/AOT wheel (built and tested on macOS 27).
- Go 1.26.8; Python 3.9+ with pip, setuptools >=58 and wheel.
- Docker with Linux arm64 support for the MariaDB guest build.
- `patch`, a network connection for first-time downloads, and sufficient disk/RAM.

The toolchain versions and source archive hashes are in
[`release/inputs.lock.json`](../release/inputs.lock.json).
Docker/compiler requirements apply to developers; they are not user dependencies.

## Guest

```sh
python3 scripts/prepare_guest.py
docker build --platform linux/arm64 -t mariamem-wasix-build:0.4.7 guest
python3 scripts/build_guest.py
```

Preparation downloads and verifies the pinned source archives, applies
`guest/source.patch` and the guest overlays, and supplies PCRE2/fmt archives to
CMake locally. It refuses to overwrite an existing `build/source`. Move both
`build/source` and `build/unpack` aside before preparing again.

The guest build generates `build/guest/mariamem.wasm`, `mariamem.wasmu`, and the
WASM/AOT hash sidecar. Build provenance is recorded in `build/prepared-source.json`
and `build/guest-build.json`. The Docker base and specialized compiler versions
are fixed; Ubuntu apt packages are not pinned to a repository snapshot. Identical
binary hashes across builds are not guaranteed.

## Local verification

Run the checks that match the changed boundary. These commands do not rebuild the
guest, wheel, or release assets.

| Change | Checks | Excludes |
| --- | --- | --- |
| Ordinary Go/Python source | `go test ./...`, `go vet ./...`, `PYTHONPATH=python .venv/bin/python -m pytest tests --ignore=tests/consumer -q`, `python3 scripts/check_public.py` | Real guest tests, installed-wheel consumer tests, release artifacts, benchmarks |
| Guest, host, MySQL wire, or lifecycle behavior | Ordinary checks plus `MARIAMEM_NATIVE_DIR=/path/to/native go test -race -tags=integration ./tests/gointegration -count=1 -timeout=3m` and the relevant opt-in Python real-host tests (`MARIAMEM_TEST_HOST=/path/to/mariamem-host MARIAMEM_NATIVE_DIR=/path/to/native`) | Wheel/platform acceptance and benchmarks |
| MySQL wire failure handling | The real-guest checks above plus `.venv/bin/python tests/integration.py` when its raw-protocol/failure-injection cases are relevant | Unrelated release checks |
| Snapshot export, restore, or validation | The real-guest checks above plus `.venv/bin/python tests/snapshots.py` for its negative-path/corruption cases | Unrelated release checks |

The Python command excludes `tests/consumer` because those tests must import an
**installed wheel from outside the checkout**. The opt-in Python real-host tests
skip without both environment variables; supply them when testing runtime or
lifecycle behavior. The older `integration.py` and `snapshots.py` scripts retain
distinct wire-failure and snapshot-corruption coverage, but are not part of the
ordinary source-change loop. Real-guest runs need a current native bundle; the
Python tests need `MARIAMEM_TEST_HOST` built from the current checkout. The older
scripts also read `build/guest` and `build/tools`, so do not use them against stale
build outputs. See [Go integration details](go.md#opt-in-integration-verification).

## Wheel and release acceptance

```sh
python3 scripts/build_alpha.py
```

Build the wheel when packaging or release inputs change. Installed-wheel
acceptance uses a fresh environment outside the checkout and
`tests/verify_alpha.py`; it is a release check, not an everyday test command.
The native archive, corresponding-source archive, platform acceptance, and
release guard likewise belong to the [release process](releasing.md). Run
[lifecycle benchmarks](../benchmarks/README.md) only for performance work; their
results are not correctness pass/fail thresholds. The guest-start diagnostic is
an [on-demand investigation tool](guest-start-diagnostic.md), not a test suite.

Use `build_alpha.py --go /path/to/go` when the pinned Go is not on PATH.
The supported deployment target is fixed in `python/deployment_target.json`:
macOS 15.0 arm64 (`macosx_15_0_arm64`), independent of the development OS.
The build sets GOOS/GOARCH and MACOSX_DEPLOYMENT_TARGET, and checks the actual
arm64 Mach-O minimum OS with `otool`; the environment variable alone does not
control the pure-Go linker. Binaries requiring a newer OS are rejected.
Packaging also checks that the native manifest matches this target.
The inspected Go host declares Mach-O minos 12.0 and Wasmer headless requires 11.0.
These load commands do not prove runtime compatibility (including the AOT guest):
Clean macOS 15.7.7 arm64 acceptance has passed for the recorded native candidate;
see [platform evidence](../release/evidence/macos15-arm64-acceptance.json).

The acceptance runner copies consumer tests outside the repository, clears runtime
overrides, and verifies installed-wheel startup, SQL, transactions, snapshots,
xdist, and cleanup after intentional test/setup failures. Results are written to
ignored `tests/evidence/`; raw logs are not published automatically.

Run `python3 scripts/check_public.py` to inspect the source-only publication set.
See [releasing](releasing.md) for source collection and binary release checks.
