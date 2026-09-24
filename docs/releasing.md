# Releasing an alpha

This folder is the source repository intended for GitHub. Historical experiments,
local tools, databases, raw logs, and native artifacts are outside the source
publication set. A GitHub source repository and a binary Release have separate
readiness checks.

## Current release work

- Product code, consumer examples, and regression tests use this repository only.
- Pinned MariaDB/lite4mariadb, connector, wolfSSL, PCRE2, and fmt archives are
  collected by hash. The build applies the maintained patch/overlays.
- Go host, Wasmer headless, guest AOT, and metadata are bundled in a platform wheel.
- `release/review.json` tracks remaining source/license and environment checks.
  An unverified item must remain false; a generated source archive is not by
  itself evidence of completeness.

## Local preparation

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
4. Finish each review in `release/review.json`, recording evidence paths and notes.
   In particular, resolve WASIX runtime source dependencies and Wasmer's static
   dependencies/licenses against the actual native binary.
5. Run `python3 scripts/check_release.py`. It must pass before distributing the
   wheel. Rebuild source/release manifests after any source or review changes.

## Go native candidate

`python3 scripts/package_native.py` packages existing staged artifacts into
`build/release/native-candidate/`. See [Go manual bundle instructions](go.md#manual-native-bundle-local-candidate).
This candidate-only path does not populate `build/release/publish/` or satisfy
release reviews. It preserves current notices and records unresolved reviews;
complete corresponding-source and runtime notice review are still prerequisites
for public binary distribution.

## GitHub

Create the repository from this folder. Choose the GitHub owner before running
the following commands; `<owner>` is a placeholder, not a configured destination.

```sh
git init -b main
git add .
git diff --cached --stat
git commit -m "Prepare mariamem Python alpha"
gh repo create <owner>/mariamem --public --source . --remote origin --push
```

Binary release commands are intentionally separate from source push. After
`check_release.py` succeeds and the release commit is pushed:

```sh
gh release create v0.1.0a1 --draft --prerelease --title 'mariamem 0.1.0a1' \
  --notes-file release/NOTES.md build/release/publish/*
```

Review the draft assets and publish it. No command in the build scripts creates
a repository, pushes code, or publishes a release. The source archive must remain
available alongside the exact binaries it corresponds to. The default GitHub
source zip is not a replacement for the collected dependency sources.

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
runtime-notice and platform-acceptance reviews remain false. This does not approve
binary publication. No guest binaries are rebuilt by this coverage verification.
