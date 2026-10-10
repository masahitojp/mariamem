# Dev guest single-pass build — DESIGN ONLY

## Human Review

Recommendation: reuse the canonical recipe for a deliberately unqualified,
single-build development route. Implement only after a separate approval.
This document implements no flag, alternate builder, guard or accepted input.
The v0.5.0 goal remains a stable MariaDB guest; no target version is selected.

The [assessment](v05-fast-feedback-assessment.md) and
[phase 1](v05-fast-feedback-phase1.md) separate cheap feedback from qualification.
The proposed route answers whether a candidate guest can build, translate and run
small SQL scenarios. It does not establish reproducibility, compatibility or
release readiness. A `--dev` label alone is insufficient.

## 1. Current constraints

`build_generated_guest.py` requires fresh Linux arm64/root, empty fixed `/work`
and SDK/source/output paths, at least two source builds, accepted WASM hash,
matching linked/WASM repetitions, and no experimental patch. It records inputs,
source commit, toolchain/archive/sysroot inventories and build configuration.

`regenerate_release_guest.py` requires an accepted guest and regenerates
translation → memory32 fixture → source-only adaptation → installed source,
then compares every byte including handwritten glue. `generate_runtime.py`
reads canonical release pins; it is not presently a generic arbitrary-WASM
installer. `setup_candidate.py --source-only --input-manifest` already supports
an explicit source inventory, but that alone does not remove the downstream
accepted-input constraints.

`generated_release.verify_build` checks exact source, contract, accepted guest,
actual WASM hash/size, at least two matching builds, linked hash, source overlays,
input lock, tools, generation proof/inventory and translation provenance.
Release CI independently uses this recipe on a fresh builder. None changes here.

## 2. Proposed lifecycle and storage separation

```text
committed experiment source/patch/tool inputs
  → fresh canonical build environment → ONE compile/link/postopt
  → dev evidence: observed hashes + UNQUALIFIED contract
  → explicit translation from those WASM bytes
  → explicit dev source installation → fresh dev host
  → small SQL + focused failures → candidate judgment

Human accepts the exact source/recipe candidate
  → independent clean Release builds (at least two)
  → accepted inputs + byte reproduction + full required qualification
  → final artifact/consumer/guard → eligible release
```

Use an existing disposable experiment branch/workspace. Dev source, WASM,
translation, generated Go and binary live only under task `temp/`; compact input
and result records live under `evidence/`. They must not use `build/generated-release`,
`build/release-regeneration`, checked-in `internal/generatedgo`, wheel `_native`,
or Release frozen handoff directories. Never update canonical pins automatically.
Fresh builder/container boundaries still protect fixed `/work`/SDK paths; parallel
builds must use distinct environments, not share that global directory.

Reuse the current source preparation, toolchain installation, shell compile/link,
Binaryen flags, pinned converter/patches, source-only adapter and installer rules.
Prefer extracting their existing call boundaries inside current scripts, rather
than a new acceptance workflow or parallel build framework. The likely interface
is an explicit development mode plus explicit fresh output/input paths, but its
exact CLI is not approved or implemented by this document.

## 3. Unqualified provenance and binding

Reuse existing JSON inventory fields and SHA256 primitives. A dev record needs:

- a contract distinct from `generated-go-v1` (e.g. `development-unqualified`),
  result explicitly UNQUALIFIED and observed one-build count;
- actual source commit/tree plus dirty diff/explicit input identities; qualification
  later requires committed clean inputs, never an ambiguous working directory;
- source archive/lock, source.patch and any experimental patch, overlays, tools,
  SDK/sysroot/flags, actual linked and optimized WASM hashes/sizes;
- converter source/archive/patch hashes, translation file inventory, adapter/install
  inputs, handwritten file inventory, generated tree identity and host build identity;
- execution OS/toolchain and exact smoke argv/exit, not only an asserted PASS.

Raw phase telemetry is diagnostic timing, not this dependency binding and not a
qualification receipt. Production provenance/license obligations remain independent.
An experimental.patch must be recorded and cannot cross to accepted Release source
without review and incorporation into canonical source.patch.

## 4. Prevent old generated Go and contamination

| Failure scenario | Concrete prevention / future negative test |
| --- | --- |
| dev guest receipt copied into Release directory | distinct contract + single-build count; existing `verify_build` rejects both. Output namespaces and fresh Release builder additionally prevent accidental discovery |
| dev WASM changes but previous translation is used | fresh translation output; actual input WASM hash passed and checked; generated inventory/provenance bound to that hash |
| previous checked-in generated tree builds successfully | explicit dev source-module/output is mandatory; verify compiled host guest identity equals observed dev hash before SQL smoke. No default-to-main fallback |
| stale `MARIAMEM_TEST_HOST` or wheel `_native` executes | build a fresh dev host into task output; verify source/build/guest identity; controlled env, explicit host path, no wheel staging |
| old accepted pins are relabelled as new guest evidence | no auto adoption. Installer must receive explicit observed dev input identity; accepted pins remain Release authority |
| same output reused after partial failure | fresh output or explicit cleanup, only successful complete inventory may be reused; absent/partial manifest never PASS |
| dev record marker is manually changed to release contract | marker is not sufficient: Release also requires accepted pins, actual bytes, source, independent repetitions, reproduction and authenticated CI. No supported promotion-by-editing-receipt operation |
| failed experiment enters automatic READY reuse | Release qualification only accepts its existing authenticated proof/contracts/source identity. Dev run has no eligible runtime/artifact receipt |
| copied dev object files conceal source/tool changes | initial design uses clean C builds. No CMake/ccache incremental reuse in this first route |
| tools have same filename but different bytes | pinned archive/source/patch identity + observed tool versions/hashes; reuse only after identity checks |

Guards defend supported workflow mistakes; a JSON label is not an adversarial
security proof against forged source/build receipts. CI source/transport identity
and independent fresh rebuilding are part of the release trust boundary.

## 5. The minimal unresolved implementation boundary

Two places actually need design work: the builder's accepted-hash/two-build
policy, and the installer's canonical-pins source. Merely allowing one repetition
would still reject a new guest hash and could accidentally weaken Release checks.

Proposed bounded approach: preserve the Release defaults and `verify_build`
unchanged; pass explicit dev input/translation inventories into the same
adaptation/installation logic with isolated output. Any opt-in overrides must
propagate through all downstream stages, not only the builder. Derive the dev
manifest from observed bytes, including converter output; never accept arbitrary
unchecked user hash assertions. Emit distinct unqualified records throughout.

Do not implement a second Snapshot format, guest runtime selector, cache manager,
new release provenance model or new workflow. If a stable guest needs changed
WASIX ABI, adapter assumptions, memory/thread/trap semantics or source patches,
stop and review that concrete dependency; this proposal does not promise that
existing converter/adapter supports MariaDB 12/13 without changes.

## 6. Promotion and failed-build reuse

Promotion means accepting the source/recipe change, not promoting a dev artifact.
Freeze clean experiment source/patch/tool hashes; review dependencies, notices and
source obligations; consciously update canonical accepted inputs and generation
recipe on the candidate branch. Run independent fresh builds and complete byte
reproduction. Require relevant SQL/protocol/auth/session, FS/growth/ownership,
Snapshot isolation, lifecycle/failure/trap, guest race census and both native OS
qualification. Then verify final module/wheel/consumers and Release guards.
Dev output can be compared with those results, never substitute for them.

On failure, retain logs/phase metrics/observed input hashes and a concise failure
description. Checksum-verified downloads can be reused while the task is active.
Existing Go cache can serve compatible converter/host rebuilds. A completed WASM
or translation can be reused only if its complete input identity remains unchanged
and its successful output inventory is rechecked. Discard partial C/translation
outputs, incomplete receipts and stale binaries. Cache and workspace are deleted
at task completion; compact evidence remains.

## Human decision still required

Approve implementation of this isolated unqualified route, including explicit
dev inputs through installation, while keeping Release defaults and guards intact?
Until that approval, no single-pass execution or guest-update experiment starts.
