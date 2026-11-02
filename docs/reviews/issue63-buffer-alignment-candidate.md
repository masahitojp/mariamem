# Issue63 scoped source candidate — implementation checkpoint

2026-11-02. Human authorized v0.7.0 milestone update followed by Issue63.
Branch: `experiment/buffer-alignment-source`.
Baseline source_commit: `c4742390cf4553636ceaa23c6732d48f76a37c9c` (main).
MariaDB source_commit: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
The unchanged accepted guest is `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
This checkpoint is not product adoption or a performance PASS.

The [prior source plan](https://github.com/masahitojp/mariamem/blob/2cb902610b1a5b423a71a59222e5ff793d81dfd8/docs/reviews/issue63-buffer-alignment-source-plan.md)
remains the design basis. `guest/experimental.patch` changes only
`mysys/my_largepage.c`, `include/my_sys.h` and `storage/innobase/buf/buf0buf.cc`.
The WASM-only internal helper accepts alignment and retains zero-fill and
NULL-on-failure. The old entry delegates with4096; pool reserve supplies its
existing extent constant. Non-WASM reserve/retry/commit/free remain intact.
No canonical guest patch, accepted generated input or release ledger is changed.

## Finite first execution

Decision: can the exact source implementation preserve the allocation contract
and remove the known retry through the normal guest/converter path?
Initial budget:2 hours active work including30 minutes tooling, at most2 heavy
CI submissions. The first local single-pass guest build has a2700-second timeout;
download/build wait is recorded separately. Workspace budget24GiB, reserve16GiB.
Only this workspace and its named container are owned by this task.
Existing image `mariamem-wasix-build:0.4.7` is the prerequisite package layer
(image ID `sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f`).
Its old SDK is hidden by a fresh task-owned `/root`; the existing builder obtains
and hash-checks LLVM23/wasixcc/sysroots/Binaryen from the unchanged pinned manifest.
The observed Docker allocation is8CPUs/~7.75GiB RAM; guest compile jobs remain3.

The first exit is one guest build and, if successful within budget, normal Go
regeneration/host smoke. Unexpected allocator redesign or build failure consumes
the same budget. A failure/incomplete result is reportable without widening scope.
The four-metric performance comparison and platform adoption checks remain work
after this checkpoint; no old overlay receipt will be relabelled.

## Confirmed before guest build

The six source files match the prior hash receipt. The adopted portability patch
is applied before the experimental patch. The unchanged WASM virtual-memory
reserve still delegates to the legacy allocator and release still calls free.

`python3 benchmarks/bufferalignmentsource/check.py --source <prepared-source> --output <receipt>`
compiles the exact new helper and the selected old WASM entry, exercises dirty
backing memory, sizes1/4095/4096/(2MiB±1)/2MiB/16MiB, both alignments, unchanged
size, one allocation, controlled ENOMEM and original-pointer free. C/C++ symbol
linkage also passes. Four mutations (missing zeroing, wrong alignment, size
mutation and changed legacy alignment) are rejected. This is a host-compiled
contract check, not real WASIX OOM, full-header compilation, pool behavior or
whole-guest safety. The initial C++ probe used a missing local `<cstdlib>` header;
it was narrowed to `<stdlib.h>`, sufficient for this C-linkage probe, and rerun.

Actual WASIX allocation failure, allocator padding/resource effects, normal guest
build/regeneration, single pool zero-fill, SQL/Fork isolation, cleanup and common
performance metrics are not yet verified. Numerical improvement/regression
margins remain undecided; this checkpoint does not claim an adoption gate PASS.

## Source guest built; development binding checkpoint

The single source build completed in989.55s (including acquisition/preparation),
producing UNQUALIFIED guest `96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`
from source_commit `d86153409067e6ad868b566872a3c4a9495ef5f7`.
All four relevant prepared C/C++ source hashes match the host contract receipt.
Initial native translation succeeded but installation correctly refused the new
guest at the canonical worker-allocation identity guard. This FAIL is retained.

The experimental development route now selects `tests/issue63_install_dev.py`
only for that exact guest. It first verifies Fn153/Fn131/Fn214 against all three
existing whole-function hashes, then binds that exact guest within the installer
process. Existing inventory, body, Module/yield and runtime-adapter checks run
unchanged; canonical `runtime_thread_lifetime.py` and release inputs are untouched.
The host-stage difference is only `scripts/dev_guest.py`, tests and this document,
which the existing origin-reuse policy verifies against the immutable old commit.
This is an experimental binding, not approval of a new canonical guest ABI.
Five adapter controls plus the existing binding/dev-tool tests pass46 total.
Native smoke and performance have not passed at this checkpoint.

## Finite comparison completed — experimental, adoption inconclusive

The rebound native pipeline and real SQL/Snapshot/Fork/Close smoke PASS.
[Matched results and exact source identities](../../benchmarks/buffer-alignment-source.md)
retain five alternating pairs for serial Fork/held RSS and separate P8/P4 batches.
RSS decreases in all pairs; wall/CPU/batch effects conflict. The zero-fill pilot
confirms the duplicate large clear is removed in every observed child.
The missing queue field means overall four-field adoption remains INCONCLUSIVE.
No extra repetitions or new optimization candidates were added to force a PASS.
Ubuntu/real-WASIX-OOM/canonical adoption remain outside this completed checkpoint.
