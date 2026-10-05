# v0.4 generated-Go default runtime

Ordinary Go `Start(ctx, Options{})` directly links the generated guest into the
consumer process; generated Go is a normal Go dependency/build input. WASM is a
build intermediate. The published v0.4.0 runtime's functional acceptance and canonical
measurements are recorded in the [integrated candidate](../benchmarks/v04-integrated-candidate.md);
the [direct-link baseline](../benchmarks/v04-direct-link-baseline.md) is the preserved pre-integration reference.

**Known v0.4 limitation:** the full generated guest is not Go `-race` clean.
The [investigation](../benchmarks/direct-link-race-scope.md) found a general shared-memory
adaptation problem, not 149 independent bugs or harmless reports. No suppression
is used. The full-guest diagnostic is not a v0.4 release gate; focused handwritten
FD/filesystem/thread/TLS/futex race tests remain enabled. The
[current roadmap](project-status.md) owns the v0.4.2 memory-contract gate and
v0.5 guest/toolchain race-census follow-up; a backing change does not settle the
broader adaptation problem.
This decision does not establish production race correctness or forced reclamation of hung
in-process execution.

## Integrated v0.4.0 fixes

Linked execution closes its host response reader after the reader joins and before
completion notification; Close releases that FD even while a closed Database or
Snapshot source handle remains retained. No finalizer/GC dependency is introduced.
Cold filesystem copying pre-sizes a private exclusive destination with existing
ftruncate, using its stable source size before the 64 KiB copy loop. Empty/sparse
contents, offsets, grow/truncate, directory identity, rename/name reuse, independent
Fork state and shutdown are verified. This is allocation reduction, not CoW or a
Snapshot format/API change. Guest source and generated artifacts are rebuilt with
pinned LLVM23/WASIX/wasm2go inputs; release/generated-go-build.json and
release/generated-go-translation.json record the new canonical input provenance.
Substantial immediate post-Close physical accounting persists independently of
live Go-object ownership. No production GC, mmap or allocator tuning is added.

## v0.4.2 memory lifecycle candidate

The accepted design scopes correctness to released pure memory32. Generic
non-wrapping effective addresses and width-aware logical bounds checks cover
scalar/SIMD/atomic accesses; atomics retain natural-alignment checks and unused
trapping loads remain observable. Root/worker guest failures become controlled
runtime errors with cooperative join.

On macOS arm64 and Ubuntu 24.04 x86_64, each instance reserves a stable 2 GiB
anonymous mapping, initially enables 256 MiB, and enables additional zero-filled
ranges before publishing logical growth. Host imports receive logical views.
Close releases the mapping exactly once after workers join; failed unmap retains
retryable ownership. No Go-heap 2 GiB backing, GC policy, CoW or Snapshot format
change is introduced. Native contract/product acceptance and bounded lifecycle
results are in the [accepted report](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md).
Final release-artifact verification is still required. Memory64 and
non-cooperative forced termination remain outside the guarantee.

## Integration contract

Architecture-decision source: `8b368a79eb3a0070f84168b1c70a1e2896e4a5ca`.
Readiness audit source: `a06773e5296be5cc3c3657e9e48785fba7bd6d25`.
Accepted architecture inputs:

| Evidence | Exact SHA |
| --- | --- |
| Wasmer v0.4 baseline | `e3224817ccfe28add8e386f7d56d425898bf644a` |
| generated-Go feasibility / final wire-tail characterization | `965da8c9d2702e6ecdd830d684e8463d31e94311` |
| pre-init CoW | `8658310fce7745c7a8df04bc0aed7d7a6ce5ce14` |
| prepared-files clone | `5676f901239c5ba4935c10061b8895216c212505` |
| ready-state reentry stop decision | `8b368a79eb3a0070f84168b1c70a1e2896e4a5ca` |

Intended model: **generated-Go execution + prepared-files reuse + fresh execution
state**. This is an integration task, not another architecture spike. All normal
SQL, transaction, auth, session, lifecycle and Snapshot/Fork behavior must remain.
No ready heap, live worker, TLS or futex-waiter restoration; no Go process fork.

## Build-time path

Pinned MariaDB/lite4mariadb sources and canonical guest overlays → pinned WASIXCC
0.4.7 / pinned LLVM23.1.0 WASM profile / WASIX sysroot / Binaryen133 → legacy-EH WASM intermediate → pinned
goccy/wasm2go fork and reproducible generator patches → generated Go → platform
ordinary Go module build input and a host-only Python wheel. v0.4.1 removed
unused encoded executable images from the normal distribution.

The legacy encoding is an internal compiler bridge. Exceptions, pthreads, shared
memory and MariaDB semantics remain enabled. Preserve the proven compatible-O2
post-link feature set; do not disable exceptions or transform exceptions to aborts.
Wasmer7.4.2 does not accept this intermediate encoding. Validation must instead
combine static WASM/import checks, generated-code compilation, reduced runtime
contract tests and observable product acceptance against the production control.
This is not same-runtime or byte-identical validation.

Required production build provenance includes input/overlay hashes, exact tool
versions and archives, compiler/linker/post-link settings, intermediate WASM hash,
converter source and patch hashes, generated source inventory, Go version/settings,
target OS/architecture and final binary checksums. Generated code is isolated from
hand-written runtime code and regenerated automatically, with no manual edits or
developer-local tools. Both macOS arm64 and Ubuntu24.04 x86_64 must be accepted.
Existing MariaDB/lite4mariadb GPL-derived obligations remain; converter, Go,
WASIX/libc, wolfSSL and other linked components require source/notices review.

## Runtime path

**generated-Go is the default v0.4 runtime. WASM changed from a runtime format to
a build intermediate.** Generated Go executes MariaDB; the WASIX compatibility
layer implements its imports. Normal startup does not discover Wasmer, consult
native bundle caches, download a bundle or verify Wasmer provenance.

```text
Build time:
MariaDB/WASIX → pinned legacy-EH WASM → pinned wasm2go → generated Go source

Go runtime:
consumer → public Go API/host → MySQL wire → directly linked generated-Go MariaDB
Python runtime:
Python API → packaged Go host process → MySQL wire → linked generated-Go MariaDB
                                                     ↓
                                        WASIX compatibility layer
                                                     ↓
                                     isolated/prepared database files
```

Go production `Start(ctx, Options{})` directly creates a generated module in the
consumer process. Generated Go is a normal Go dependency/build input. It does
not decode, write, checksum or execute an embedded native image. Python retains
one packaged host process per DB; that host directly runs its generated module,
without another guest subprocess. Python host artifact verification remains.
Execution architecture is an internal implementation detail; a child-process
failure-containment boundary is not a public API contract.

Normal shutdown joins guest workers and closes descriptors and prepared mappings.
Non-cooperative/hung execution cannot be forcibly reclaimed inside a Go process;
arbitrary worker panic/abort containment remains a separate architecture decision,
not a new guarantee. Legacy force-kill tests remain explicit Wasmer coverage.

Internal kinds are `generated-go` and `wasmer`. `Options.NativeDir` and
`MARIAMEM_NATIVE_DIR` are retained **compatibility bundle overrides**. Explicit
legacy bundles keep their existing integrity/exact-identity checks and execute
Wasmer. The earlier generated candidate bundle adapter is also retained; its
historical executable filename is not evidence of Wasmer execution. Go's
`MARIAMEM_RUNTIME=wasmer` is a development-only explicit legacy resolver selector;
empty or `generated-go` selects the default, while unknown values are errors.
An explicit NativeDir override takes precedence. No new public option was added.
Python uses an explicit bundle override or runtime/module pair for legacy use.

Each instance receives independent guest linear memory, Module/function tables,
thread agents, TLS, pthread bookkeeping, wait queues, clocks/timers, FD table,
MemFS nodes/handles/offsets and session state. Immutable prepared database files
may back private writable views. Growing files must become child-owned; closing
one child cannot unmap or invalidate another child's files. Generated code is normally linked once into the consumer. No live Go runtime object is captured or cloned.

Verification covers platform identity, compiled guest identity (plus Python host executable checksums) and
snapshot build identity, inventory and file hashes. Explicit legacy bundles retain
their module, sidecar and artifact-change verification. Existing released Wasmer
bundles remain usable through intentional selection.

## Snapshot/Fork contract

Snapshot remains cold and consumes its source after acceptance. Keep existing
active-client/transaction rejection and rollback option, destination ownership,
context behavior, integrity checks and exact guest-build compatibility.
Capture uses ordinary session drain/join and MariaDB shutdown, then committed
files export; no running heap is retained.

Fork verifies the prepared snapshot and creates private writable file state,
then initializes a fresh generated guest against that state. The child does not
inherit live connections or transactions. Concurrent Fork and snapshot Close
retain the current ownership/read-lock contract. Prepared-file mapping must not
bypass Snapshot validation or change the build mismatch policy.

## Acceptance order

First reproduce all v0.3 behavior through unchanged workloads. The previously found Aria
schema-discovery issue is covered by passing GORM32 acceptance: do not use checkfirst=False or
change GORM AutoMigrate to pass. Audit generated runtime contracts before moving
shims into production. Then establish reproducible build and platform acceptance,
bounded failure/cleanup behavior, and canonical public-boundary measurements.
Benchmark only after correctness passes; retain the legal InnoDB ~1-second tail.

If an existing feature cannot be implemented correctly with bounded changes,
record the concrete discrepancy and stop integration. Keep the selected path
disabled, avoid incomplete product benchmarks and report NOT READY.

## Historical integration evidence

The following records pre-release integration gates and selection bridges.
[Project status](project-status.md) owns the published milestone and next decisions.

The opened-directory FD identity and quadratic MemFS Snapshot growth gates are
fixed and regression-tested in the selected local candidate. SQLAlchemy/GORM,
SQL/transactions/sessions/Snapshot/Fork and local cleanup checks pass. The earlier
failed gates remain historical evidence in the candidate report. This does not
replace platform release acceptance. The default runtime has now migrated;
release/distribution cleanup remains a separate task.

### FD follow-up from 023796b9

The opened-directory identity gate is now fixed in the isolated shim. Relative
resolution retains a MemFS node and opens under the tree mutex; parent links
follow rename and unlinked objects remain descriptor-owned. Pathname reuse
cannot rebind an already opened directory. Close/dup/reuse includes the preopen
entry. The same deterministic rename gate fails before and passes after the fix.

Integration has resumed with a **selected local production-like candidate**.
`setup_candidate.py` validates the accepted generated Go/assembly inventory,
applies bounded adaptations automatically, binds the compiled guest to its input
module SHA256, builds the existing host and records provenance/checksums.
Prepared cold files use independent MemFS nodes and MAP_PRIVATE views; new guest
execution state is built each time. Join every worker before releasing mappings.
No diagnostic I/O overhead, Wasmer execution, ready heap or live state cloning is
included. The historical runtime filename is retained only for selection by the
unchanged local bundle resolver; manifest runtime_kind labels the candidate.

The generated source is now isolated under `internal/generatedgo` and selected
by default. Source-to-WASM and generated source reproducibility are recorded in
[v04 guest reproducibility](v04-guest-reproducibility.md). Generated-source build cost is documented separately; normal startup no longer
provisions images. Source/notices/provenance and exact-byte Ubuntu/macOS15
acceptance remain release gates. Local regression/benchmark evidence does not replace them. See the updated
candidate report for public-boundary measurements and observed regressions.

## Historical release preparation audit

[The infrastructure/docs/test audit](v04-integration-audit.md) records retained
API options, intended artifact migration, verification tiers and actual build/CI
gaps. NativeDir remains a compatibility override; ordinary v0.4 zero setup is
delivered by direct-linked Go and a host-only Python wheel, without a local
runtime directory. Do not remove Wasmer fallback/trust
mechanisms before their replacements and both-platform acceptance pass.

The source-build reproducibility recipe and exact toolchain/input pins are in
[guest reproducibility](v04-guest-reproducibility.md). This supersedes the earlier
LLVM21 candidate build bridge; historical artifact pins remain explicit.


## Default build and regeneration

The current Release CI contract is [generated-go-v1](releasing.md). On a fresh
Linux arm64 build runner, `build_generated_guest.py` checksum-verifies downloaded
tools and performs two independent source builds against the canonical guest
identity. `regenerate_release_guest.py` repeats translation/adaptation/import in
a disposable tree and compares every file with `internal/generatedgo`.

```sh
# Fresh canonical build host only; fixed /work and SDK locations must be empty.
sudo -E "$(command -v python3)" scripts/build_generated_guest.py --repetitions 2
# With transferred build/generated-release inputs on a Go1.26.8 builder:
python3 scripts/regenerate_release_guest.py
python3 scripts/verify_generated_runtime.py
python3 scripts/build_alpha.py --ci-candidate
```

`release/generated-go-toolchain.json` pins tools/downloads;
`release/generated-go-inputs.json` pins source/assembly/data inputs;
`internal/generatedgo/provenance.json` pins resulting source. Generated code is
intentionally committed and is normal consumer build input. Generator patches
and bounded shim adaptations are applied automatically, never by manual edits.
The historical image verifier remains in normal checks while old encoded assets
are retained; **image regeneration is not part of the v0.4 default release path**.

The generated pure function packages retain dead structured-control fallthrough
from the translator. `scripts/vet_generated.py` inspects each vet configuration, including dependency
packages. Normal verification runs all vet analyzers except
`unreachable` **only on `code/pN` generated functions**; handwritten API, host,
WASIX/base shims and lifecycle code retain full vet. Generated code is compiled,
checksum-verified and functionally exercised. Ordinary direct `go vet ./...`
reports those translator diagnostics; the scoped canonical check makes this
explicit rather than hiding other findings.

Canonical guest generation is Go1.26.8. A local Go1.27.1 compiler failed in the
large arm64 pure function package (LDPSW offset handling); do not silently change
the build compiler. Ordinary consumers compile the generated packages as normal Go dependencies;
Go1.27.0/1.27.1 arm64 are unsupported, as documented below.

## Packaging follow-up

The Go source set retains generated source and two historical encoded images.
Normal consumers direct-link generated Go; **no DB expands or spawns an image**.
Encoded assets and their verifier/provisioner remain later cleanup candidates.
Python's default host-only wheel contains neither Wasmer nor runtime WASM/AOT.
The migrated Release CI verifies the current source/module and host-only wheels;
legacy native resolver/cache/packaging and Wasmer notices remain isolated for
fallback. No license obligation is considered removed.

## Go toolchain support and regeneration

Go 1.26.0/1.26.8 and upstream-fixed Go tip build the unchanged canonical generated
source. **Go 1.27.0 and 1.27.1 on arm64 are unsupported**, due to upstream compiler
regression [golang/go#81036](https://github.com/golang/go/issues/81036). Upstream fix
`b3f5034b15a7a6f065e92d0617f7a473d5d9dcfa` was tested in both the reduced reproducer
and the real direct-link consumer. No mariamem-side compiler/generated-code
workaround is used. Toolchains containing that fix are expected to work; see the
[consumer measurements](../benchmarks/direct-link-consumer-experience.md).

`runtime_instance.go` and `code/base/runtime_cleanup.go` are handwritten,
version-controlled ownership adapters, outside the unchanged WASM-transpilation
inventory. Regeneration copies these ordinary source files automatically. Guest,
converter, pins and generated provenance hashes remain unchanged.

## Distribution and legacy consolidation

The accepted v0.4.1 distribution candidate removes the unreferenced
`internal/builtinruntime` package and image-only metadata/provisioning. Normal
generated code and Python host-only packaging are preserved. Diagnostic guest
CLI/spawn scaffolding and intentionally supported legacy bundle/cache machinery
are separate. The [current roadmap](project-status.md) keeps distribution polish
in v0.4.1, lifecycle work in v0.4.2 and conditional legacy retirement in v0.4.3;
this architecture record does not authorize broader removal.
