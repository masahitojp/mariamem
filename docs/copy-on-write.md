# Copy-on-Write terminology and Snapshot/Fork audit

Audited production baseline: `fa6ef5355ecb93f7e1cabbedf5caa74fe4210870`
(generated-Go v0.4.2 implementation). This audit changes documentation only;
the independent v0.4.3 characterization branch is measurement evidence, not an
integrated runtime change. Historical release-state descriptions are not updated
by this terminology audit.

## Human Review

1. **Is “mariamem has no CoW” true?** False as an unqualified statement about
   the normal generated-Go path: prepared files use OS page-level CoW. It is
   true that mariamem does not clone running MariaDB state or implement a custom
   filesystem CoW overlay.
2. **What exists?** Each Fork maps the same non-empty prepared files privately
   with `PROT_READ | PROT_WRITE, MAP_PRIVATE`. The OS can share clean file pages;
   writes to those mappings become private to the child. This is a property of
   the file mappings, not a snapshot of the running server.
3. **What does not exist?** No running linear-memory/heap, threads, TLS, locks,
   waiters or stacks are cloned. No application-managed block/page CoW overlay
   and no Unix `fork()`-based runtime cloning are used. Every child starts
   MariaDB afresh with independently owned execution and filesystem metadata.
4. **What was misleading?** “No CoW” around cold-copy preallocation meant that
   the change introduced no new CoW mechanism. “CoW” as a future roadmap option
   failed to distinguish runtime-image/custom filesystem work from existing OS
   file-page CoW. “Private writable files” described isolation without explaining
   shared clean backing. Current descriptions are made explicit; historical
   reports receive interpretation notes without changing their measurements.

## Canonical terminology

> Snapshot/Fork does not clone a running MariaDB runtime, and mariamem does not
> implement a custom CoW filesystem. On the generated-Go path, non-empty prepared
> files use private file-backed mappings (`MAP_PRIVATE`), allowing the OS to share
> clean file pages and create private modified pages on write. This OS-level CoW
> is an implementation detail, not a public memory-usage guarantee. `Fork()` is
> not Unix `fork()`.

Use **runtime-state CoW**, **custom filesystem CoW**, **prepared-file OS CoW**,
or **Unix process fork** explicitly. “No runtime sharing” refers to mutable
execution state, not immutable linked code or clean file-page sharing. Do not
use “no CoW” as a description of the whole product.

## Production path and ownership

`Database.Snapshot → host.Server.Snapshot/finish → MariaDB shutdown → guest
snapshot_copy → generatedgo.exportTransfer → snapshot.Publish/Validate`

`Snapshot.Fork → start → host.start/ValidateTimed → guest.startLinked →
generatedgo.StartInstance → MapPreparedFiles + newMemoryModule → generated.Start
→ MariaDB startup → SQL/use → cooperative Close/join → release mappings`

| Layer | Backing and sharing | Copy/write behavior | Ownership and lifetime |
| --- | --- | --- | --- |
| Snapshot capture | Cold guest MemFS data after MariaDB shutdown; no live runtime image | `snapshot_copy` pre-sizes destinations and eagerly copies bytes in a 64 KiB loop | Successful capture consumes the source DB; no heap/worker state is retained |
| Host export/publication | Ordinary disk files under transfer, then destination `data/`; committed manifest includes inventory/build identity/hashes | `exportTransfer` allocates a per-file buffer and writes host files; `Publish` uses `io.Copy` to new destination files and verifies contents | Snapshot handle retains path/options; temporary destinations are handle-owned, explicit destinations persist |
| Fork validation | The saved directory/manifest and files | Reads/hashes prepared bytes before use; this is not a private full-file materialization | Go handle's read lock pins files through admitted startup; validation is not a claim that externally changed files are safe |
| Prepared file views | Separate file-backed RW `MAP_PRIVATE` mapping of each non-empty file, same saved backing files across Forks; empty files have no mapping | No eager full-byte copy in `MapPreparedFiles`; clean pages can be OS-shared, writes become private | Each child owns its mappings; file descriptors close after mapping. No `MAP_SHARED` writeback to the prepared files |
| Filesystem metadata | Fresh `NewMemFS` tree; independently constructed nodes, descriptors, directory/file offsets and timestamps | Directory/file metadata is constructed per child, not shared as mutable nodes; rename/unlink affect the child's tree | One child's filesystem operations/Close cannot invalidate a sibling's views |
| Writes and file growth | Initially mapped file data; new files use child-owned Go buffers | Within capacity, writes and truncate/regrow zeroing dirty private pages. Beyond capacity, `resizeMemData` does `make + copy` for that file and detaches from its mapped storage | Original mapping stays in the owner's release list until teardown; detached/new buffers are GC-managed |
| Guest linear memory | New anonymous `MAP_PRIVATE | MAP_ANON` region per instance; 2 GiB reservation, initial logical/RW range 256 MiB | Initializers write into fresh memory; grow uses `mprotect` without moving the base. No saved linear-image backing is reused between DBs | Workers within one DB share its linear memory; other DBs have separate mappings. Owner unmaps after cooperative join |
| MariaDB execution/use | Fresh Module/globals/function tables, thread pool/TLS, locks/waiters/stacks, sessions and InnoDB state | Server startup runs for every Fork; file reads copy into guest buffers/linear memory, so file-page sharing does not eliminate private buffer-pool costs | No running MariaDB continuation is captured, restored or cloned |
| Close | Child descriptors, prepared mappings and linear mapping | `executeGuest` joins workers; deferred descriptor/prepared cleanup and linear release then run | `PreparedFiles.Close` unmaps owned file views; linear owner releases its anonymous region. Non-cooperative forced reclamation remains unsupported |

Source anchors:
[public Snapshot/Fork/Close](../snapshot.go),
[host validation/export/publication](../internal/host/server.go),
[cold guest copying](../guest/snapshot_fs.inc),
[guest shutdown/export](../guest/resident.inc),
[host file export](../internal/generatedgo/main.go),
[publication/inventory](../internal/snapshot/snapshot.go),
[linked execution](../internal/guest/linked.go),
[instance ownership](../internal/generatedgo/runtime_instance.go),
[prepared mappings](../internal/generatedgo/code/base/prepared_files.go),
[file growth](../internal/generatedgo/code/base/memfs_growth.go),
[linear constructor](../internal/generatedgo/memory_backing_unix.go),
[anonymous mapping](../internal/generatedgo/code/base/memory_mapping.go), and
[linear release](../internal/generatedgo/memory_lifetime.go).

“No Unix fork” describes the DB cloning strategy. Python starts a fresh packaged
Go host via `subprocess.Popen`; the explicit legacy Wasmer path uses `exec.Command`.
The OS/library may use fork/exec or spawn internally to launch an executable;
mariamem does not keep a cloned parent MariaDB address space in either case.
Legacy restore passes `--restore-snapshot` and copies `/snapshot-in/data` into
the guest filesystem. The generated-Go adapter instead pre-populates `/mariadb`
with mappings and starts with no restore-copy argument. Its OS CoW must not be
generalized to every historical Wasmer restore path.

Anonymous memory can also benefit from OS zero-page/demand-allocation mechanisms;
`MAP_PRIVATE` alone does not mean that a MariaDB image is shared. The unused
converter helpers [SharedImage](../internal/generatedgo/code/base/sharedimage.go)
and `NewFromSnapshot` support image-based experiments, but `newMemoryModule`
calls `NewWithMemory` on a fresh `MemoryMapping`. No production call to the
`NewShared*` constructors or `NewFromSnapshot` was found. Their comments describe
helper capabilities, not mariamem's selected memory model; generated/support
source is left unchanged to preserve provenance.

## Evidence for the narrow OS CoW claim

The decisive implementation evidence is the actual non-empty-file call to
`syscall.Mmap(fd, 0, size, PROT_READ|PROT_WRITE, MAP_PRIVATE)` followed by attaching
that slice to a fresh MemFS node. `memFile.writeAt` writes into that slice within
capacity. This establishes private file-backed mapping semantics; naming such as
“Fork” or “private” is not the evidence.
These flags' private-copy semantics are documented by
[Apple mmap(2)](https://developer.apple.com/library/archive/documentation/System/Conceptual/ManPages_iPhoneOS/man2/mmap.2.html)
and [Linux mmap(2)](https://man7.org/linux/man-pages/man2/mmap.2.html). These explain
the mechanism; they do not replace execution acceptance or measure its savings.

Existing deterministic tests independently check observable consequences:

- `TestPreparedFilePrivateViews`: in-place child writes, append, rename and child
  unmap leave the saved file and sibling unchanged.
- `TestPreparedGrowthOwnershipAndZeroFill`: truncate/regrow preserves the mapped
  view while zeroing removed bytes; growth past capacity detaches to Go storage,
  retaining child data and leaving base/sibling unchanged.
- `TestDefaultNoBundleAndForkIsolation`: actual SQL data/schema changes stay
  isolated and a sibling remains usable after the other DB closes.

The [v0.4.3 Track B report](https://github.com/masahitojp/mariamem/blob/31f66c1f810da19444c2696c9bc7acf7352c652c/benchmarks/v043-snapshot-characterization.md)
measured this unchanged path on macOS arm64. At 16 children, prepared size grew
138→262 MiB while live Go heap stayed about 198→199 MiB and cumulative allocation
was about 208→219 MiB. This supports the absence of eager full-file Go copies,
not a count of precisely shared physical pages. Mapped dirty-page accounting and
base/sibling mutation checks are consistent with private writes. Additional
100 MiB full-payload scans at ×1/×4 avoid relying only on COUNT.

RSS increased about 1,319→3,180 MiB across those ×16 cases. Physical deltas were
about 1,188–1,261 MiB, but subtract each process's own post-preparation/GC
checkpoint and include unrelated reclamation. Neither RSS nor these deltas
prove exclusive private-byte cost or exact sharing ratios. Filesystem metadata,
dirty pages, anonymous runtime memory, InnoDB buffers and detached growing files
still cost memory per child. Heavy growth/hot workloads and Linux performance
were not characterized by Track B. There is no zero-incremental-memory promise.

## Documentation occurrence audit

[Baseline occurrence inventory](cow-terminology-inventory.tsv) records each
matching line and classification at the pinned baseline, including historical
report references, example mode names and runtime-helper comments. Searches
covered tracked docs/status/release notes, benchmark reports/templates, and
code comments; no separate ADR directory or literal “COW not required” claim
was found. Snapshot/Fork implementation sections were also read end-to-end.
The inventory contains 219 matching baseline lines: 195 class 1, six class 2,
and 18 class 3, including non-assertion experiment names/commands. These are
occurrence counts, not 219 independent product claims.

Classification: **1 correct**, **2 historically correct but stale as a current
description**, **3 technically correct but ambiguous**, **4 incorrect**.
No unequivocally false implementation assertion was found in its original
scoped context; the global reading “no CoW anywhere” is false.

| Baseline wording/location | Class | Resolution |
| --- | --- | --- |
| Architecture “not CoW” / “No … CoW … introduced” | 3 | Name cold-copy preallocation and fresh anonymous linear memory; explicitly preserve existing prepared-file OS CoW |
| Status “CoW/immutable Snapshot views” as future work | 3 | Scope future work to runtime-state/custom filesystem CoW; link current prepared-file semantics |
| Go/release docs “private writable files” | 3 | Explain independent metadata/private writes versus potentially shared clean pages |
| Integrated/direct-link reports and their generators “No CoW” / “new CoW or runtime sharing” | 3 | Add matching historical interpretation notes, preserving original tables/claims and generated report consistency |
| v0.4.0 notes “This is not CoW” | 3 | Annotate that this describes preallocation, not absence of OS file-page CoW |
| alpha.1 “not a live/COW snapshot” | 3 | Annotate runtime-state scope; historical restore implementation remains historical |
| CoW/prepared feasibility “filesystem CoW … 未実証”; direct-link inventory “prepared … 未実験” | 2 | Annotate exact experiment scope and later production adoption; no rewriting historical results |
| Older FAST / Wasmer timing docs describe restore as byte copying | 2 when read as current generated-Go | Preserve historical reports; label runtime-specific timing description and point to this path |
| “No … OS/process fork” and “no ready heap/live-worker restore” | 1 | Retain: these do not deny OS CoW on private mappings |
| “No runtime sharing” without a mutable-state qualifier | 3 | Interpretation is no mutable execution-state reuse, not no shared code/file pages |
| `PreparedFiles`/growth comments and isolation tests | 1 | Match implementation; retained |
| `SharedImage` comments, CoW spike names/tables/templates | 1 in helper/experiment scope | Retain; explicitly distinguish unused helper capabilities from production |
| Older release-readiness deferrals and dated experiment non-goals | 1 historically scoped | Retain history; not current capability statements |

## Verification

Go 1.26.8, macOS arm64, production code identical to the baseline:

- `go test -race -count=1 -v ./internal/generatedgo/code/base ./internal/snapshot`:
  PASS, including prepared views/growth, partial-tree cleanup, MemFS zero-fill,
  directory identity and inventory/hash validation.
- `go test -p 1 -tags=integration -count=1 -v ./tests/godefault
  -run '^TestDefaultNoBundleAndForkIsolation$'`: PASS. Real SQL setup, two Forks,
  data/schema isolation and sibling survival after Close. Initial sandbox run
  could not bind localhost; the same test passed outside that restriction.
- Public-source check, changed Markdown local links, Python report-template AST,
  matching report annotations and `git diff --check`: PASS. Runtime, generated
  guest, tests, pins and provenance remain unchanged.

Existing tests already cover backing reuse/detach and isolation, so no test
asserting permanent mmap flags is added. No full-guest race acceptance or new
Ubuntu run is claimed. No new benchmark campaign or runtime change. Temporary
checks used workspace disk guards: minimum free 12 GiB, owned budget 4 GiB,
600-second timeout, preserved shared Go cache; no budget violation occurred.
