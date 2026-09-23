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
