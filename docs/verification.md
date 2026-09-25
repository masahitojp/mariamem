# Local verification — 2026-09-23

This is a historical verification record. Its then-open publication items were
reviewed later; see the current [release review](../release/review.json) and
[release instructions](releasing.md).

The public repository was tested on macOS 27 arm64 with Python 3.9, Go 1.26.8,
Wasmer 7.4.2, PyMySQL 1.2.3, pytest 8.4.2, and pytest-xdist 3.8.0.

## Build provenance

MariaDB was built from freshly extracted pinned archives using the public
`prepare_guest.py`, maintained overlays, and Docker toolchain. PCRE2/fmt were
supplied from the verified local archives. No earlier guest binary or
investigation script was used. The existing pinned Docker toolchain image was
reused; rebuilding that image from scratch and cross-machine execution remain
unverified.

| Artifact | SHA-256 |
|---|---|
| WASM | `8b2822d3414cb978bc9b608faa55e3b8980c905906889741aba0a40a3cc17c10` |
| AOT | `f2d31597064e12ba3a6955c51cdbef5aaae5d33501b50799a5ef27dadc7e562b` |

Build timestamps can change guest hashes. Snapshot compatibility is tied to the
specific guest build. These hashes describe this local validation, not a claim
that a public release has occurred.

## Acceptance

| Check | Result |
|---|---|
| Installed wheel, default options, consumer outside source tree | 7 tests passed |
| Same consumer with xdist, two workers | 7 tests passed |
| Migration/seed fixture override | 2 tests passed |
| Intentional assertion/setup failures | Both expected failures; fixture processes and temporary directories reaped |
| SQL/lifecycle integration | 37 checks passed |
| Snapshot/fork regression | 49 checks passed |
| Publication/archive-boundary unit tests | 6 tests passed |
| Source candidate extracted outside the repository | Offline preparation passed; modified guest files match the fresh build inputs |
| Go static analysis | `go vet ./...` passed |

The installed-wheel runner checks the installed Python/native files against the
wheel and records the exact wheel hash. Local build/acceptance records are under
ignored `build/` and `tests/evidence/`; those raw machine paths/logs are not part
of the GitHub source publication set.

## Remaining publication work

- Collect and verify the recursive WASIX runtime sources identified in
  `release/inputs.lock.json`, including LLVM runtime code and header definitions.
- Resolve the actual Wasmer headless dependency set and required notices.
  The upstream full-source archive includes a Cargo.lock with 813 packages;
  775 are registry packages and 38 are workspace packages. It does not vendor
  registry package sources/licenses and is not a completed dependency audit.
- Validate the documented environment outside this development machine before
  expanding the supported platform claim.

The source candidate and binary publication gate deliberately retain these
unresolved checks. Passing functional tests does not mark them complete.

## Historical macOS 12 candidate (superseded)

The previous wheel target was explicitly `macosx_12_0_arm64`, with native manifest
`minimum_macos: 12`. On the development macOS 27 arm64 machine, `otool` reports
`LC_BUILD_VERSION minos 12.0` for the Go host and `11.0` for Wasmer headless.
The build rejects binaries requiring a newer OS, verifies the wheel tag and
bundled manifest, and records binary minimums in local `alpha-wheel.json` evidence.
Five focused deployment-check tests passed. The newly built and installed wheel
passed startup, PyMySQL `SELECT 1`, and shutdown on the development machine.

This earlier load-command inspection did not establish runtime compatibility.
Clean macOS 12.5.1 testing subsequently failed during guest execution; see
[the compatibility finding](macos-compatibility.md). The current target is
macOS 15+ arm64 (`macosx_15_0_arm64`, `minimum_macos: 15`).
Clean macOS 15 acceptance is required before changing the platform review.
