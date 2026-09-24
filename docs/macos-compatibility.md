# macOS support floor: 15+ / arm64

The initial native alpha targets **macOS 15 and later on arm64**. macOS 12–14
are unsupported. Declared bundle/wheel metadata uses minimum macOS 15; this does
not rewrite the runtime binary's older Mach-O load commands.

## Preserved macOS 12 failure

The maintainer reported clean macOS **12.5.1 arm64** acceptance of candidate
SHA256 `7fe851bdab2fafef1dffd2607a8af41b880a1a539c6e37be25b11c7f1aa8c8c2`:

- Archive checksum, extraction/permissions, module fetch and consumer build passed.
- `wasmer-headless --version` returned Wasmer 7.4.2; Mach-O was arm64 with minos 11.0
  and expected system dylibs.
- `mariamem.Start` returned EOF. Subsequent diagnostic evidence reported guest
  execution aborting because `__unw_add_find_dynamic_unwind_sections` was unavailable.

This records the maintainer's finding; the raw VM diagnostic files were not
provided to this checkout. The earlier preparation record and diagnostic tooling
remain preserved. No Wasmer/libunwind fix has been implemented, and the missing
symbol is not claimed to be repaired by raising metadata. Mach-O minos and a
successful `--version` were insufficient to establish guest-execution compatibility.
Supporting older macOS is outside this alpha's scope.

## New acceptance boundary

The harness now requires macOS major version **15** and arm64 to verify the new
floor. Newer development hosts may perform dry-run only, even though declared
product support is 15+. Use a newly generated archive, its exact SHA256 and an
external public-module consumer. Platform review remains false until all checks
succeed on a clean macOS 15 arm64 host.

GitHub's [hosted runner reference](https://docs.github.com/en/actions/reference/runners/github-hosted-runners)
lists `macos-15` as arm64; `macos-15-intel` is not a substitute. Candidate transfer
must not turn this acceptance task into public binary publication.
