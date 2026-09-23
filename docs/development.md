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

## Wheel and acceptance

```sh
python3 scripts/build_alpha.py
python3 -m venv .venv
.venv/bin/python -m pip install './build/dist/mariamem-0.1.0a1-py3-none-macosx_27_0_arm64.whl[test]'
.venv/bin/python tests/verify_alpha.py
.venv/bin/python tests/integration.py
.venv/bin/python tests/snapshots.py
go vet ./...
```

Use `build_alpha.py --go /path/to/go` when the pinned Go is not on PATH.
Wheel tags conservatively use the build machine's macOS major version. The
acceptance runner copies consumer tests outside the repository, clears runtime
overrides, and verifies installed-wheel startup, SQL, transactions, snapshots,
xdist, and cleanup after intentional test/setup failures. Results are written to
ignored `tests/evidence/`; raw logs are not published automatically.

Run `python3 scripts/check_public.py` to inspect the source-only publication set.
See [releasing](releasing.md) for source collection and binary release checks.
