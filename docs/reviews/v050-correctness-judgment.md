# v0.5.0 bounded correctness judgment

**Recommendation: do not qualify the current candidate unchanged.** Three
bounded correctness changes are required before final qualification: preserving
file contents in fd_allocate, zero-length bulk bounds, and load-only 8/16-bit
atomic lowering. Shared-memory semantics remain unresolved; on production mmap
backing, zero Go race reports are an observation limit, not a safety result.
This is an engineering recommendation for Human decision, not approval of a
runtime redesign or a release. No production fix is applied in this task.

## Scope and identities

Baseline is the pushed A–D source
`808df8b614906a9cd918229e2754d33a5a76dc4b`, MariaDB 12.3.3 guest
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`,
goccy/wasm2go `730057c146463f663e8774587bc96fb2bea91af8` plus unchanged nine
patches. See [A–D integration](v050-ad-integration.md), rather than repeating
its input/build/consumer inventory. Main is still `098b0144ed50835da792ba811d11e0a1c8b000b2`.

Probe input commit is `4b67095` (full SHA in results.json). The
[fixture runner](../../benchmarks/spikes/v050-correctness/probe.py) copies every
canonical base implementation byte unchanged into an isolated small module,
including its canonical prepared.Entry dependency, then adds diagnostic tests.
[Identity](v050-correctness-evidence/identity.json) records helper dependency,
fixture, guest and actual installed Go runtime source hashes.
No guest, converter patch, generated output, public API or product guard changed.
We did not compile the full guest, run full qualification, perform a new full
race census or collect performance measurements for this judgment.

Local environment is macOS27.0.1 arm64, Go1.26.8. Ubuntu24.04 x86_64 is **SKIP**:
no native runner in this task. Go runtime range-filter evidence below is specific
to the observed darwin/arm64 toolchain; the native amd64 observation must be
repeated before using it in that platform's review.

## Results and judgments

[Results](v050-correctness-evidence/results.json) contains 26 command outcomes:
18 PASS, 8 FAIL, zero setup/build errors in the final run. These are diagnostic
outcomes, not a release acceptance score. Each failing oracle is retained; the
runner never rewrites goldens or converts a semantic FAIL into a product PASS.
The first fixture attempt omitted prepared.Entry; it produced setup errors,
not semantic findings. That dependency was included and all tests were rerun.

| Boundary | Observed result | Judgment |
| --- | --- | --- |
| fd_allocate inside an existing file | MemFS and native: 16-byte file becomes 4 bytes; errno=0 | Confirmed data loss; bounded release blocker |
| fd_allocate zero length / unsigned overflow | Both backends truncate to zero; unsigned `u64 max + 1` represented as `(-1,1)` is accepted | Confirmed validation/data-preservation defects; include in the same bounded fix |
| fd_allocate growth and invalid FD | Growth to 32 preserves original 16 and zero extension; invalid FD returns EBADF | Controls PASS; do not mistake them for allocation-contract coverage |
| Zero-length memory.fill/copy/init | At-end controls pass; 9 out-of-bounds/source/drop cases fail to trap | Confirmed WASM semantic mismatch; bounded release blocker |
| Atomic 8/16 values, alignment and bounds | Correct lane values and existing bounds/alignment traps | Controls PASS; they do not establish load-only access semantics |
| Atomic load versus ordinary read of its target | Both widths report a write/read race on Go heap; CAS is the writer | Confirmed load introduces a physical write; bounded lowering blocker |
| Atomic load versus write to adjacent byte | Both widths report overlap on Go heap | Widened access footprint; fixing identity CAS alone is insufficient |
| Read-only 32-bit extraction versus adjacent byte write | Race still reported on Go heap | Reject this as a complete width-preserving solution; diagnostic only, no patch adopted |
| Same four subword patterns on NewMemoryMapping backing | No race report | Detector observation limit; no conflict-resolution claim |
| Ordinary read/modify/write conflict, heap versus NewMemoryMapping | Heap reports race; mmap reports none | Same unsynchronized pattern, different observability; zero mmap reports cannot certify the guest |

### fd_allocate

The [WASI snapshot ABI](https://raw.githubusercontent.com/WebAssembly/WASI/snapshot-01/phases/snapshot/docs.md#fd_allocate)
describes space allocation and relates it to posix_fallocate. The
[primary POSIX API documentation](https://docs.oracle.com/cd/E86824_01/html/E54766/posix-fallocate-3c.html)
preserves file size for allocation inside existing contents. By contrast, the
current helper calls Truncate(offset+length) unconditionally. The
[reproducer](v050-correctness-evidence/TestAllocatePreservesExistingData.txt)
shows actual byte loss on both backends, not only a missing return-code check.
Zero length may require rejection or a documented no-op depending on the precise
adopted ABI; neither outcome permits destroying preexisting contents. We do not
require successful zero-length allocation to prove the bug.

Unsigned WASI filesize cannot be validated by signed addition: max-u64 plus one
wraps to zero and currently destroys data while returning success. Reject
unrepresentable/overflowing ranges before invoking the backend. Preserve bytes,
current position and size when the request does not grow the file. Verify
allocation errors, readonly/invalid descriptors and concurrent size changes.
A separate Stat followed by unconditional Truncate can still shrink a file that
another writer grew between those calls; a proposed fix must close that race.
This is a bounded allocation contract, not approval to redesign VFS or file locks.
Native storage reservation guarantees are separate from logical-size preservation;
do not silently promise ENOSPC prevention merely because Truncate succeeds.

There is one direct new-guest import call, in Fn18201, mapped by the A–D function
map to InnoDB os_file_set_size. It is guarded/aligned in that guest function.
This static call does not prove a normal SQL workload exercises every failing
range, nor that ordinary workloads already lost data. The host contract is still
wrong and the capability is present in the adopted guest.

### Zero-length bulk operations

The [WASM instruction specification](https://webassembly.github.io/spec/core/exec/instructions.html#memory-fill)
checks bounds before taking the zero-length no-op. That applies to destination
and source ranges in copy/init, including the empty dropped segment.
Current helpers return before these checks. A destination one byte beyond the
logical bound returns normally even when reserved backing exists; unsigned -1
also bypasses the trap. Empty copy/init sources past their bounds do too.
The [oracle log](v050-correctness-evidence/TestZeroBulkBounds.txt) distinguishes
legal at-end empties from those invalid cases and checks that memory is unchanged.

The proposed correction must retain unsigned nonwrapping logical bounds, accept
exactly-at-end zero-length ranges, reject invalid source/destination endpoints,
and preserve the empty dropped-segment rule. Place it in the converter helper
source/patch ownership and independently regenerate; never hand-edit canonical
Generated Go. The A–D 2,472-case memory32 PASS is a different fixture boundary and
does not negate these now-reproduced bulk-operation failures.

### Subword loads

The [Threads instruction definition](https://webassembly.github.io/threads/core/exec/instructions.html#atomic-memory-instructions)
defines an atomic load as a sequentially consistent read with its requested
width. Current AtomicLoad32_8u / AtomicLoad32_16u dispatch to AtomicSubword32,
which uses identity CAS when contended and a direct 32-bit write otherwise.
The value stays the same but the lowered access kind and footprint differ.
Read/read conflicts in the heap fixture originate in CAS, not in a guest write.
A correct fix must remove load-only writes while preserving alignment, unsigned
bounds and zero extension. It also needs a proved width/overlap/ordering contract:
[read-only word extraction](v050-correctness-evidence/TestReadOnlyWordNeighbor-race.txt)
continues to conflict with an independent neighboring byte writer.

Do not declare atomic.LoadUint32 plus a mask a complete 8/16-bit solution. Nor
should a plain byte load be called sequentially consistent without proof. An
architecture-specific narrow primitive or another proved overlap-consistent
mechanism requires its own limited design/verification; no platform/API/Go minimum
change or full shared-memory adapter redesign is approved here. Existing stores,
RMW and cmpxchg also have widened footprints; this task diagnoses loads and does
not claim to have certified or repaired all overlapping atomic operations.

## Shared-memory semantics and observation

The historical [race scope](../../benchmarks/direct-link-race-scope.md) remains
an investigation of its recorded old guest/converter, not the count for 12.3.3.
Its 149 signatures cannot be carried forward as a new census. The
[new static direct-call inventory](v050-correctness-evidence/call-sites.json)
finds 451 byte loads, one 16-bit load, and bulk/import paths. These are lexical
call counts, not runtime execution, object ownership or distinct race counts.

WASM's [shared-memory event model](https://webassembly.github.io/threads/core/exec/relaxed.html)
and the [Go memory model](https://go.dev/ref/mem) are separate contracts.
Ordinary/atomic overlaps, aliases, access widths and source ownership require
analysis before calling a WASM concurrency pattern preserved by generated Go.
A data race report alone does not prove SQL corruption; an unchanged scalar
value or functional PASS alone does not prove the translation sound.
The [Go detector documentation](https://go.dev/doc/articles/race_detector)
also limits detection to executed code paths.

There is a more concrete limit in this exact runtime. Production
`internal/generatedgo/memory_backing_unix.go` uses NewMemoryMapping, which reserves
anonymous mmap outside the normal Go heap. The same canonical constructor is
used in our mapped tests. Go1.26.8's installed `src/runtime/race_arm64.s` has
ordinary/atomic address-range gates: outside the registered Go arena/data range,
ordinary access instrumentation returns and atomic calls take their ignore path.
The file's SHA256 and inspected gate lines are recorded in identity.json; no
runtime range/linkname workaround is added.

[Heap ordinary conflict](v050-correctness-evidence/TestHeapPlainConflict-race.txt)
reports a race, while [mapped ordinary conflict](v050-correctness-evidence/TestMappedPlainConflict-race.txt)
does not. The pattern contains unsynchronized overlapping accesses in both;
mmap is not a synchronization mechanism. All four mapped subword conflict tests
also report zero, even though the identical heap patterns report races. Their
PASS labels mean those commands returned zero, **not race-correctness PASS**.
The counter values are incidental; no single scheduling outcome is a corruption
rate or an algorithmic correctness proof.

Keep focused handwritten/runtime race gates enabled. They still cover Go-owned
FD tables, thread/TLS/futex state, lifecycle and filesystem metadata. Their PASS
must not be presented as coverage of every mmap linear-memory byte. Do not add
norace, suppress reports, replace backing, promote all accesses to atomic, or
use function/address whitelists to make this investigation appear clean.

**Judgment:** general shared-memory correctness remains unestablished. A separate
Human decision must explicitly choose whether v0.5 continues the documented
limitation after the three bounded corrections, or requires a broader design
before release. Automatically inheriting a detector-zero result is not an option.
A full fresh census on mmap alone would not resolve the observation gap.

## Reproduce and next decision

Prepare an owned workspace based on the A–D commit, pin the probe source, inspect
Git identity, and select task-owned Go1.26.8 caches. Run:

```sh
python3 scripts/experiment_disk.py --work-dir /absolute/task \
  --min-free-gib 20 --budget-gib 6 --timeout 900 -- \
  python3 benchmarks/spikes/v050-correctness/probe.py --output ../temp/probes
```

The output directory must be new. The runner keeps every command result and
refuses setup/build errors as semantic findings. Known failing tests intentionally
remain outside ordinary product package discovery; successful collection does
not approve their failures. Final helpers/source remain checksum-identical to A–D.

Recommended Human decision: authorize three separately reviewable bounded fixes,
including an explicit narrow-load design, then repeat their positive/negative
fixtures and canonical independent generation. Decide the shared-memory limitation
with the mmap observation gap stated. Only after those decisions and verification
should final native Qualification and Product Validation start. This task does
not submit CI or publish, and does not mark v0.5.0 RELEASE READY.
