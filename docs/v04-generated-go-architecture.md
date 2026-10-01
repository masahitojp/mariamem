# v0.4 generated-Go default runtime

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
guest executable, host-only Python wheel and checksum-bound Go images.

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
MariaDB/WASIX → pinned legacy-EH WASM → pinned wasm2go → generated Go → executables

Runtime:
Go Options{} → in-process host → dedicated built-in generated guest child
Python start() → packaged Go host → fresh generated guest child
MySQL client → host wire endpoint → guest protocol → generated-Go MariaDB
                                                   ↓
                                      WASIX compatibility layer
                                                   ↓
                                 isolated/prepared database files
```

Go carries both supported platform executables as compressed text images.
`internal/builtinruntime` expands only the matching image into the database's
private temporary directory, checks the complete executable SHA256 and removes
it on close/failure. No user cache or download is needed. It executes a dedicated
mariamem guest, **never the consumer executable**, so consumer init functions are
not rerun. The materialization and new-executable launch costs belong in public
Start/Fork measurements; see the default-migration sanity report.

The Python wheel contains the host executable and its manifest, with generated
MariaDB linked into the host. Its owned command dispatches an internal guest
entry in a fresh child. Host-only manifest checksum/platform verification remains
required; no external Wasmer/WASM/AOT payload is needed. Build-time WASM identity
is compiled into both endpoints and remains the Snapshot compatibility identity.

Internal kinds are `generated-go` and `wasmer`. `Options.NativeDir` and
`MARIAMEM_NATIVE_DIR` are retained **compatibility bundle overrides**. Explicit
legacy bundles keep their existing integrity/exact-identity checks and execute
Wasmer. The earlier generated candidate bundle adapter is also retained; its
historical executable filename is not evidence of Wasmer execution. Go's
`MARIAMEM_RUNTIME=wasmer` is a development-only explicit legacy resolver selector;
empty or `generated-go` selects the default, while unknown values are errors.
An explicit NativeDir override takes precedence. No new public option was added.
Python uses an explicit bundle override or runtime/module pair for legacy use.

Each child receives independent guest linear memory, Module/function tables,
thread agents, TLS, pthread bookkeeping, wait queues, clocks/timers, FD table,
MemFS nodes/handles/offsets and session state. Immutable prepared database files
may back private writable views. Growing files must become child-owned; closing
one child cannot unmap or invalidate another child's files. Code pages use normal
OS executable sharing. No live Go runtime object is captured or cloned.

Verification covers platform identity, compiled guest/executable checksums and
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

First reproduce all v0.3 behavior through unchanged workloads. The deferred Aria
schema-discovery issue is a compatibility gate: do not use checkfirst=False or
change GORM AutoMigrate to pass. Audit generated runtime contracts before moving
shims into production. Then establish reproducible build and platform acceptance,
bounded failure/cleanup behavior, and canonical public-boundary measurements.
Benchmark only after correctness passes; retain the legal InnoDB ~1-second tail.

If an existing feature cannot be implemented correctly with bounded changes,
record the concrete discrepancy and stop integration. Keep the selected path
disabled, avoid incomplete product benchmarks and report NOT READY.

## Current integration state

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
[v04 guest reproducibility](v04-guest-reproducibility.md). Distribution size and
Go image-provisioning cost, comprehensive WASIX hardening, licensing/source
review and exact-byte Ubuntu/macOS15 acceptance remain release gates. Local regression/benchmark evidence does not replace them. See the updated
candidate report for public-boundary measurements and observed regressions.

## Release preparation audit

[The infrastructure/docs/test audit](v04-integration-audit.md) records retained
API options, intended artifact migration, verification tiers and actual build/CI
gaps. NativeDir remains a compatibility override; ordinary v0.4 zero setup must
be delivered by a runtime-kind-aware exact-version distribution rather than
requiring users to choose a local directory. Do not remove Wasmer fallback/trust
mechanisms before their replacements and both-platform acceptance pass.

The source-build reproducibility recipe and exact toolchain/input pins are in
[guest reproducibility](v04-guest-reproducibility.md). This supersedes the earlier
LLVM21 candidate build bridge; historical artifact pins remain explicit.


## Default build and regeneration

First run the pinned source/translation/candidate commands in
[v04 guest reproducibility](v04-guest-reproducibility.md). Then:

```sh
python3 scripts/generate_runtime.py --source-module /work/candidate/module --output /work/imported-runtime
# Compare /work/imported-runtime to internal/generatedgo; replace the latter only
# after the script's pinned inventory check succeeds.
python3 scripts/embed_generated_runtime.py --work-dir /work/platform-images
python3 scripts/verify_generated_runtime.py
python3 scripts/build_alpha.py
```

`generate_runtime.py` performs the package/import/data and owned-entry conversion
without manual patches. `release/generated-go-inputs.json` pins all candidate
Go/assembly/data inputs; `internal/generatedgo/provenance.json` pins the resulting
source. The generated source is intentionally committed. Image generation uses
Go1.26.8, CGO disabled, trimmed paths, no VCS embedding, sequential compilation to bound developer/CI memory, baseline target CPU flags
and no user GOENV/GOFLAGS/GOEXPERIMENT/GOWORK overrides. Its provenance records
both uncompressed executables, encoded sources and Python/zlib versions.
Changing a pin requires regeneration and product acceptance, never a checksum
exception. The image verifier is part of normal `scripts/verify.py check`.

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
the build compiler. Ordinary consumers execute the pinned image and do not compile
that generated package unless they build the developer host/guest commands.

## Packaging follow-up

The Go module source set is about 326 MiB, below Go's 500 MiB uncompressed module
zip limit, but includes generated source and both platform images. Each database
currently expands its own image. A distribution/provisioning follow-up must
address this cost with explicit trust, ownership and cleanup; this task adds no
shared runtime, ready heap or cache. Python's default host-only wheel contains
neither Wasmer nor a runtime WASM/AOT payload. Explicit legacy packaging commands,
old native resolver/cache, release CI native-bundle assumptions and Wasmer notices
remain for fallback/release migration. No license obligation is considered removed.
