# Building and testing

Generated-Go is the only supported runtime on this v0.4.3 candidate branch.
Build products and downloaded inputs live under ignored `build/`. Use Go1.26.8
and Python with pytest/PyMySQL; Go1.27.0/1.27.1 arm64 remain unsupported because
of upstream go#81036. Product platforms are macOS15+ arm64 and Ubuntu24.04 x86_64.

## Local verification

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py check
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py integration
```

`check` runs Go tests/vet, checkout Python tests, generated identity,
version consistency and public-source validation. Historical Wasmer fixtures
under `tests/historical` are excluded; they are not a current release gate.
`integration` always uses the compiled generated guest: SQL/auth/sessions,
Snapshot/Fork, lifecycle/memory32 traps, focused runtime/thread/TLS/futex races,
and Python normal Close/multi-client tests. Retired native/runtime environment
overrides are cleared by the harness; public APIs reject them explicitly.
Installed-wheel SQLAlchemy and outside-checkout GORM remain separate acceptance.

The full generated guest is not Go race-detector clean; do not suppress it or
claim focused tests prove otherwise. See the [race census](../benchmarks/direct-link-race-scope.md).
Forced query-timeout/hard-failure reclamation remains a separate diagnostic,
not part of normal cooperative Close acceptance. The retained diagnostic
`tests/test_python_timeout.py::test_query_timeout_disposes_wrapper` is not a gate.
No force-kill or guest race adaptation is added by runtime retirement.

## Guest / generated source

WASM is a build intermediate; WASIX libc/sysroot and LLVM runtime sources remain
required. Retiring the Wasmer execution engine does not retire those sources,
thread imports, converter or notices. Current exact recipes/pins remain unchanged:

- `scripts/build_generated_guest.py`: two independent source-to-WASM builds on
  a fresh Linux arm64 builder; this is a build platform, not the Ubuntu product.
- `scripts/regenerate_release_guest.py`: regenerate all checked-in translated
  source and compare every byte, including pure-memory32 regression fixtures.
- `scripts/verify_generated_runtime.py`: cheap committed translation identity.

Use the exact-source Release CI for fresh guest/source acceptance. No Wasmer
validator, native AOT compilation or external runtime is used in that path.
`guest/source.patch` stays canonical. Temporary source changes belong only to
`guest/experimental.patch` on experiment branches and cannot pass release provenance.

## Packaging / release dry runs

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/build_alpha.py
python3 scripts/verify.py release-check --ci-candidate-sha <full-sha> --candidate-root <clean-checkout>
```

The builder stages a host-only wheel; legacy runtime/module packaging flags are
rejected. `release-check` only validates/stages accepted bytes, never publishes.
Exact macOS/Ubuntu artifacts, Go/Python consumers, GPL corresponding source,
NOTICE/licenses/provenance and READY are required. See [releasing](releasing.md).
A release request is one exact-SHA CI handoff; historical evidence is not new
candidate approval. Do not wait/poll after successful submission.

## Benchmark / experiment mechanics

```sh
GOTOOLCHAIN=go1.26.8 python3 scripts/verify.py bench go-isolation --runs 3 --warmup 1 --workers 1
```

No native directory is needed. Measurements remain manual and run alone on the
machine. Preserve useful lifecycle/stage/resource harnesses and historical
reports; reproduce old Wasmer execution with its pinned old tag rather than a
second current runtime. See [benchmark notes](../benchmarks/README.md).

Use independent experiment branches/worktrees and explicit disk/resource guards.
Preserve compact JSON/CSV, final reports and checksums; dispose owned temp/build
outputs after finalization. Never clear shared expensive caches or uncertain raw
evidence. See [safe cleanup](development-cleanup.md) and [project status](project-status.md).

## Historical runtime material

The removed legacy guest-build/platform/Ubuntu workflows exist in prior tags.
Native/AOT packaging, provision/cache, Wasmer-specific acceptance and notice
review CLIs are retired and fail with guidance to that history. Their source and
inert fixtures remain reference material, outside current gates. Shared module
identity, platform metadata and authenticated GitHub artifact transport are
retained as runtime-independent helpers. See [Track A inventory](../benchmarks/v043-wasmer-retirement.md).
