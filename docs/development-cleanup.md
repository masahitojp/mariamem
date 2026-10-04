# Development disk layout and cleanup

This is development housekeeping on `v0.4/generated-go-integration`, from
`b7bdf27fbf54a2fab3a352136a193aa09cf2766f`. It changes neither production
runtime selection nor release publication.

For new fan-out work, use the owned workspace and disk guard described in
[Disposable experiment workspace](experiment-workspace.md). Its cleanup defaults
to dry-run and leaves unmanaged legacy data for REVIEW. The historical allowlist
here is retained for its original scope.

## Keep source separate from disposable outputs

From the public repository root, the local workspace convention is:

| Location | Purpose | Policy |
| --- | --- | --- |
| tracked source, `docs/`, `benchmarks/*.md` and small evidence JSON | recipes, pins, reports, regression tests | KEEP |
| `../../build/mariamem-cache/` | checked source/tool archives, one selected LLVM prefix, checksum-bound guest | CACHE; reproducible inputs, never cleaned by the helper |
| `../../build/mariamem-work/` | translations, candidate modules/bundles, snapshots, compressed raw evidence | WORK / HISTORICAL RAW; not corresponding source |
| existing `build/tools`, fixed-reference/native bundles and test environments | Wasmer fallback and ordinary compatibility checks | CACHE; retained in this cleanup |
| existing `build/runtime-notices` | dependency/source/license closure material | KEEP pending release review |
| existing prepared `build/source`, other unclassified outputs and outer investigation tree | potentially useful local sources/experiments | UNKNOWN; retained |

The outer workspace already ignores `build/`; cache/work stay outside `publish/`
and the publication allowlist. In a standalone checkout choose sibling cache/work
locations instead; explicit reproduction arguments accept those paths. No global
SDK, Go module/build cache, Docker image or user-owned files were removed.
Do not move Python virtual environments: installed interpreter paths may be
absolute. They remain where they were created.

The reproducibility scripts, pinned LLVM source/version/archive hashes, input
lock, generated-source manifest and canonical guest hashes remain tracked. The
51 generated files are regenerated, not version-controlled production artifacts.
The [reproducibility recipe](v04-guest-reproducibility.md) and its
[evidence](../benchmarks/v04-guest-reproducibility-evidence.json) are authoritative.
Six complete compiler/source trees are not needed to retain that evidence.

## Large-item inventory

Sizes below are the initial `du` allocation (GiB), before moving/deleting.

| Item | GiB | Classification / disposition |
| --- | ---: | --- |
| generated-Go integration outputs | 23.05 | WORK / HISTORICAL RAW; repeated trees removed, small history exported/moved |
| LLVM archive and selected prefix (within the previous row) | ~3.2 | CACHE; one prefix/archive pair moved; redundant prefixes removed |
| runtime notices / dependency source closure | 1.31 | KEEP; release/source review still needs it |
| old legacy-EH source/product/artifact/probe | 0.99 | WORK; removed, user-file backups retained |
| Wasmer tools | 0.91 | CACHE; fallback/default check paths retained |
| prepared source tree | 0.86 | UNKNOWN; may contain local preparation changes, retained |
| GORM preparation tree | 0.58 | UNKNOWN; retained rather than guessing about local sources |
| input downloads | 0.49 | CACHE; moved, archive hashes checked |
| SQLAlchemy environments / reference bundle | 0.33 | CACHE; test interpreters retained at original paths |
| old release directory | 0.29 | HISTORICAL RAW; retained reference assets pending release integration |
| local Go cache | 0.23 | CACHE; retained |
| old wasm2go spike directory | 0.20 | UNKNOWN except pinned converter archive; archive moved, other outputs retained |
| dist/reference release fixtures | ~0.32 | CACHE / HISTORICAL RAW; retained fallback/consumer assets |
| historical benchmark outputs | 1.28 | HISTORICAL RAW; small evidence exported and compressed, raw trees removed |
| test snapshot runs | 0.40 | WORK; results exported, snapshots removed |
| outer investigation tree | ~4.2 | UNKNOWN; outside public repo and not touched |

## Safe cleanup helper

```sh
python3 scripts/clean_development.py --dry-run
python3 scripts/clean_development.py --apply \
  --evidence-dir ../../build/mariamem-work/cleanup-evidence-new
```

Dry-run is the default. The helper selects an explicit allowlist of historical
v0.4 directories, `tests/runs` and `benchmarks/results`. It cannot select arbitrary
paths, canonical reports, guest source, downloads, tool installations or current
native inputs. It rejects symlink targets/ancestors, tracked files and paths no
longer ignored. `--apply` requires a fresh evidence directory outside all targets.

Before deletion it exports JSON/log/CSV/XML files up to 10 MiB, excludes nested
source/modules/converter trees, records SHA-256 and size, and losslessly compresses
files over 64 KiB. Larger diagnostics are listed as omitted; canonical reports
already record the conclusions and reproduction inputs. Compression is verified
before deletion. This is evidence archival, not WASM checksum normalization.
A failure to export stops cleanup. Keep `export.json` and compressed file indexes
with archived results. APFS shared blocks mean `du` estimates are not a guarantee
of filesystem free-space recovery.

The initial dry-run and deletion list were printed before deletion. Old candidate
modules, successful/failed repeated clean-room builds, redundant LLVM prefixes,
compiler dumps, profiler/disassembly output and snapshots were removed. Historical
benchmark results were exported first. Pre-existing user-file backup directories
and the untracked npm manifests were retained unchanged.

## Rebuild after cleanup

Use fresh destinations. Build-time guest regeneration is still available:

```sh
python3 benchmarks/spikes/generated-go-integration/repeat_guest_builds.py \
  --output ../../build/mariamem-work/guest-six-clean-new \
  --downloads ../../build/mariamem-cache/downloads \
  --converter-archive ../../build/mariamem-cache/wasm2go-fork.tar.gz \
  --llvm-dir ../../build/mariamem-cache/llvm23-wasm-prefix/LLVM-23.1.0-Linux-ARM64 \
  --trials 6 --parallel 2
```

The selected prefix is recreatable with `prepare_llvm23.py` from the two retained,
checksum-pinned LLVM/ICU archives. Source archives remain pinned by the lock. The
six full source builds were already verified in the preceding commit; housekeeping
did not repeat that expensive campaign. This task instead verified a fresh
WASM→generated-Go→compiled-candidate rebuild after moving the inputs:

```sh
python3 benchmarks/spikes/generated-go-integration/translate_guest.py \
  --guest ../../build/mariamem-cache/guest-llvm23/mariamem.wasmu \
  --guest-sha256 5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb \
  --converter-archive ../../build/mariamem-cache/wasm2go-fork.tar.gz \
  --output ../../build/mariamem-work/translation-new
python3 benchmarks/spikes/generated-go-integration/setup_candidate.py \
  --source-module ../../build/mariamem-work/translation-new/module \
  --guest ../../build/mariamem-work/translation-new/guest.wasm \
  --input-manifest benchmarks/spikes/generated-go-integration/llvm23-generated-source.json \
  --output ../../build/mariamem-work/candidate-new
```

Translation matches all 51 generated files and converter/input identities. Fresh
candidate compilation and generated/base race tests pass. Ordinary Go test/vet,
Python tests, generated-Go integration and Snapshot/Fork acceptance are recorded
in the cleanup result. A source-only check copy excludes untouched user-owned npm
files; Git identity is supplied explicitly when that copy is outside the checkout.
The native-auth source archive remains available to avoid reducing test coverage.
No architecture/performance changes, tag or publication are part of cleanup.

## Completed cleanup and validation

| Measured data | Before GiB | After GiB |
| --- | ---: | ---: |
| Public repo build/results/test runs | 31.73 | 5.56 |
| Newly created external cache/work | 0 | 4.41 |
| Combined | 31.73 | 9.97 |

Net allocation reduction: **21.76 GiB** including retained caches,
compressed evidence and the fresh rebuild. Filesystem free space rose from about
18 to 37 GiB; APFS sharing, metadata and concurrent OS activity mean these two
measurements differ. The final archive contains lossless compressed raw evidence
with content hashes; canonical reports and small result JSON remain tracked.
The previous native candidate was removed only after its fresh replacement
passed acceptance. Validation snapshots were deleted again after preserving their
result. [Exact inventory/result](development-cleanup-results.json) records paths,
classifications, measurements and log digests.

Cleanup safety regressions: 7/7. Normal Go test/vet and Python380 PASS/3 SKIP;
fresh generated-Go integration passes Go race and Python3/3; Snapshot/Fork50/50.
`git diff --check` passes. `git status` retains only the original user-owned
untracked npm manifests after committing this documentation/tooling.
