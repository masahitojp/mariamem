# Issue65 step3C — first real WASIX link

**Build/link PASS; recommend isolated Go translation and byte-mux execution next.**
The product-baseline embedded library and native memory-Vio entry compile and
link together under the pinned LLVM23/legacy-EH recipe. Postoptimization succeeds;
all64 import items have names supported by the current host declarations/methods.
No new host shim was added. This completes the authorized first build/link step,
not3C's endpoint execution,3D, product adoption or a release.

The strongest limitation is unexecuted lifecycle behavior. Fourteen existing
fail-closed imports remain declared, and the native controller still co-locates
host-like I/O/timer duties for this experiment. The actual Go byte/control mux,
per-instance identity, cancellation, cross-DB failure isolation and joins must be
proved before this can replace the product path. Static import ownership does
not establish ABI correctness or whether a panic stub is reachable.

## Exact result

- Build source_commit: **924363e76f8f7a4435a0b2968787d954d4ac29c0**.
  Reports/inventory tooling committed afterward do not relabel that build SHA.
- Starting preflight source_commit:5ccdc92f22a922e68b01767fe09c8fd615f36bd9.
  MariaDB12.3.3 source_commit:83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e.
- Postoptimized guest:18,446,451 bytes;
  SHA256 **df958353fe10d0368de73d3d20737576b6c288afc3039b28ed9d2847b191135c**.
- Linked guest:21,925,038 bytes;
  SHA256 dc99a350719ef8dc3a469d79c880aee23b719eadb8d4172a7483d404e68df3e4.
- Existing scripts/build_generated_guest.py --development-output produced
  contract=development-unqualified-v1, result=UNQUALIFIED, one repetition.
  [Full build receipt](evidence/guest.json) binds source inventory, prepared
  files, checked archives, actual tool versions and outputs. No release guards
  were relaxed, no canonical guest hash was changed and no output was installed.
- Actual compile/link took428.14s; postoptimization18.71s. LLVM preparation took
  176.99s and source preparation121.99s. These diagnostic phase durations exclude
  initial download/other setup and are not a benchmark or a future build promise.
  [Phase records](evidence/phases.jsonl) retain their resource-attribution limits.

Budget was2h active from2026-11-05 13:51 UTC, tooling30min, heavy CI0,
owned12GiB/free floor12GiB. No heavy CI was submitted. Observed workspace
snapshots peaked around5.4GiB, not a precise continuous peak measurement.
Downloads/setup/compile waiting are included in the wall timeline rather than
invented as measured active engineering time. Completed scratch is disposable.

## Source and build boundary

The Human selected the first real3C build after the
[preflight](../issue65-wasix-preflight/README.md) and host/guest role discussion.
The two EOF conflicts were resolved by retaining the product's parameter-metadata
helpers and the3B native include/counter. guest/experimental.patch is now a delta
from the actual product preparation baseline, not pristine MariaDB. Canonical
guest/source.patch and product Go/runtime/generated code are unchanged.

The product's original C translation unit remains, with its old resident main
renamed only for that file. The new C++ main calls a fresh-only C bootstrap:
normal boot-mode validation, bundled auth-key setup, l4m_open, actual auth-key
readiness and routine_bootstrap. It closes the bootstrap MYSQL before admitting
native sessions. Product InnoDB/Aria build settings remain; this is not3B's minimal
native MEMORY-only library. Restore/capture is intentionally not implemented by
this new entry. Legacy C API exports/code are retained in the module; code removal
or a minimal production extraction is not claimed.

The3B C++ queue/gate controller is reused as a build fixture, with Linux
execinfo/backtrace/signal diagnostics removed. Embedded BIND and routine checks
are compiled but **not executed** in this task. This is not approval to keep all
transport, timers and host-like policy in guest C++. Final Go placement remains
as discussed: host owns byte transport/management; guest keeps authoritative
admission, engine state and cooperative cancellation/cleanup.

The generated [compile flags](evidence/compile-flags/) confirm
MARIAMEM_NATIVE_WIRE for sql_embedded, mysqlserver and the entry, and
EMBEDDED_LIBRARY on the relevant embedded targets. The C entry's main rename and
exact C++ source bytes were checked before successful build cleanup.
[Flag verification](evidence/coherent-flags.json) records those observations.
Normal preparation, instrumentation, auth hooks and routine-schema generation
all completed through the existing script. The existing host allocator-contract
control also passed; it is not a real WASIX OOM or runtime acceptance result.

Builder base image was fixed at
sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f,
CPU3/memory6GiB/pids512, with empty mounted /root and /work. Its preinstalled
LLVM21 SDK was hidden; the script installed checked LLVM23.1.0, wasixcc0.4.7,
legacy-EH sysroots, Binaryen133 and ICU using the unmodified toolchain pins.
SDK, /work and downloads were inside the owned workspace for accounting/cleanup.

## Actual module inventory and limits

[Inventory](evidence/module-inventory.json) retains64 import declarations,
4,974 exports, TLS global mappings, tags and static section counts. Shared memory
has4096 initial pages and32768 maximum pages (256MiB/2GiB). __tls_base, __tls_size,
__tls_align, __wasm_init_tls and wasi_thread_start are present. The module contains
21,745 defined functions and3 data segments. Legacy try/catch/rethrow expressions
are present; try_table and throw_ref counts are zero. Counts are static, not
runtime frequencies, reachability or converter acceptance.

The14 declared panic methods remain fd_dup2, thread_signal, proc_exit2,
sock_addr_local/peer, sock_open, sock_set_opt_flag/time/size, sock_get_opt_size,
sock_bind/connect/send_to and resolve. No stub was made silently successful.
WASM generation used the existing Binaryen validation/postoptimization path;
there was no wasm2go translation, Go binary, SQL execution, real socket or new
runtime test campaign in this build/link task.

The PID-derived epoch inherited from3B is a concrete porting limitation: current
host Proc_id returns os.Getpid(), so independent DBs in one Go process would not
get distinct instance epochs this way. Supply and validate a per-instance identity
in the Go/guest control setup before cross-DB/stale-message acceptance. This is a
source-based finding, not a demonstrated cross-DB runtime failure. The private
pipes still separate the current fixture channels; they do not establish the
design's independent epoch invariant. Outer-pipe failure still exits the fixture
with80 and needs real Go cancellation/ownership proof.

## Reproduction and next work

Check out build source924363e7 and verify it with scripts/git_identity.py. The
committed experimental.patch is complete; prepare.py documents its generation
from the preflight product files but is not an extra required build stage.
Use a fresh Linux/arm64 builder with the system build dependencies and bind an
owned empty directory at /root and another at /work. Mount source separately;
its linked Git metadata must be readable at the recorded paths. Keep everything
under the12GiB workspace guard and a12GiB free floor.

Run scripts/build_generated_guest.py --development-output `<external-scratch>/artifact`.
It verifies clean source, fresh work/SDK, locked archives and source identity
before/after. Preserve the UNQUALIFIED receipt, prepared-source record, build
logs and library/entry flags before removing build trees. Do not select a release
operation or install generated output into internal/generatedgo.

Disassemble the exact postoptimized module with the same Binaryen wasm-dis,
writing `<workspace>/temp/module.wat`; run inventory.py `<workspace>` while the
artifact is at temp/artifact. This inventory helper is a later report tool;
its source SHA is not substituted for the artifact's original build identity.

Next recommendation: a separately bounded2h/CI0 isolated translation and minimal
Go byte/control mux attempt, initially with12GiB scratch/free floor12GiB. This is
a proposed planning allowance, not measured campaign cost or an action started
here. Use the pinned patched converter and Go1.26.10. First observe fresh
bootstrap/greeting/login/SELECT/prepared, then blocked output/partial input/SLEEP
cancel and actual joins. Fix per-instance identity before isolation/stale-message
checks. Keep host I/O processing independent of a stalled client and preserve
fatal original-cause reporting. No cgo or second MySQL server decoder is implied.
Only after that execution evidence should3D's stopped-root storage/Snapshot/Fork/
Live campaign be selected. Existing fatal-wire diagnostics, malformed-string and
aggregate-result policy choices remain separate adoption conditions.
