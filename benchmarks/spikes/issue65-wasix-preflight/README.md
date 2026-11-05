# Issue65 step3C — WASIX preflight

**Preflight complete; recommend a bounded canonical build/link attempt next.**
The small WASIX module links and validates with existing callback/thread/wait
facilities, and the product/native patch overlap is limited to two independent
EOF additions. No new import name was identified by this small probe. This is
sufficient to justify trying the real build, not evidence that the MariaDB
endpoint runs under generated-Go.

The strongest objection is that the available compiler is LLVM21 while the
canonical build requires LLVM23, and no full engine module was built or executed.
Two linked signal/exit imports are still intentionally fail-closed. Native3B
success cannot establish that the larger WASIX module avoids those paths or
that guest cancellation and joins work. Keep unsupported paths fail-closed;
implement a shim only after an actual reachable failure establishes its need.

## Scope and identity

The Human selected the next step after [3B](../issue65-native-control/README.md),
whose recommendation was this preflight, under the
[3C plan](../../../docs/design/issue65-native-protocol/README.md). This task does
not include a full guest rebuild, endpoint implementation,3D, adoption or release.

Starting source_commit:4c642b3206af309f928a1ce51871ba1f4ba83001.
MariaDB12.3.3 source_commit:83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e.
[Identity](evidence/source-identity.json), [source/recipe/patch hashes](evidence/overlay.json)
and [small module/source hashes](evidence/primitives.json) bind the observations.
The compared guest inputs/patches, preparation/build scripts, toolchain pin and
host import methods match published0.6.2 source_commit
47121e1be0b399ba4e2270ce3e25c411ade0e2eb. The experimental patch is separate.
No tag object was substituted for a source commit.

Budget:2h active from2026-11-05 06:36 UTC; measurement tooling30min; heavy CI0;
owned6GiB/free floor8GiB. No heavy job was submitted. Only selected pinned source
files were extracted for composition; this is deliberately not a complete
prepared source tree. The small compiler containers were CPU2/memory2GiB and
bounded at120s (diagnostic control60s). Source assessment was disk-guarded.
All source and binary observations precede cleanup; generated artifacts are
reproducible and removed, with hashes and selected WAT retained.

## Observed checks

| Boundary | Observation | Limit |
| --- | --- | --- |
| Existing compiler | Fixed image contains wasixcc0.4.7, LLVM21.1.2, Binaryen133, legacy-EH sysroot | Official generated-Go recipe pins LLVM23.1.0 and checked archives; this image is not a canonical builder |
| Primitive compile/link | std::thread, mutex, condition_variable, steady_clock deadline and callback compile/link into shared-memory legacy-EH WASM | No MariaDB or WASM execution |
| Callback lowering | Exported non-inlined probe_callback retains call_indirect; [WAT](evidence/callback.wat) records it | Function-table execution/converter behavior not tested |
| Static validation | Binaryen reads/validates/writes the linked module successfully | Warning about no optimization passes is expected; no Go translation |
| Import names |21 import items, all have existing owners; [inventory](evidence/primitives.json) lists signatures and owner methods | Name/owner audit is not ABI or runtime reachability acceptance |
| Patch stack | Direct application fails3 hunks across lib_sql.cc and sql_prepare.cc;3-way merge leaves one conflict per file | Original failure retained in stack-dry-run.txt |
| Composition draft | Preserve product parameter-metadata helpers, then append the3B include/counter; resulting14-path delta applies without fuzz | Uncompiled draft, not installed as guest/experimental.patch |
| Product preservation | Both metadata helper blocks retained byte-for-byte; TIME width and unsigned-BIND corrections present; other selected product files unchanged | Static preservation does not establish runtime prepared compatibility |
| Native diagnostics | Including execinfo.h fails in WASIX (expected diagnostic control) | The Linux backtrace handler must be excluded/replaced before compiling3B's driver |

The exact existing image is
sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f.
[Compiler logs](evidence/primitives-build-final.txt) and
[diagnostic/sysroot hashes](evidence/diagnostics-final.txt) preserve actual tools.
Canonical pins remain in release/generated-go-toolchain.json. Local Go1.27.3 was
observed but not used to build/execute anything; the canonical route pins1.26.10.

The import inventory includes shared env.memory and wasi.thread-spawn as special
existing facilities. Futex_wait/wake/wake_all, Thread_exit and Thread_parallelism
already have handwritten host methods; WASI clocks, stdio and poll also have
existing implementations with finite semantic limits. Thread_signal and
Proc_exit2 are linked and remain explicit panic stubs. Static imports do not
prove either is called on this probe's normal path. No new shim was added and
no signal stub was made silently successful.

## Concrete port work

1. **Compose source on the product baseline.** The native3B patch is a delta from
   pristine upstream; scripts/prepare_guest.py applies it after portability,
   prepared and canonical overlays. It therefore cannot be reused unchanged.
   [Draft](evidence/composed-draft.patch), [original conflict excerpts](evidence/conflicts/)
   and [verification](evidence/composition-verification.json) preserve a bounded
   rebase candidate. Both conflicts are independent EOF additions, not competing
   changes to metadata semantics. Keep canonical guest/source.patch unchanged.
2. **Compile one coherent mode.** Propagate MARIAMEM_NATIVE_WIRE to all required
   embedded C++ translation units, not only the final executable. Existing
   wasm/CMakeLists.txt builds a C lite4mariadb/resident entry and exports the old
   APIs; the new memory-Vio entry needs a separate C++ resident driver/target and
   explicit exports. Merely linking control.cc with the old target will not
   replace the old resident loop. Product bootstrap must run before native READY.
3. **Port the3B driver deliberately.** Its execinfo/backtrace/SIGSEGV diagnostics
   are Linux-only. Do not turn them into a fake WASIX backtrace shim. Native
   filesystem paths, embedded-library link flags and minimal MEMORY-engine
   bootstrap are also fixture details, not the product startup/restore contract.
   Its queues/gate/lease/ACK/retirement design can be reused; its portability and
   failure paths still need a real compiler/runtime test.
4. **Keep Go as a byte owner.** internal/guest/linked.go already connects os.Pipe
   to generatedgo.StartInstance's io.Reader/io.Writer. Reuse that execution/I/O
   boundary, but the existing guest.Process response reader expects JSON APIv2;
   it cannot parse the new private binary mux. Add a separate thin mux consumer,
   output-credit and control pump; do not route raw packets through the old
   Query/response decoder. No cgo or guest OS socket listener is implied.
5. **Retain lifecycle ownership.** runtime_instance.go reports worker failure
   early, joins through executeGuest/WaitThreads, then releases descriptors,
   prepared mappings and memory. The new coordinator must wake its I/O waits
   before waiting for that join. The3B prototype's outer-pipe write failure exits80;
   that is not a Go ownership solution. A blocked/non-cooperative worker still
   owns resources until it exits. Capture must remain after complete joins.

The inspected THD::awake_no_mutex/abort_current_cond_wait body sets killed state,
optionally shuts down Vio, calls scheduler/storage hooks and broadcasts the
registered condition variable. It contains no direct pthread_kill call. This
supports trying existing futex/condition primitives first; it does not prove that
every scheduler/engine callback avoids signal imports. SLEEP, partial-input and
blocked-output cancellation must be repeated in the actual WASIX endpoint.

## Next bounded attempt and stopping conditions

Recommend the first **real3C build/link attempt**, planning allowance2 active
hours, tooling30min, heavy CI0, owned12GiB/free floor12GiB. This is an estimate
and proposed budget, not measured build cost or a build started by this preflight.
It includes source/glue adaptation and one canonical compile/link attempt; an
artifact within that allowance is not promised. A fresh compiler setup may
consume most of it. Cost of a complete SQL/Go campaign is still unknown.

Use the checked LLVM23/legacy-EH/wasixcc0.4.7/Binaryen133 archives and existing
UNQUALIFIED development route, keeping SDK, /work, downloads and Go caches in
owned mounted scratch. scripts/build_generated_guest.py requires fresh /work
and absent /root/.wasixcc; the old image with its preinstalled SDK cannot be
passed off as satisfying that recipe. Do not bypass cleanliness, input hashes,
release guards or install output into internal/generatedgo.

First target: a coherent linked module from the rebased source, with source,
flags, import/export/TLS/memory inventory and the original first failure retained.
If a stub/import or linker error blocks it, reduce that exact path before adding
an implementation. If the bounded attempt expires, report the first remaining
failure and a new estimate; do not call3C complete or spend an unbounded campaign.
After link succeeds, use the pinned patched converter in an isolated module,
then validate greeting/login/SELECT/prepared and real input/output/SLEEP failure
joins through the new Go byte mux. That execution evidence, not this preflight,
is the3C exit condition.3D's stopped-root storage and Snapshot/Fork/Live acceptance
remain later work. Fatal-cause delivery, malformed-string semantics and aggregate
result bounds remain the design's separate adoption choices.

## Reproduction

From the retained experiment source, prepare an owned workspace and verify its
commit with scripts/git_identity.py. Set6GiB/8GiB budgets for this small preflight.

- Run overlay.py --workspace `<workspace>` (Python3.12+). It downloads/verifies only
  the pinned MariaDB and lite4mariadb recipe archives, extracts selected files,
  checks exact product patch pre/postimages and emits the original stack failure,
  EOF conflicts and uncompiled composition draft. Use a fresh temp directory.
- Bind that workspace as /exp in the exact image above, then run compile.sh.
  It builds only primitives.cc, uses legacy EH and preserves a non-inlined
  callback. Run inventory.py --workspace `<workspace>` afterward for static owners.
- Run diagnostics.sh in the same image. Its captured compiler exit1 is the
  expected negative control; the script also prints actual tool/library hashes.
- Apply the draft to a copy of the selected product files with patch --fuzz=0;
  compare all14 hashes with overlay.json. Preserve product metadata helpers and
  the canonical prepared anchors, as recorded in composition-verification.json.

The original controls, source identities and draft are compact evidence. Large
archives, selected copies, WASM/WAT and the completed worktree are disposable.
