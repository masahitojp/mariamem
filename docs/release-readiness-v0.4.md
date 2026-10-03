# v0.4.0 release-readiness audit

Audited product candidate: `543867f82d3c174a72435d3077d8c1ec19b7949c`,
`v0.4/generated-go-integration`, 2026-10-03 JST. The audit adds a focused
non-race acceptance test and corrects timeout documentation only. No execution,
guest, generated artifact, Snapshot format, version, packaging or benchmark
change is made. This is not release approval or an exact-byte two-platform
Release CI acceptance record.

## Checklist

| Boundary | Classification | Evidence / remaining action |
| --- | --- | --- |
| Normal Go/Python | READY | Canonical `verify.py check` and `integration`; direct-link default, core SQL/protocol/auth/sessions/MaxSessions/reconnect and normal shutdown. |
| SQLAlchemy / GORM | READY | Repeated external consumer gates: SQLAlchemy44/44 against the installed unchanged candidate wheel; GORM32/32 with Options{}, including repeated AutoMigrate/discovery. Wheel host source is `57b5ed4f8c7148e553e23583516567ddb21052ad`; this is local product evidence, not a final release-version wheel acceptance. |
| Snapshot/Fork | READY | Normal fixture/multiple-child/write/schema isolation and negative corruption/lifecycle coverage; new malformed-manifest and closed-Snapshot rejection checks. |
| Representative graceful failures | SMALL GAP — fixed | `TestDefaultReleaseFailurePaths`: auth1045, syntax1064, duplicate1062, closed-listener error, reconnect, active idle-session Close, invalid Start inputs, canceled Start, malformed/closed Snapshot, recovery and FD/goroutine inventory. Three repetitions: FD6→6, goroutines2→2; no GC/finalizer or race suppression. |
| Timeout public description | SMALL GAP — fixed | Package/Options comments now say invalidation, not guaranteed termination; no runtime behavior changes. |
| Canonical guest / generated provenance | READY (local recipe) | [Reproducibility](v04-guest-reproducibility.md) and [integrated report](../benchmarks/v04-integrated-candidate.md): LLVM23.1.0 profile, clean canonical guest SHA `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`, independently matching build and deterministic generated-source/provenance inventory. `verify_generated_runtime.py` remains required. |
| Source/package selection | READY (committed source) | Clean managed checkout passes publication allowlist, version and license-mirror tests. Unrelated untracked npm files in the development checkout are excluded by using committed source; neither deleted nor allowlisted. A final release source archive is not yet accepted. |
| License/notice texts | READY (presence/mirroring only) | GPL/MariaDB, Go, WASIX/dependency and wasm2go MIT notices remain; wheel archive license propagation was checked during integration. This does not approve the new corresponding-source closure. |
| Generated-Go corresponding source / release provenance | BLOCKER | `package_source.py`, `verify_source.py`, `ci_guest_source.py` still require WASM→Wasmer AOT records and the old sysroot/compiler lock. `inputs.lock.json` uses LLVM21.1.206/exnref while this guest uses the documented LLVM23/legacy profile. New converter/toolchain/source closure and notices review must be integrated into the release guard, preserving exact hashes. Historical `review.json` approval is for different artifacts. |
| Supported platforms/toolchains | READY (documentation); exact acceptance BLOCKER | macOS15+ arm64 and Ubuntu24.04 x86_64 only; acceptance Go1.26.8/Python3.14. Local audit runs macOS27.0.1 arm64, Go1.26.8, Python3.14.8. Linux cross-compilation/local earlier evidence is not native macOS15/Ubuntu release acceptance for the final release SHA/bytes. |
| v0.4 release identity/notes | BLOCKER | Canonical `_version.py` and checked release examples still identify v0.3.0; there is no v0.4.0 release-notes file. Coordinate the version/notes and artifact metadata after the release-pipeline contract is migrated. Do not reuse/relabel the old artifacts. |
| Release CI inputs / frozen artifacts / guards | BLOCKER | Existing workflow, handoff, consumer expectations and platform/aggregate guards still describe Wasmer native bundles. They cannot currently approve the intended generated-Go host-only wheel + ordinary Go-source path. No workflow was dispatched. |
| Known runtime/performance limitations | DEFERRED / KNOWN LIMITATION | Listed below; not represented as resolved and not the reason for the release-pipeline blocker. |

## Failure matrix and boundaries

The new single integration test deliberately retains closed Database handles.
Each SQL/auth error must return an expected MySQL error, preserve healthy SQL
after ordinary failures, and permit subsequent Start. No panic recovery masks
host failures. Two rounds include a reconnected, established idle session during
Close, repeated Close and refusal by the closed listener. Eight repetitions
exercise each negative timeout option, pre-canceled Start, malformed Snapshot
Fork, and a temporary root that is a regular file rather than a directory.
Releasing the Snapshot is followed by ErrClosed rejection and a fresh SELECT1.
After cleanup, FD count equals its warmed boundary and goroutines return within
the explicit bounded allowance; observed 6→6 / 2→2 in all three repetitions.

This does not inject arbitrary mid-worker faults, abort an executing/hung query,
or establish exhaustive leak freedom. Existing concurrent lifecycle, retained
pipe-FD, grow/truncate, directory identity/rename-name-reuse and child isolation
checks remain enabled. Focused handwritten FD/MemFS/thread/TLS/futex runtime
`-race` checks remain mandatory. No canonical benchmark is rerun: only tests and
comments/docs changed, so the measured production runtime remains identical.

## Release CI mismatch: concrete stages

1. `.github/workflows/release-candidate-ready.yml` installs the old x86_64
   toolchain via `install_guest_toolchain.py` / `inputs.lock.json` and builds the
   Wasmer guest. It does not run the accepted LLVM23 legacy-EH→wasm2go recipe or
   compare regenerated Go with the checked-in canonical inventory.
2. Candidate jobs call `compile_guest_aot.py`, `build_alpha.py --runtime ...
   --module ...` and `package_native.py`. Passing both legacy arguments selects
   `runtime_kind=wasmer` and bundles Wasmer/AOT files. Omitting these arguments
   locally already builds a generated-Go host-only wheel, but the workflow does
   not use that path. Changing one invocation is insufficient.
3. `check_ci_release.py` requires `NATIVE_FILES=(wasmer-headless,
   mariamem.wasmu, mariamem.wasmu.json)`, a reviewed Wasmer binary, AOT provenance
   and identical native files in the wheel. Source closure, frozen handoff,
   cache-oriented consumer smoke, aggregation and public smoke depend on this
   contract. They need a bounded, separately approved release-pipeline migration;
   weakening the existing guard or claiming old evidence as new is unacceptable.

Expected v0.4 acceptance inputs are the exact remote candidate SHA/version,
canonical guest/generator input and generated-source manifests, reviewed
corresponding source/notices, and platform-specific generated-Go host-only
wheels. Freeze their hashes before external clean Go and installed-wheel
acceptance on both supported platforms. Any separately distributed legacy
fallback assets need their own unchanged verification; they must not stand in
for the default path. No distribution redesign/removal is chosen by this audit.

The local `verify.py release-check` correctly returns **NOT READY**: no accepted
source archive, no final wheel/installed-wheel record for this checkout, and no
exact native acceptance artifact. It does not stage publication. These missing
files are not synthesized to make the guard pass; the deeper CI contract above
must first describe the intended artifacts.

## Preserved limitations

- Full generated guest is not Go `-race` clean: general shared-memory-model
  adaptation remains deferred. No suppression and no claim of harmless races.
- Forced query-timeout reclamation/hard failure containment for non-cooperative
  in-process execution is not guaranteed. The retained diagnostic is known to
  fail its cleanup deadline; it is not run or fixed by this audit.
- Go1.27.0/1.27.1 arm64 are unsupported due to upstream `LDPSW: constant is not
  in pool`; upstream fix `b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa` was tested
  previously. No mariamem compiler/generated-source workaround is used.
- macOS post-Close physical footprint is distinct from live Go heap. Preserve
  **OS PHYSICAL ACCOUNTING DOMINATES**; do not claim harmlessness or immediate
  reclaimability. Prepared scaling remains a resource concern.
- Legacy Wasmer fallback and its packaging remain isolated and retained.
- The approximately one-second guest-side startup tail remains observable; the
  canonical campaign did not remove slow trials.

## Decision

Product and representative graceful failures pass locally. **Not ready to submit
the intended v0.4.0 candidate to the existing Release CI**: its build/provenance/
artifact/consumer/guard contract remains Wasmer-specific. This is broader than
a small release-readiness fix, so it was not implemented in this task.
Release version/notes and exact two-platform frozen artifact acceptance also
remain. No tag, release workflow, publication or new public artifact was made.

**V0.4.0 NOT READY — BLOCKERS REMAIN**
