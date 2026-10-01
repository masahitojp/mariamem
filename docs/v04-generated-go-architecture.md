# v0.4 generated-Go runtime candidate

## Integration contract

Source HEAD: `8b368a79eb3a0070f84168b1c70a1e2896e4a5ca`.
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
0.4.7 / LLVM21 / WASIX sysroot / Binaryen133 → legacy-EH WASM intermediate → pinned
goccy/wasm2go fork and reproducible generator patches → generated Go → platform
guest executable, host executable and metadata bundle.

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

Public Go `Start(ctx, Options{})` / Python Database start → exact-release bundle
resolution and per-start verification → existing mariamem host → isolated
generated-Go guest subprocess → fresh MariaDB → existing MySQL-wire endpoint.
The generated guest executable replaces Wasmer in the selected bundle. Retain
the subprocess boundary for cancellation, traps, bounded forced teardown and
Python ownership; no Wasmer interpreter or AOT loader is involved.

Each child receives independent guest linear memory, Module/function tables,
thread agents, TLS, pthread bookkeeping, wait queues, clocks/timers, FD table,
MemFS nodes/handles/offsets and session state. Immutable prepared database files
may back private writable views. Growing files must become child-owned; closing
one child cannot unmap or invalidate another child's files. Code pages use normal
OS executable sharing. No live Go runtime object is captured or cloned.

Verification continues to cover platform identity, executable/module metadata,
checksums, artifact change identity, snapshot build identity, inventory and file
hashes. An experimental argv adapter alone does not satisfy this trust contract.
Do not enable the generated path by default until its build and acceptance gates
pass. Existing released Wasmer bundles remain usable during integration.

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

## Current integration gate

The compatibility preflight and its stop decision are recorded in
[the candidate gate report](../benchmarks/v04-generated-go-candidate.md).
The diagnostic Aria/readlink/relative-FD fixes pass ordinary ORM cases but fail
an opened-directory identity contract under rename/path reuse. They are not
production shims. No generated runtime has been selected or enabled in the
product. Production regeneration/provenance, bundle binding and platform/failure
acceptance remain prerequisites after resolving that gate.
