# Guest source provenance (Task 9a3)

`release/guest-source-provenance.json` records the reviewed guest's WASM/AOT
hashes, build image ID, modified source hashes, source archive hashes/revisions,
and sysroot evidence. `guest_source=true` applies to this recorded build only.
Wasmer static Rust notices and clean-platform acceptance remain unresolved;
this review does not make a native bundle ready for publication.

## Evidence chain

The WASIX `v2026-07-03.1` asset `sysroot-exnref-eh.tar.gz` has SHA256
`12874e8ff2347ec57fd70954964689eb37ab7c0491b492c092d8dd19fbcc5b7e`.
Its payload and the actual saved build image's
`/root/.wasixcc/sysroot/sysroot-exnref-eh` match: 2,492 regular files/symlinks,
zero missing, extra, or changed entries. Files were compared by content SHA256;
symlinks by target. The manifest records a canonical inventory digest and hashes
for libc, libc++, libc++abi, libunwind, compiler-rt builtins, crt1, emulated-mman,
and emulated-process-clocks. Directory metadata is not part of this comparison.

The release tag resolves to WASIX libc
`09503b230e8acc721c1e013ca28a41bf149e4ee2`. The recorded successful
[upstream release run](https://github.com/wasix-org/wasix-libc/actions/runs/28659258439)
used recursive checkout and the exnref-eh build variant. The collected source
contains `.github/workflows/release.yml`,
`.github/workflows/build_cxx_sysroot.yml`, and the sysroot build scripts.
The pinned source inputs are:

| Source | Revision |
| --- | --- |
| WASIX libc | `09503b230e8acc721c1e013ca28a41bf149e4ee2` |
| LLVM | `6bb93a243f6d15855f485f5aec3810d9e2de150d` |
| WASI headers | `bac366c8aeb69cacfea6c4c04a503191bf1cede1` |
| WASIX headers | `0dfbd35a0f30f3fe7fd3b3ab5a50dc4191d5caed` |

Archive PAX commit metadata, pinned download URLs, hashes, and recorded submodule
refs identify these sources. Full upstream archives retain license/notice files.
The runtime coverage verifier checks required LLVM/runtime/header sources and
license files. Existing MariaDB/lite4mariadb dependencies, modifications and build
scripts remain in the corresponding-source candidate.

The saved compiler/link evidence identifies the eight runtime inputs above;
this is not a claim that every archive member survives linking. Full runtime
source archives cover that set without requiring a complete member map.
The actual variant is **sysroot-exnref-eh**; CMake's older `sysroot-eh` search-root
setting does not identify the actual driver-selected sysroot.

## Repeat verification

With the existing pinned downloads and saved guest build records/artifacts:

```sh
python3 scripts/verify_guest_provenance.py
python3 scripts/verify_guest_provenance.py \
  --sysroot-archive build/downloads/wasix-sysroot-exnref-eh.tar.gz \
  --compare-build-image
python3 scripts/package_source.py
python3 scripts/verify_source.py
```

Obtain the optional sysroot archive from the exact URL in the evidence manifest;
the verifier checks its SHA256 before reading it. Image comparison requires the
saved image and Docker; it runs read-only with networking disabled. Without these
options, verification checks recorded consistency, source coverage and local guest
hashes, and does not claim to repeat the payload comparison or remote CI check.

The source candidate embeds the evidence plus its hash and guest/sysroot hashes
in its source manifest. Packaging and verification reject guest build records,
modified inputs, source revisions or archive hashes that differ from the reviewed
evidence. Source verification also repeats offline MariaDB source preparation.
A future guest build requires renewed evidence review; the current approval must
not simply be carried forward to a changed artifact.

## Remaining reproducibility / hardening gaps

These are recorded separately from guest corresponding-source coverage:

- Header-generator Cargo dependencies are not fully vendored.
- A full offline sysroot rebuild is unverified.
- Full toolchain source closure is not collected.
- An independent bit-for-bit rebuild is unverified.
- A complete final archive-member link map is not recorded.

The original compressed download was not retained. A newly fetched fixed release
asset matches the entire installed payload; this is provenance evidence, not a
signed attestation or independent rebuild. Runtime-notice and platform reviews
remain separate binary-release blockers.
