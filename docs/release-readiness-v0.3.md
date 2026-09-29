# v0.3 release-readiness audit

## v0.3 merged candidate

Audited on **main**, after integration and push, at
`96a5c3b32e76715eee664a171e0b6f435f3b458f` on 2026-09-29 JST.
`v0.3/integration` was created from accepted source
`872fdea882ad82540ffe32e14e506ff67b2d10c3`, then fast-forwarded through its
acceptance-report documentation commit. Main was fast-forwarded from
`dca0413f6f7adfb97961271b164ff476241380bc`; no squash, cherry-pick or history
rewrite was used. The complete history includes SQLAlchemy dogfood,
CLIENT_FOUND_ROWS, GORM dogfood, WASIX discovery, Go resolution and acceptance.

The only differences between accepted source `872fdea` and integrated `96a5c3b`
are five documentation files. Product, guest, workflow and acceptance harness
bytes are unchanged. This supports the compatibility conclusions below; it
**does not transfer exact-source CI acceptance to a different SHA**. The audit
commit adds documentation only; its resulting main HEAD is the current candidate
identity. Future release preparation must freeze and accept its final exact SHA,
not reuse `872fdea` as the release/tag source.

## Confirmed

[Completed CI 36582171063](https://github.com/masahitojp/mariamem/actions/runs/36582171063)
accepted `872fdea` independently on macOS 15.7.9 arm64 and Ubuntu 24.04.5 LTS
x86_64, with Go 1.26.8, Python 3.14.7 and Wasmer 7.4.2.
Downloaded records were checked for source/hash consistency; downloaded AOT
manifest and current harness hashes were recomputed. Binary archive hashes were
verified by CI and reconciled between records, not recomputed locally from
archive downloads. See [full acceptance identities](v03-acceptance.md).

| Boundary | macOS | Ubuntu | What the evidence establishes |
|---|---|---|---|
| SQLAlchemy 2.0.54 / PyMySQL 1.2.3 | 44/44 | 44/44 | Installed-wheel User/Address CRUD, relationships, default pools, commit/rollback and ordinary constraints; no flag removal or application workaround |
| GORM 1.31.1 / MySQL driver 1.6.0 | 32/32 | 32/32 | CRUD, relationships, repeated AutoMigrate, discovery, normal pools and transactions; no SQL rewrites or single-connection restriction |
| Disposable isolation | PASS | PASS | Commit → dispose → successor sees seed only, without cleanup SQL; engine/pool/database resource close still required |
| Wire checks | 38 | 38 | FOUND_ROWS unchanged UPDATE returns 1; unflagged returns 0; schema enumeration and existing protocol behavior |
| Snapshot integrity | 50 | 50 | Snapshot/Fork plus actual corruption, symlink and wrong-build rejection |
| Lifecycle | PASS | PASS | Real-guest race/lifecycle, timeout invalidation and cleanup; packaged Go and Python checks |
| Release-like zero setup | 9/9 | 9/9 | Download, cached/offline, concurrent first start, corrupt cache/archive, interrupted download, missing asset, incompatible version and explicit override |
| Runtime notices | PASS | PASS | Exact runtime identities match reviewed notices |

Normal usage in a matching future tagged release is:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

The resolver selects the exact module tag, never latest. Explicit NativeDir then
MARIAMEM_NATIVE_DIR precede the version/platform cache and canonical GitHub
download. SHA256SUMS, optional GitHub digests, archive contents, package version,
sidecar and embedded input-lock identity are checked before atomic installation;
cached files are verified again per startup. Private staging tolerates concurrent
installers. Dev, replaced and pseudo-version builds fail before network access
without an explicit matching bundle. Deterministic unit tests cover these cases
without public downloads.

Scope remains macOS 15+ arm64 and Ubuntu 24.04 LTS x86_64, SSE2 + SSSE3. No
manylinux, broader distro, Linux arm64, Windows or macOS Intel claim is made.
Framework/version combinations beyond those above are not established by this
work. Python 3.14.7 / Go 1.26.8 are the clean acceptance toolchains, not a broad
language-version matrix.

## Release-boundary checks

### Clean Go consumer

The dedicated v0.3 harness builds an ordinary external Go executable from a
private tagged module proxy, without replace or NativeDir. Canonical resolver
HTTP requests are redirected by a test-only transport to a controlled server.
Real runtime startup, SQL, cache/offline and failure recovery passed on both
platforms. This proves the implementation boundary, not public installation.

Two release-path gaps remain:

1. `tests/consumer/run_zero_setup.py` uses synthetic `v0.3.0-alpha.999` and
   repackages a copied manifest as `0.3.0a999`. It preserves AOT/runtime bytes but
   does not consume the frozen release archive unchanged. Release-candidate
   validation needs a private tagged-module fixture that consumes the exact
   final candidate archive/checksums at the derived release version, without
   editing candidate bytes or using a production resolver override.
2. `scripts/ci_release_public_smoke.py` delegates to `platform_acceptance.py`;
   its Go consumer explicitly requires an absolute NativeDir and calls
   `Start(Options{NativeDir: native})`. It checks the public tag and published
   bytes but bypasses automatic download/cache. It cannot prove the normal v0.3
   public Go installation path. A post-publication check must use a clean module,
   empty isolated cache, no native override and the real published exact tag,
   then verify cached/offline startup. Such a public check cannot genuinely be
   performed before publication; the private candidate check complements it.

### Clean Python consumer

`v03_acceptance.py` installs the candidate wheel in a clean temporary virtualenv;
SQLAlchemy runs outside the checkout with no native override. This passed 44/44
on both platforms. The normal release workflow already installs/checks exact
wheels outside the checkout (`tests/verify_alpha.py`, plus Ubuntu tests), but
**does not invoke the SQLAlchemy runner**. It must attach the maintained ORM
check to the final exact wheel's acceptance before release READY. Current
post-publication smoke also lacks installed-published-wheel SQLAlchemy coverage.
GitHub wheel distribution is sufficient; PyPI recovery is not a v0.3 blocker.

### Native/source/artifact consistency

No stale v0.2 native bytes were found in the accepted v0.3 run. It built a fresh
common WASM, SHA256
`d49402efec834414527537f639c9a11e5709bf8642357d34d33c7cfa471322d3`,
and independently compiled both AOT targets. Actual FOUND_ROWS and discovery
checks passed against those artifacts. The new guest connection passes the
requested capability to MariaDB; `guest/source.patch` makes WASIX directory
readability use stat/access rather than absent permission bits. These are
canonical source changes, not application workarounds.

The release workflow builds the exact remote SHA. `ci_guest_source.py` checks
prepared source/overlay hashes, pinned toolchain/sysroot, WASM handoff, AOT,
target/CPU baseline and reviewed runtime identity. `check_ci_release.py` compares
corresponding-source contents to the candidate, requires offline source checks,
checks native/wheel equality and versions, and binds platform acceptance to
source SHA and archive hash. The aggregate requires both platforms and common
WASM; publication rechecks READY, tags the exact source and uploads frozen bytes.
Reusing old branch acceptance or old v0.2 AOT/provenance cannot satisfy these
checks. Downloads rely on HTTPS GitHub publication/checksums, not an independent
signature; native archives do not themselves embed a source commit.

This audit did not build new release artifacts or run aggregate READY. Current
canonical version and public distribution remain **v0.2.0 / Python 0.2.0**.

## Findings

Each finding has one classification.

| Class | Finding / required action |
|---|---|
| **BLOCKER** | Final v0.3 clean-consumer gates are incomplete: wire exact candidate zero-setup and maintained ORM acceptance into the release path, bind evidence to final source/artifact identities and require success before READY. Current guard can pass without these v0.3 checks. |
| **BLOCKER** | Public smoke bypasses the central Go zero-setup feature and does not exercise published-wheel SQLAlchemy. Before v0.3 publication, provide clean external public-tag Options{} and published-wheel consumer smoke on both platforms; failures must stop/report without retagging or replacing assets. |
| **REQUIRED BEFORE RELEASE** | Finalize canonical v0.3.0 metadata, README/Go/Python installation examples, maturity wording and NOTES-v0.3.0.md through existing preparation mechanisms; check tag/release uniqueness. Keep public v0.2 references accurate until the release transition. |
| **REQUIRED BEFORE RELEASE** | Freeze the new exact main release-preparation SHA; run complete two-platform v0.3 acceptance and source/license/provenance checks against its immutable artifacts, then aggregate READY. Historical branch PASS is not final-source READY. |
| **DOCUMENT** | Development-check workflow integration intentionally downloads alpha.2 guest bytes. It cannot establish v0.3 FOUND_ROWS/discovery behavior and must not be cited as current-guest release acceptance; dedicated exact candidate acceptance is authoritative. |
| **DOCUMENT** | First Go startup needs network/download unless cached or overridden; dev/pseudo/replaced modules need explicit matching native input. GitHub wheels remain the Python installation channel while PyPI recovery is pending. |
| **DOCUMENT** | Per-DB memory remains substantial; performance is hardware dependent. Small ORM fixtures have not shown a clear Snapshot/Fork speed advantage. No product correctness blocker follows from these limitations. |
| **DEFER** | Larger migration-heavy workloads, additional framework/version matrices, dbt, broader platforms and CoW/runtime/VFS/sharing architecture work. |

## Checks on merged main

- `python scripts/verify.py check`: PASS; Go tests/vet, Python **329 passed /
  3 skipped**, version/public-source checks.
- `go test -race ./...`: PASS; real-runtime race/lifecycle separately passed in
  the accepted cross-platform run above.
- macOS and Ubuntu runtime-notice verification: PASS; no missing notices.
- Existing source/provenance, retry, guard and publication negative tests are
  included in normal verification. No real release, tag or publication attempted.
- `git diff --check`: PASS.

## Release verdict

**NOT READY** for v0.3 publication: product compatibility acceptance is green,
but the release path does not yet enforce/prove the new clean-consumer boundary.
No new product feature, optimization or architecture change is needed by this
audit. The two BLOCKER findings require focused release validation work; metadata
and final exact-source READY remain ordinary release preparation afterward.
