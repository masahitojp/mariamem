# C2 source-only dependency inventory for Issue133 / Issue134

Question: which source, generated artifact, receipt, ref, path, environment and
cache inputs does current C2 assembly/qualification/lifecycle require, and what
must #134 formally place or reproduce without historical local workspaces?

Input snapshot: `ae9c243f1f65ae0adb94dbd10b5049d298475afa`; fixed guest/installer
origin `be244a0bdb510a22417241c2aa2f76a9093aac1b`. Scope: these three C2 scripts,
their fixed-origin generation/verification chain, committed fixtures and saved
receipts. Exit: a compact classified inventory with consuming source locations,
pins, reproduction gaps and placement suggestions; source/link/hash checks only.
Additional active work ceiling: 30 minutes within the original two-hour budget;
zero builds, CI, runtime acceptance, measurements or other-workspace cleanup.
An inaccessible artifact or unexecuted reproduction stays unknown, never PASS.
At the ceiling, record the remaining gap and next work rather than expand.

The current C2 scripts have a committed generation recipe, but they still
require externally prepared guest/translation bundles and a prepopulated Python
venv. The available summaries and hashes do **not** supply all original artifact
bytes or raw receipts. Recommend #134 define explicit guest, translation,
staged-source, binary and installed-wheel handoffs, then run a fresh supported
platform reproduction. The main limitation is that neither that reproduction
nor global artifact availability was checked here; source availability alone
cannot establish independence from local state.

The [machine inventory](evidence/dependency-inventory.json) has 22 dependency
records, consuming source commit/path/line, classification, reproduction gap and
suggested formal placement, plus 47 cited source SHA256 pins and the seven
toolchain/six selected upstream archive URL/checksum declarations. These
classifications distinguish committed inputs, declared fetch inputs, generated
outputs and operational state; “regeneratable” means a committed recipe exists,
not that regeneration passed. Archive endpoints/content were not fetched.

## Source and ref boundary

The clean source check inventories **all tracked files**, not only runtime code.
C2's host checkout and guest checkout are separate inputs. The guest must be at
`be244a0bdb510a22417241c2aa2f76a9093aac1b`; host/observer identities must follow the
candidate actually executed. The original host was
`3602b186f309eb3af349df494470d28b8bb800c2`, public observer was
`af42349d368e281f530935c33d620af3b6ebf7e1`, and lifecycle observer was
`545ca1f83e7749d59556edfbab2c4f9bee36b45e`. Their historical PASS is unchanged.
The current source snapshot is not that historical execution.

Read-only GitHub commit API checks found the current inventory input commit,
fixed guest origin and historical host commit with tree IDs recorded in the
JSON. This establishes remotely served commit metadata, not fresh clone success
or availability of every binary. Observer commits remain identified by saved
receipts/local Git history; separate remote transport was not checked for them.
No local branch name is a semantically required input: exact source commits and
complete inventories are. The previous six-file normalization and raw-history
mapping remain on this branch without changes.

## Required chain and classification

| Stage/input | Source classification and gap | Suggested #134 placement |
| --- | --- | --- |
| Guest producer | Entire fixed-origin checkout, `guest/input.json`, canonical and experimental patches, guest overlays, prepared UCA numeric bundle and preparation helpers are committed. A new source replay remains unexecuted. | Guest build job with exact source/overlay lock, seam controls and tool identity. |
| Source downloads | `prepare_guest.py` directly selects MariaDB, lite4mariadb, connector-c, wolfSSL, PCRE2 and fmt by lock URL/SHA. Additional runtime-source entries in the general lock are not direct reads on this preparation path. Download availability is untested. | Verified fetch/mirror stage; cache optional and always checksum-checked. |
| Builder tools | Seven archives are pinned, including LLVM23/ICU, wasixcc, both sysroots, Binaryen and converter. Fresh root Linux arm64, empty `/work`, absent `/root/.wasixcc`, host packages and mount privileges are operational requirements of the P1-b wrapper. Apt package versions/image are not fully locked. | Isolated producer image/job, recorded package/tool versions; task-owned SDK/build directories. |
| Guest bundle | `mariamem.wasm`, `linked.wasm` and **complete** `guest.json` are read by the verifier. C2 summary records hashes; it is not a substitute for this bundle. Current global availability is unknown. | Authenticated producer artifact with all three files and manifest; retain `UNQUALIFIED` scope. |
| Converter | Fixed archive, 13 ordered committed patches and wait-contract fixture; Go toolchain/modules and converter executable must be acquired/generated. | Maintained translator and lock with explicit upstream archive/module checks. |
| Translation | `input-manifest.json`, guest copy, patched `wasm2go` executable and complete `module/generated` including `data.bin` are required by `verify_translation`. Summary hash is insufficient. | Same-job regeneration or complete authenticated translation handoff. |
| Source adapter | `setup_candidate.py --source-only` calls `setup_audit.py`/`patch_memfs.py` and copies committed FD/prepared-file templates. Default accepted manifest and old Wasmer native build are bypassed by C2's explicit manifest/source-only arguments. | Maintained source adapter/template owner, separate from historical Wasmer diagnostics. |
| Install receipt | Fresh `installation-inputs.json` records inventories and hashes plus **live** guest/translation directories. Installer reopens those directories. Historical exact receipt is not preserved here as a C2 file. | Restore verified inputs first, then emit a new path-bound receipt and downstream hash; never edit historical receipt paths. |
| Runtime installer | Fixed-origin generator imports adaptation modules and copies `HANDWRITTEN_FILES` from `internal/generatedgo`/`scripts/runtime_correctness`. Whole fixed checkout is the source input; the cited hash list is an audit index, not a replacement checkout. | Formal generator plus handwritten-source owner inventory. Final manifest must cover owner copies and overlays. |
| Public overlays | P1-b binding/ABI identities, wire/completion fixtures, lifetime preimage overlay, and C2 factory/public fixture are committed required inputs. They cannot be deleted as duplicate scratch. | Runtime-required code under maintained generator/host owners; instrumentation/tripwire/fault fixtures under acceptance owners. Placement is a suggestion, not approved migration. |
| Host product | All tracked host files except old generated runtime are copied, then runtime/factory/tripwire/guest identity are changed. Even tracked `build/go.mod` is part of source. | Explicit staged-source owner/selection and post-overlay inventory; do not use a historical all-files inventory for new source. |
| Binaries | `public.test`, `mariamem-host` and raw `public-binaries.json` are compile outputs. Committed normalized binary receipt has a different structure/hash and cannot satisfy qualification's raw-receipt check. Old executable availability unknown. | Same-job compile or authenticated source-bound binary bundle, raw receipt plus optional public normalization sidecar. |
| Python/wheel | Venv/pip/build packages/PyMySQL must already exist. Wheel, native manifest, installed module and consumer directory are generated operational state. Hash in historical result does not supply wheel bytes. | Locked Python build/consumer setup and fresh venv; exact host/wheel/install handoff. |
| Public qualify | Source inventory, both binary hashes/raw receipt, fixtures and factory-disabled controls are checked. Root observer also supplies license/target metadata. | Acceptance entry bound to producer/observer inputs and same-artifact controls; fresh evidence. |
| Lifecycle | Staged Go consumer and current-root Python consumer are different source inputs. It expects `qualify`'s consumer directory and installed wheel. It verifies staged sources but does not reopen the wheel/raw-binary hash chain. | Explicit dependency on verified installed wheel/source bundle and both fixture origins. |

The guest builder also saves link/flags/CMake diagnostics, prepared source and
toolchain identity. These are durable reproduction evidence, distinct from
required inputs to `verify_guest`; P1-b's wrapper adds source-seam and controller
controls before source disposal. #134 must preserve or formally replace those
checks rather than silently treating the generic builder as equivalent.

## Environment, paths and caches

C2 sets `GOTOOLCHAIN=go1.26.10`, `CGO_ENABLED=0`, `GOMAXPROCS=2`, `GOWORK=off`,
empty `GOFLAGS`, task compiler/module cache paths, and usually `GOGC=50`
(`lifecycle.py` omits that override). It inherits other environment values:
`PATH`, `GOROOT`, `GOPATH`, `GOENV`, `GOEXPERIMENT`, `GOOS`, `GOARCH`, architecture
knobs, proxies/certificates/module sum settings and temporary-directory controls
are not comprehensively cleared. Go launcher availability and upstream module
acquisition remain external inputs. Host modules are pinned by `go.mod/go.sum`;
converter transitive module checksums are inside the un-fetched upstream archive.

The fixed translator uses `build_feedback.go_environment`. An inherited
`MARIAMEM_DEV_WORKSPACE` activates an ownership/checkout/cache-name check and can
conflict with C2's `temp/gomodcache` versus helper `temp/modcache`. This is a
source-identified setup gap, not a reproduced failure in this task.
`MARIAMEM_PHASE_TRACE` affects logging and must point to task-owned writable
storage. Cache misses may require network; no old compiler/module/download cache
is a unique mandatory input. Actual populated caches were not inspected.

`--workspace`/`--guest-workspace` are resolved, but C2 does not prepare ownership
receipts or all parent directories. `temp/` and `evidence/` must exist; translation,
adapter, installation and packaging outputs must be fresh. Installer requires
output outside the origin checkout and reserved namespaces. An absolute path
string is operational state; recreating the same old developer directory is not
a reproducibility requirement. New path-bound manifests necessarily get new
hashes and must retain links to their fresh inputs.

`qualify.py` expects `temp/venv/bin/python`, invokes pip with
`--no-build-isolation --no-deps`, and never provisions setuptools/wheel/PyMySQL.
The historical profile recorded Python3.14.10, PyMySQL1.2.3,
setuptools80.9.0 and wheel0.45.1; it did not record a complete immutable pip/build
lock. `-I` isolates Python imports but does not define the entire process
environment. `MARIAMEM_WHEEL_PLATFORM` must agree with generated platform metadata;
`python/deployment_target.json`, setup/license inventory, root notices/licenses
and supported macOS arm64/Ubuntu24.04 x86_64 targeting are real packaging inputs.
Python optimization flags must preserve the scripts' assertions.

## Concrete next work and remaining uncertainty

1. Define #134's exact source/observer SHAs and maintained input ownership,
   including experimental guest patches, bindings, adapter templates and public
   instrumentation. Preserve original historical proof as historical proof.
2. Acquire all locked upstream archives/modules in an isolated producer and
   record actual availability/checksums and OS/Python/Go tools. Source-only API
   checks here do not complete this step.
3. Rebuild or locate/authenticate the complete guest/linked/guest-receipt bundle;
   then produce translation/module/install/source/binary/wheel receipts together.
   The C2 summary supplies target identities, not proof these bundles still exist.
4. Create a fresh Python venv with explicit dependencies, sanitize/record effective
   environment, and make lifecycle's installed wheel dependency explicit.
5. Run the separately authorized same-candidate platform/acceptance work and
   clean its owned scratch afterward. This inventory does not authorize builds,
   acceptance, adoption or release and does not close #133/#134.

No **confirmed uniquely local-only required input** was found in this source
slice. That is not proof of absence: old guest/translation/binary/wheel bundles,
raw C2 receipts and external cache contents remain unknown outside this checkout.
No other worker workspace/cache was inspected or cleaned. Global local-only
classification and final cleanup remain #133 work after owners finish.

## Source-only verification

All 47 cited source SHA256 values matched their exact Git objects; all 22 rows
have input/classification/consumer/gap/placement fields and valid consumer line
locations. The relative report link resolves. Existing six-file raw/normalized
SHA and path-only recipe checks still pass. Full unchanged public-source guard
passes across 7617 files, and `git diff --check` passes. The four protected root
files match this worktree's input snapshot; all existing historical evidence is
unchanged. No tests of unchanged runtime, downloads, builds or CI were run.
Only this report and its JSON inventory are added; generated guard output is
removed, and workspace lifecycle stays with the coordinator.
