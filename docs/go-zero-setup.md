# Exact-release Go native setup

This branch implements automatic native setup for future tagged releases. It
starts from `d3d700a76095a55361ad3c52ff031750c84c83c4`; no release/version bump or
runtime build was performed. Python packaging/installation is unchanged.

Ordinary application code becomes:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

See the [Go guide](go.md#automatic-setup-next-release-development-branch) for
cache locations, offline recovery and overrides.

## Distribution identity

Release CI publishes platform-specific `mariamem-native-darwin-arm64.tar.gz`
and `mariamem-native-ubuntu24.04-x86_64.tar.gz` alongside `SHA256SUMS`. The
archive contains runtime/AOT, their sidecar, native manifest, CANDIDATE metadata
and notices. Go runs the host in process; it does not download `mariamem-host`.

Go build metadata identifies the exact module tag. Native `package_version`
must equal its Python spelling (for example `v0.3.0-alpha.1` → `0.3.0a1`).
CANDIDATE's input-lock hash must equal the input lock compiled into the Go
module. Manifest/runtime/AOT/sidecar checks remain mandatory, with the existing
single-use startup identity and mutation checks. The lock hash identifies pinned
inputs, not all local guest patches: exact-tag published asset identity and CI
provenance provide the source/build relationship. Archives currently do not
embed a source commit; no new provenance or release policy was invented here.

Only stable and alpha/beta/rc module tags without replacement may download.
Development checkout, pseudo-version, replacement or missing build information
fails before network access unless an explicit override is supplied. In
particular, this branch cannot automatically use the v0.2.0 guest, which lacks
its protocol/discovery changes.

Downloads use exact-tag GitHub release metadata, canonical asset URLs and
SHA256SUMS; GitHub asset digests are checked when available. Trust is the same
HTTPS GitHub publication trust as manual release downloads, not an independent
signature. The private cache receipt records release/platform/archive and
extracted-file hashes. Each startup rechecks files; it is not a global trust
cache. As with explicit bundles, the user account controlling the cache remains
part of the trust boundary.

## Verification on this branch

| Boundary | Result |
|---|---|
| Exact release selection, stable/prerelease spellings | Controlled fixtures pass; never selects latest |
| macOS and Ubuntu artifact naming/manifest selection | Controlled fixtures pass |
| First download, checksum/provenance/version validation | Controlled HTTP transport fixtures pass; streamed bounded archive |
| Cached second resolution and offline resolution | Pass; test transport fails if any network request occurs |
| Concurrent first installers | Four concurrent callers pass; private staging and atomic installation |
| Corrupt cache/runtime/sidecar/manifest/notices/receipt | Rejected; no silent redownload |
| Missing asset, wrong version/input identity, unsafe archive, truncated response | Rejected; no installed partial cache |
| Cancellation during download, failed download then retry | Pass; staging removed and subsequent resolution succeeds |
| Explicit NativeDir and environment precedence | Public API tests pass |
| Public Options{} in an untagged unit build | Fails safely without contacting GitHub |
| GORM with application Options{} | 32/32 cases pass on macOS; matching environment override |
| Go race / real-guest lifecycle | Pass on macOS with explicit matching bundle |
| Python / SQLAlchemy regression | Standard tests and 44/44 SQLAlchemy cases pass |

GORM uses unchanged pool/migration/CRUD behavior. For this untagged branch the
runner explicitly substitutes the development Go module and sets the supported
`MARIAMEM_NATIVE_DIR` override; the application passes `Options{}`. This is
**not** proof of public tagged automatic startup or a published consumer smoke.
The local bundle has Wasmer 7.4.2 and AOT SHA256
`90da311cbcaeec30705a73fe45629c7ede470d1094b3db7ca6e113de294b1d84`.
Ignored evidence is under `tests/evidence/gorm-zero-options/` and
`tests/evidence/sqlalchemy-zero-setup-regression/`.

```sh
/opt/homebrew/bin/python3.14 tests/consumer/run_gorm.py \
  --native-dir build/gorm-dogfood/native \
  --output tests/evidence/gorm-zero-options --source-dir . --zero-options
```

## Remaining usability acceptance

- **P1:** a future exact tagged release containing this code must exercise public
  first-download/cache/offline `Options{}` startup on both release platforms.
  No compatible public bundle exists for this development source; using v0.2.0
  to pretend otherwise would violate compatibility.
- Ubuntu real-runtime acceptance is now complete; see the follow-up below.
- **NICE TO HAVE:** an explicit prefetch/cache-inspection command may help offline
  provisioning; existing NativeDir/environment overrides already provide it.

No P0 blocker was found in the implemented resolver or local lifecycle checks.

## Follow-up full startup acceptance

The release-like full public startup path now passes locally with a real macOS
bundle: tagged private module, local release server, Start(Options{}), SQL,
cache/offline, concurrent startup and failure recovery. No production resolver
hook or public release was added. Clean macOS 15 arm64 and Ubuntu 24.04 x86_64
acceptance subsequently passed on `872fdea882ad82540ffe32e14e506ff67b2d10c3`
in [run 36582171063](https://github.com/masahitojp/mariamem/actions/runs/36582171063).
Both platforms passed all nine full-startup resolver cases, GORM 32/32 and
installed-wheel SQLAlchemy 44/44; see [v0.3 acceptance](v03-acceptance.md).
The earlier fixture-only limitation above is historical; public published-tag
smoke remains distinct from this controlled release-like check. The branch is
ready for a dedicated release-readiness audit.
