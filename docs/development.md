<!-- Current v0.4 production path: direct-linked generated-Go. -->
# Building and testing

The repository is self-contained: no files from an earlier investigation workspace
are required. Downloaded inputs and all build products live under ignored `build/`.

## v0.4 default-path checks

Direct-linked generated-Go is the default. Go1.27.0/1.27.1 arm64 are unsupported
(upstream go#81036); no generated-source workaround. Use pinned Go1.26.8 for developer commands:

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py check
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py integration
# Explicit legacy Wasmer coverage:
MARIAMEM_NATIVE_DIR=/path/to/legacy-native GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py integration
```

Without an override, integration runs non-race generated-Go lifecycle/default
Snapshot/Fork tests, focused handwritten/runtime race tests, and Python host-only
lifecycle checks. Explicit legacy guest integration retains `-race`; default-only
tests always use the normal generated-Go path, clearing that override for the
default-isolation test. `tests/integration.py` and `tests/snapshots.py` select host-only
checks with `MARIAMEM_TEST_DEFAULT=1`. Default integration requires normal Python
Close/session behavior. Forced query-timeout reclamation remains separate from
this normal-path scope: `tests/test_python_timeout.py::test_query_timeout_disposes_wrapper`
is retained unchanged and was observed to fail with `guest cleanup timed out`
on direct-link. Explicit legacy integration still runs that failure-containment
test. Do not represent it as passing for direct-link. Installed-wheel SQLAlchemy and outside-checkout
GORM remain separate consumer acceptance. Generated source/guest identity checks run in
`check`; the narrow generated-function vet exception is documented in the
[architecture](v04-generated-go-architecture.md). The older bundle/AOT workflow
below remains available for explicit legacy/fallback builds, not normal v0.4 use.

The full generated guest is not Go race-detector clean. The v0.4 scope decision
retains this known limitation without suppression and does not require that
full-guest diagnostic to pass as a release gate. See the
[race investigation](../benchmarks/direct-link-race-scope.md) and
[direct-link baseline](../benchmarks/v04-direct-link-baseline.md).
Focused handwritten FD/filesystem/thread/TLS/futex race tests remain mandatory.
The [current roadmap](project-status.md) separates the v0.4.2 memory-contract
validation gate from the v0.5 stable-guest/toolchain race census. A backing change
does not prove the full shared-memory model race-clean; these races are not
claimed harmless.
To observe the full-guest limitation explicitly (expected to fail, diagnostic only):

```sh
MARIAMEM_NATIVE_DIR= MARIAMEM_RUNTIME= MARIAMEM_TEST_DEFAULT=1 GOTOOLCHAIN=go1.26.8 \
  go test -race -tags=integration ./tests/godefault -run '^TestDefaultRepeatedConcurrentLifecycle$' -count=1
```

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

Choose verification from the changed boundary, not the file extension or the
fact that a branch is being merged. Start with focused checks. Expand only when
a focused failure or an actual dependency requires it, and explain the exact
changed-file-to-subsystem dependency before running broader checks.

For experiment-workspace skill/helper/docs/tests changes that do not affect the
MariaDB runtime, generated-Go execution, SQL, Snapshot/Fork or language SDKs:

- Run `python3 -m pytest tests/test_experiment_workspace.py tests/test_release_tools.py tests/test_development_cleanup.py -q`.
- Validate the skill using the available skill validator and check its examples
  and relative links; run the Python tooling checks affected by the diff.
- Run `python3 scripts/check_public.py` and the affected boundary tests. If
  unrelated user files violate the publication allowlist, use a clean worktree
  at the exact candidate SHA; do not remove those files or relax the allowlist.
- Check `git diff --check`, the intended merge diff and Git status. Confirm no
  new tracked/staged or untracked changes remain; report pre-existing user state
  separately and preserve it.

Do not run full `verify.py check`, Go runtime integration, SQLAlchemy/GORM,
Snapshot/Fork runtime acceptance or broad release acceptance for that scope
without a concrete dependency found by focused verification. Documentation-only
changes need wording/reference and diff/status checks, not runtime tests. These
rules leave runtime-change and explicitly requested release gates intact.

For product-code checks below, run the matching command from the repository root
with Go 1.26+ and Python with `pytest` and `PyMySQL` installed. These commands do
not rebuild the guest, wheel, or release assets.

| Change | Command | Excludes |
| --- | --- | --- |
| Product Go/Python source (runtime or SDK) | `python3 scripts/verify.py check` | Real guest, installed-wheel consumer, release assets, benchmarks |
| Guest, host, MySQL wire, or lifecycle behavior | `MARIAMEM_NATIVE_DIR=/path/to/native python3 scripts/verify.py integration` after `check` | Wheel/platform acceptance and benchmarks |
| MySQL wire failure handling | The real-guest checks above plus `.venv/bin/python tests/integration.py` when its raw-protocol/failure-injection cases are relevant | Unrelated release checks |
| Snapshot export, restore, or validation | The real-guest checks above plus `.venv/bin/python tests/snapshots.py` for its negative-path/corruption cases | Unrelated release checks |

`check` runs Go unit tests, Go vet, checkout Python tests, and the public-source
check, plus the cheap release-version consistency check. It clears native test
settings so the opt-in real-host tests remain skipped.
`integration` uses generated-Go by default or an explicitly supplied legacy
native bundle, runs the real-guest Go tests with the
race detector, builds a temporary current Go host, and runs the Python timeout
and multi-client tests. Neither command runs `tests/consumer`, which must import
an **installed wheel from outside the checkout**. The older `integration.py` and
`snapshots.py` scripts retain distinct wire-failure and snapshot-corruption
coverage, but are not part of the ordinary source-change loop. Real-guest runs
need a current native bundle; the older scripts also read `build/guest` and
`build/tools`, so do not use them against stale build outputs. See
[Go integration details](go.md#opt-in-integration-verification).

For release work, `python3 scripts/verify.py release-check` invokes the current
`generated-go-v1` aggregate guard after host-only wheels, corresponding source,
regeneration and external acceptance evidence have been prepared. It stages
accepted bytes locally in `build/release/publish/`; it does not publish.
For an explicit candidate, use `release-check --ci-candidate-sha <sha>
--candidate-root <checkout>`; add `--platform darwin-arm64` or
`--platform ubuntu24.04-x86_64` for a platform guard. `--native-acceptance` is
retained only as an explicit legacy Wasmer guard path. Both-platform READY
requires one common exact source/guest identity and fresh immutable-artifact
acceptance. See [releasing](releasing.md).
For performance work only, select one workload with
`python3 scripts/verify.py bench go-isolation --native-dir /path/to/native [options]`
for canonical 0.2 core measurements; `bench isolation` retains Python consumer
regression measurement (other historical benchmark workloads remain optional);
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
workflow does not publish. Ubuntu is now a supported, publicly distributed target
with successful clean acceptance; every new release candidate still requires
its own exact-byte Ubuntu acceptance in the multi-platform release workflow.

`compile_guest_aot.py` selects the pinned Linux Wasmer distribution on Ubuntu
and an explicit x86_64/SSE2+SSSE3 AOT target, rather than inheriting optional CPU
features from a particular build runner. The target is recorded in provenance.
`build_alpha.py` builds the Linux Go host, records actual ELF `NEEDED` libraries
and GLIBC symbol requirements, and produces a `linux_x86_64` wheel.
`package_native.py` produces `mariamem-native-ubuntu24.04-x86_64.tar.gz`.
There is no manylinux claim, and the target is not generic Linux support.

Archive-only public Go acceptance uses the maintained harness with
`--target ubuntu24.04-x86_64`; the default macOS acceptance is unchanged.
Both consumers use exact packaged candidate artifacts outside the checkout.
No Docker or Tart is needed for this path.

## Measurement artifact reuse and architecture experiments

`guest-build-boundary.yml` uses exact-key immutable caches for measurement WASM
and each platform AOT. There are no prefix/fallback cache hits. Every hit verifies
input identity, original producing checkout, provenance and every output hash;
a corrupt hit fails instead of silently using or rebuilding it. A missing/evicted
cache rebuilds through the canonical scripts. Summaries report REUSED/REBUILT.

WASM identity covers all guest patches/overlays, pinned source/toolchain lock,
preparation/instrumentation/build/toolchain-install recipes, target and job
configuration. AOT identity covers exact WASM and handoff provenance, Wasmer
archive/version, platform, CPU compile flags, compiler recipe and package version.
Harness/analysis changes do not invalidate those keys. Platform/runtime changes
invalidate the corresponding AOT; only guest-relevant lock entries participate
in WASM identity. Release checks still require the complete current lock. Full release builds still require the exact candidate checkout;
measurement reuse never relabels an earlier artifact as newly built source.

For local measurements, `scripts/benchmark_artifacts.py key|seal|verify wasm`
and `key|seal|verify aot --target <platform>` expose the same checks. Seal only
fresh canonical build outputs, never restored artifacts. The AOT compiler's
`--benchmark-input-reuse` verifies a sealed WASM's identical inputs before
allowing an earlier build commit; do not use it for release preparation.
Cache scope/retention may cause misses; no bit-for-bit rebuild guarantee is added
for unpinned hosted OS packages.

Use `experiment/<short-purpose>` for disposable architecture probes. Keep main
for stable product behavior, measurements, harnesses, diagnostics and tooling.
On that branch, put temporary unified source changes in
`guest/experimental.patch` (paths `a/...` / `b/...`), leaving `guest/source.patch`
unchanged. Fresh `prepare_guest.py` applies it after the canonical patch, before
overlays, records its hash and affected source files, and refuses it outside an
experiment branch. Prefer modifications/additions; deletion-only patches are
not supported by this small mechanism. Commit the patch with the experiment so
its original input identity remains retrievable. The measurement workflow's
full-history checkout must retain an experiment branch when using this path.
Release source verification rejects experimental patches. Do not put prototype
outputs into accepted production provenance.

Before integration, provide a short hypothesis/correctness/benchmark summary,
semantic differences, platform limitations, guest/upstream patches and a
reject/continue/integrate decision. Experiment history is disposable: integrate
only the accepted production-quality change. No continuation or storage probe
is implied by this workflow preparation.

## First FAST tranche: prepared authentication keys and startup validation

The guest embeds one fixed **public, non-secret, test-only** RSA-2048 pair from
`guest/test-auth-keypair.json`. It is never appropriate for production credentials.
Source preparation derives a deterministic header; the fixture, preparation
helpers and modified plugin sources are recorded in guest provenance and guest
artifact reuse identity. Each process writes the keys exclusively into its own
memory filesystem at `/mariamem-auth`, outside snapshot-exported `/mariadb`.
They disappear with that process; Start and Fork provision the same fixture.
The plugin remains enabled, automatic key generation is disabled, and missing,
invalid or mismatched keys fail startup with a recovery message.

Default `skip-grant-tables` and public connection behavior are unchanged.
The dedicated guest command `--check-auth-keys` invokes the actual pinned
`caching_sha2_password` full-auth callback over a bounded mock non-TLS transport:
public-key request, RSA OAEP password, successful authentication, wrong-password
and malformed-ciphertext rejection. This establishes plugin/key correctness;
it does **not** establish full network account/grant authentication support.
The matching missing/corrupt-key diagnostic commands must fail, never generate
replacement keys.

Go validates manifest, runtime, AOT bytes and sidecar once on **each** startup,
then carries a single-use internal verified identity through that call. It skips
two repeated AOT hash scans; sidecar consistency and full snapshot inventory/hash
validation remain mandatory. Metadata rechecks (inode, size, mode, mtime and
ctime) reject mutation/replacement before launch. Keep `NativeDir` unchanged
throughout startup. This preserves the existing path-open race boundary; it is
not atomic protection against a hostile concurrent writer. There is no global
or persistent trust cache. Python's separate host still validates independently;
trust is not serialized across its process boundary.

For both-platform packaged acceptance and the new 1,000-row Go baseline,
dispatch `guest-build-boundary.yml` with `fast_tranche=true` on the exact pushed
commit. It checks external Go/installed-wheel consumers and real lifecycle/race
regressions, then records 20 samples plus two warmups at ×1/4/8, without costly
memory diagnostics. Verified WASM/AOT reuse applies only to identical inputs.
See [tranche baseline](../benchmarks/fast-tranche-baseline.md). Nothing is released;
submit the workflow and hand off without polling.

## v0.4 candidate verification tiers

The generated-Go candidate is isolated and disabled by default. See
[the documentation/test/build audit](v04-integration-audit.md) for the inventory.
Fast PR uses `verify.py check`; candidate integration additionally regenerates
inputs, runs generated filesystem/thread contracts, `verify.py integration`,
raw-wire/Snapshot checks and installed SQLAlchemy/GORM consumers. Release
acceptance adds exact supported platforms, cold source/artifact provenance,
zero-setup consumer and notices review. Fixed-environment benchmarks and old
spike traces remain manual; do not run them in parallel or make speed a CI gate.
Current CI's Wasmer guest job is not generated-Go regeneration/acceptance.

## Development artifact cleanup

Keep disposable v0.4 translations/builds and tool caches outside `publish/`.
Use the [disposable experiment workflow](experiment-workspace.md): caches and
completed workspaces are DELETE candidates after preserving unique knowledge.
See the historical [disk layout and cleanup](development-cleanup.md) for
a default dry-run helper, evidence retention and checksum-bound rebuild commands.
Canonical source, reports, input pins and regression tests remain in the repository.
