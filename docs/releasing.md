# Releasing an alpha

The canonical release version is `v0.1.0-alpha.4`; the Python distribution is `0.1.0a4`.
Change the five semantic components only in `python/mariamem/_version.py`.
Run `python3 scripts/verify.py check` to verify the derived Python version and
Git/Go tag and release-facing README/Go/Python examples. Update those examples
when changing the canonical version; historical release records are excluded.
The release guard checks these docs and versioned artifact names and rejects stale
native/wheel metadata; set `MARIAMEM_RELEASE_TAG` when comparing a proposed tag.
The source repository, native bundle, and Python wheel have separate checks.
Historical experiments, local logs, and generated binaries stay outside Git.

For future candidates, the [guest build boundary](development.md#guest-build-boundary)
records Linux x86_64 source/toolchain/WASM identity separately from macOS arm64
Wasmer AOT identity. Its CI verification is not release approval. The published
alpha.3 `release/guest-source-provenance.json` and review apply only to their
recorded artifact hashes; a newly built guest requires its own corresponding
source/provenance review before the existing release guard can accept it.

## CI candidate readiness (future releases)

Manually dispatch `release-candidate-ready.yml`. Its small input interface is:

| Mode | Inputs | Work performed |
| --- | --- | --- |
| `full` (default) | remotely fetchable `candidate_ref` | Linux guest build, macOS AOT/package, clean acceptance, guard |
| `acceptance-only` | original candidate SHA as `candidate_ref`, `candidate_run` ID | restore exact frozen candidate, clean native/wheel acceptance, guard |
| `guard-only` | original SHA, `candidate_run`, optional `evidence_run` (defaults to candidate run) | restore exact candidate and acceptance evidence, guard only |

Retry modes skip both build jobs. `candidate_run` must be the original run that
uploaded `release-candidate-<sha>`; an acceptance retry only uploads new evidence.
Use its run ID as `evidence_run` for a later guard retry. The workflow tooling
and immutable candidate source are checked out separately, so a guard fix can
verify an older candidate without changing its source or bytes.

For example, to retry the proven candidate's guard:

```sh
gh workflow run release-candidate-ready.yml \
  -f mode=guard-only \
  -f candidate_ref=1f1379351c6054518fb48aeddc9640845b36dab9 \
  -f candidate_run=36215480255
```

The workflow resolves the requested source to a full remote SHA. Reuse verifies
the GitHub artifact ZIP digest, safe extraction, exact source/build provenance,
and recomputed native/wheel/source hashes. Guard-only additionally validates
both acceptance records against those exact artifacts. Missing, expired,
corrupted, or mismatched inputs fail clearly; there is no rebuild fallback.
Retention is currently 14 days. A new full run is required when reusable inputs
are unavailable.

The full path transfers exact WASM to macOS 15 arm64 for AOT, wheel, native,
and corresponding-source construction. A separate clean macOS job accepts the
frozen native archive through the public Go module at the exact source commit
and tests the installed wheel. Acceptance evidence stays external. The workflow
produces candidate/evidence artifacts and a summary of mode, source, reused
identity/hashes, failed stage, acceptance, and `READY`/`NOT READY`. The verification
stages never tag or publish; `operation=release` enables the publication job
described below. Neither path requires Docker or Tart.

**Codex submits work to CI; it does not supervise CI.** After a long-running
dispatch, hand back the run URL, candidate SHA, and mode immediately. Do not poll,
wait, or report elapsed time. Re-enter for an explicit human status request,
requested CI failure/NOT READY diagnosis, or an unexpected engineering decision.
The handoff is:

> Release CI has been submitted for candidate `<sha>`. GitHub Actions owns
> execution; no further local work is needed until a result requires attention.

### Publication decision

```text
human: "release this candidate"
→ Codex: submit exact candidate and hand off
→ CI: build → acceptance → guard
      NOT READY → stop
      READY → tag → publish → post-publication smoke
```

Starting the release workflow is the single human publication decision. It
approves the deterministic transaction as a whole; READY must not request a
second approval. Codex does not supervise or poll after submission. CI does not
make release decisions, schedule releases, or bump versions automatically.

`release-candidate-ready.yml` defaults to `operation=verify`, which never
publishes. `operation=dry-run` rechecks READY and publication inputs without
creating tags or releases. Only `operation=release` authorizes publication;
it works with the same full/acceptance-only/guard-only retry boundaries.

After preparing the canonical version, current release-facing docs, and tracked
`release/NOTES-alpha.N.md` (or `NOTES-beta.N.md`, `NOTES-rc.N.md`,
`NOTES-vX.Y.Z.md`), submit the remotely available exact commit:

```sh
gh workflow run release-candidate-ready.yml -f candidate_ref=<full-source-sha> \
  -f mode=full -f operation=release
```

An optional `notes` input selects another tracked candidate-relative file with a
heading identifying the canonical tag. CI rechecks the guard and exact artifact
hashes, creates an annotated tag at the build commit, uploads the four accepted
assets to a draft, downloads/verifies them, then publishes (prerelease for
alpha/beta/rc). It runs the maintained external Go consumer against the public
tag and downloaded native bundle. No candidate is rebuilt after acceptance.
Existing local/remote tags or GitHub releases stop publication, even if they
appear to describe the same candidate. No overwrite, deletion, or rollback is
performed after failure; a public-smoke failure leaves the release intact for
investigation. JSON reports and logs are retained in
`release-publication-<source-sha>` with the failing stage in the workflow summary.
Codex returns the run URL and hands off immediately; it does not supervise CI.

For this path, `package_source.py --ci-evidence-dir build` and
`verify_source.py --ci-evidence-dir build` compare the new WASM/AOT provenance,
reviewed sysroot source payload, pinned source archives, licenses, and offline
source preparation. The source archive contains build-time records only.
`build_alpha.py --ci-candidate` likewise embeds stable candidate metadata, not
post-build review. `verify.py release-check --ci-candidate-sha <sha>
--native-acceptance <evidence.json>` checks the exact hashes and emits external
`ci-ready.json` and `SHA256SUMS` only after all checks pass. The legacy local
release-check and historical alpha.3 evidence remain unchanged.

## Current release work

- Product code, consumer examples, and regression tests use this repository only.
- Pinned MariaDB/lite4mariadb, connector, wolfSSL, PCRE2, and fmt archives are
  collected by hash. The build applies the maintained patch/overlays.
- Go host, Wasmer headless, guest AOT, and metadata are bundled in a platform wheel.
- `release/review.json` records source, runtime-notice, and clean macOS 15
  acceptance evidence. Recheck the evidence if a reviewed binary changes.

## Local tooling reference (diagnostics)

These commands remain available for focused diagnostics and tooling development;
the normal release path belongs to CI.

1. Follow [development](development.md) to build and test the guest and wheel.
2. Run `python3 scripts/check_public.py`. The source publication set must not
   contain local paths, secrets, symlinks out of the tree, native artifacts, or
   references to the previous workspace.
3. Run `python3 scripts/package_source.py` to produce a source *candidate* and
   manifest in `build/release/`. This collects pinned source archives and this
   repository's selected sources, licenses, and build scripts.
   Then run `python3 scripts/verify_source.py` to extract it outside the repository,
   prepare the guest with network access disabled, and compare the modified source
   files with the inputs of the local guest build.
4. Build the versioned wheel with `scripts/build_alpha.py`. From an isolated
   environment outside the checkout, install that exact wheel with its `test`
   extra and run `tests/verify_alpha.py`. It records the wheel SHA256 in
   ignored `tests/evidence/alpha-wheel.json` and binds installed-wheel results
   to it in `tests/evidence/alpha.json`.
5. Run `python3 scripts/verify.py release-check`. It invokes the existing release
   guard to check source, reviews, exact wheel/acceptance hashes, and the native
   archive hash from clean-platform
   evidence. It stages the native bundle, corresponding source, wheel, and
   SHA256SUMS in `build/release/publish/`, with a local release manifest at
   `build/release/release-manifest.json`. The publish directory must be empty
   first. Rebuild source and wheel evidence after public files or reviewed
   artifacts change.

## Go native candidate

`python3 scripts/package_native.py` packages existing staged artifacts into
`build/release/native-candidate/`. See [Go manual bundle instructions](go.md#manual-native-bundle-local-candidate).
This path does not populate `build/release/publish/`; the release guard copies
the accepted archive there after hash verification. The accepted candidate's
SHA256 is recorded in [clean-platform evidence](../release/evidence/macos15-arm64-acceptance.json).
The review applies to that exact archive; regenerate and recheck if its bytes
change. The planned Release includes this native bundle.
`CANDIDATE.json` records stable build inputs only. Review and clean-platform
acceptance are external evidence bound to the finished archive's SHA256; updating
them does not change the native candidate bytes.

## Smoke checks

- **Go source:** after the tag is published, use a fresh external module to run
  `go get github.com/masahitojp/mariamem@<published-tag>` and build the
  [README Go example](../README.md#go). Before tagging, use the pushed commit
  instead of the version. The Go module contains no native binaries.
- **Native bundle:** compare the downloaded archive's SHA256 with its published
  checksum and the accepted evidence. Extract it, check that `wasmer-headless`
  is executable, then run the same Go example with `MARIAMEM_NATIVE_DIR` set
  to the extracted directory. It should print `1`.
- **Python wheel:** install the exact staged wheel with `[test]` in a
  fresh virtual environment. From outside the checkout, run the checked-in
  `tests/verify_alpha.py` with that environment's Python. It checks bundled
  files, SQL, fixtures, snapshots, parallel workers, and cleanup. Compare its
  `wheel_sha256` with the staged wheel's hash.

## Publication inputs

Prepare notes for the intended canonical version before submitting a release.
`release/NOTES.md` and `release/NOTES-alpha.3.md` are historical release records,
not current version inputs. Publication consumes the READY candidate's exact
assets and derived tag without another approval gate.
The corresponding-source archive must remain available alongside the binaries
it covers; GitHub's default source zip is not a replacement for the collected
dependency sources. Local build/check commands never publish; only the explicitly
authorized CI publication job pushes the release tag and publishes assets.

## License scope

The project chooses GPL-2.0-only for its own code. Keep original licenses and
copyright notices for all dependencies. Source collection includes build scripts
and modifications; generated binaries are bound to their inputs by hashes.
Build tools and linked runtime libraries must be distinguished when determining
source requirements. See [GPLv2 section 3](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html).

## WASIX guest source coverage (Task 9a1)

The source candidate now includes full pinned archives for the three submodules
of WASIX libc `v2026-07-03.1`:

| Source | Revision | Required license files inside its archive |
| --- | --- | --- |
| llvm/llvm-project | `6bb93a243f6d15855f485f5aec3810d9e2de150d` | `LICENSE.TXT`, `libcxx/LICENSE.TXT`, `libcxxabi/LICENSE.TXT`, `libunwind/LICENSE.TXT`, `compiler-rt/LICENSE.TXT` |
| WebAssembly/WASI | `bac366c8aeb69cacfea6c4c04a503191bf1cede1` | `tools/witx/LICENSE` |
| wasix-org/wasix-witx | `0dfbd35a0f30f3fe7fd3b3ab5a50dc4191d5caed` | `tools/witx/LICENSE` |

All other upstream LICENSE/NOTICE files are retained inside the full source
archives too. LLVM runtime licenses include Apache-2.0 with LLVM exceptions and
component-specific legacy notices; header tools declare Apache-2.0. Preserve the
actual per-file notices rather than assigning one new license to all sources.

`release/inputs.lock.json` connects the existing submodule pins to downloadable
source inputs with explicit commit URLs and SHA256 hashes. `package_source.py`
verifies these before packaging. The candidate embeds that lock plus a source
manifest recording each revision, archive hash, source coverage, and license-file
hashes. GitHub source tarballs do not include Git history: revision verification
uses the pinned commit URL, expected archive root, and content hash, not `git rev-parse`.

`verify_source.py` checks the outer archive hash, bundled/current lock agreement,
all three nested archives, revision consistency, required source directories and
nonempty license files. It also retains the existing offline MariaDB preparation
and comparison with the actual guest's modified build inputs. LLVM source is
inspected without expanding its whole tree or compiling any runtime.

The recorded variant is **`sysroot-exnref-eh`**: it was observed in the actual
compiler dependency files and build-image driver selection. CMake's older
`sysroot-eh` search-root setting is not proof that this other variant was linked.

Task 9a3 completed the guest source provenance review for the recorded artifact.
See [guest source provenance](guest-source-provenance.md) for the evidence,
validation commands, and remaining reproducibility gaps. `guest_source` is true;
runtime-notice review and acceptance of the recorded native candidate are now
complete. This provenance review does not publish binaries. No guest binaries
are rebuilt by source verification.

## Wasmer runtime notice review (Task 9b)

See [runtime notices](runtime-notices.md) for the pinned dependency inventory,
verification commands, Singlepass BUSL-1.1 disclosure, and the accepted webc
12.0.1 package MIT declaration. `runtime_notices` is true after Task 9b-final.
The absence of a separate webc license file is recorded without inferred
copyright wording. The release guard and review of the exact staged assets
remain the final local checks before publication.
