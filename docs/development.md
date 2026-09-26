# Building and testing

The repository is self-contained: no files from an earlier investigation workspace
are required. Downloaded inputs and all build products live under ignored `build/`.

## Requirements

- macOS 15+ arm64 or Ubuntu 24.04 LTS x86_64 for native AOT/package builds.
- Go 1.26.8; Python 3.9+ with pip, setuptools >=58 and wheel.
- Linux x86_64 with the pinned WASIX toolchain for the canonical guest WASM
  build; native AOT and packaging run on the matching product platform.
- Docker with Linux arm64 support only for the older combined local build path.
- `patch`, a network connection for first-time downloads, and sufficient disk/RAM.

The toolchain versions and source archive hashes are in
[`release/inputs.lock.json`](../release/inputs.lock.json).
Docker/compiler requirements apply to developers; they are not user dependencies.

## Guest build boundary

The future-candidate path separates the host-independent WASIX guest from its
target-specific AOT artifact:

```sh
# On Linux x86_64, after installing the native host-tool packages listed in
# .github/workflows/guest-build-boundary.yml:
python3 scripts/install_guest_toolchain.py
python3 scripts/prepare_guest.py
python3 scripts/build_guest_wasm.py

# Transfer the complete build/guest-wasm/ directory unchanged. On macOS 15
# arm64 or Ubuntu 24.04 x86_64, from the same source commit:
python3 scripts/compile_guest_aot.py --wasm-dir build/guest-wasm
```

The Linux output includes the exact WASM SHA256 and source/toolchain provenance.
The target-native command verifies that hash before using pinned Wasmer 7.4.2 and records
the AOT SHA256 separately. The manually dispatched
`guest-build-boundary.yml` workflow runs this handoff and a minimal real
MariaDB smoke on separate GitHub-hosted jobs. It does not produce an approved
release or alter the published alpha.3 provenance. No Docker or Tart is needed
on this path; build-tool packages and hosted-runner images are not yet pinned to
bit-for-bit reproducible OS snapshots.

## Older combined local guest build

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

Run the matching command from the repository root with Go 1.26+ and Python with
`pytest` and `PyMySQL` installed. These commands do not rebuild the guest, wheel,
or release assets.

| Change | Command | Excludes |
| --- | --- | --- |
| Ordinary Go/Python source | `python3 scripts/verify.py check` | Real guest, installed-wheel consumer, release assets, benchmarks |
| Guest, host, MySQL wire, or lifecycle behavior | `MARIAMEM_NATIVE_DIR=/path/to/native python3 scripts/verify.py integration` after `check` | Wheel/platform acceptance and benchmarks |
| MySQL wire failure handling | The real-guest checks above plus `.venv/bin/python tests/integration.py` when its raw-protocol/failure-injection cases are relevant | Unrelated release checks |
| Snapshot export, restore, or validation | The real-guest checks above plus `.venv/bin/python tests/snapshots.py` for its negative-path/corruption cases | Unrelated release checks |

`check` runs Go unit tests, Go vet, checkout Python tests, and the public-source
check, plus the cheap release-version consistency check. It clears native test
settings so the opt-in real-host tests remain skipped.
`integration` requires the native bundle, runs the real-guest Go tests with the
race detector, builds a temporary current Go host, and runs the Python timeout
and multi-client tests. Neither command runs `tests/consumer`, which must import
an **installed wheel from outside the checkout**. The older `integration.py` and
`snapshots.py` scripts retain distinct wire-failure and snapshot-corruption
coverage, but are not part of the ordinary source-change loop. Real-guest runs
need a current native bundle; the older scripts also read `build/guest` and
`build/tools`, so do not use them against stale build outputs. See
[Go integration details](go.md#opt-in-integration-verification).

For release work, `python3 scripts/verify.py release-check` invokes the existing
release guard after the source, wheel, native bundle, and acceptance evidence have
been prepared. It verifies hashes/reviews and **stages files locally** in
`build/release/publish/`; it does not publish. See [releasing](releasing.md) for
the required preparation. For performance work only, select one workload with
`python3 scripts/verify.py bench {ready,seeded,parallel,memory} [options]`;
see [benchmark settings](../benchmarks/README.md).

CI runs `check` on Ubuntu and `integration` on the GitHub-hosted macOS 15 arm64
runner, using the SHA256-pinned public alpha.2 native bundle. It tests the current
host/wrapper against that fixed guest; after guest source changes, rebuild the
bundle and run `integration` against the new guest separately. The clean platform
acceptance and exact release-artifact checks remain release-only.

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

## Ubuntu 24.04 product candidates

The first Linux product target is exactly Ubuntu 24.04 LTS / x86_64. The
`ubuntu-product.yml` workflow uses `ubuntu-24.04` runners to build
and hand immutable candidate bytes to a separate clean consumer job. This
workflow does not publish. Clean acceptance remains pending until that run passes.

`compile_guest_aot.py` selects the pinned Linux Wasmer distribution on Ubuntu
and an explicit x86_64/SSE2 AOT target, rather than inheriting optional CPU
features from a particular build runner. The target is recorded in provenance.
`build_alpha.py` builds the Linux Go host, records actual ELF `NEEDED` libraries
and GLIBC symbol requirements, and produces a `linux_x86_64` wheel.
`package_native.py` produces `mariamem-native-ubuntu24.04-x86_64.tar.gz`.
There is no manylinux claim, and the target is not generic Linux support.

Archive-only public Go acceptance uses the maintained harness with
`--target ubuntu24.04-x86_64`; the default macOS acceptance is unchanged.
Both consumers use exact packaged candidate artifacts outside the checkout.
No Docker or Tart is needed for this path.
