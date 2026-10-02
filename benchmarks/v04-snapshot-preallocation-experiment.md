# Lane B — cold Snapshot filesystem copy preallocation

## Scope and provenance

Common base: **`6940bf1ac3010a020c8a67cd366d9e26c42c4974`** on
`v0.4/generated-go-integration`. This independent lane is
`experiment/v04-snapshot-preallocation`; it neither incorporates Lane A nor
changes the integration branch. No canonical benchmark or production integration
was performed. The normal generated-Go/direct-link execution decision remains unchanged.

Environment: Apple M1, 16 GiB, 8 logical CPUs, macOS 27.0.1 / 26A434, arm64,
Go **1.26.8**. Five before and five after trials each run in a fresh process,
sequentially with alternating order, after both lanes' compilation and tests
finished. All ten valid trials are retained. Sampling uses 64 KiB Go heap profiles;
only after the timed/allocation boundary does diagnostic GC settle the profile
epoch. No GC or FreeOSMemory enters production code. This is a small diagnostic
sample, with min/median/max, not a new p95 or canonical performance claim.

Guest build recipe source: `6233141573a5907c7cf3616d479a600c2b6eecd5`.
Corrected external assembly recipe: `3d57a529c6230e565d40351e18b9a675538b280b`;
complete transformed-file audit: `48cf7e2cd0ce3a50add2e9e6f4e0075034baa775`.
The before runtime is the exact common-base production code, guest
`5a513f74607ef1f1ddd4a36ebeefbba50354d9d00564e1977475d642104903bb`.
The rebuilt experimental guest is
**`33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`**,
18,560,271 bytes, +47 bytes. Pinned LLVM/LLD 23.1.0, WASIXCC 0.4.7,
legacy-EH sysroot and goccy/wasm2go input/three patches are unchanged.

Type/import/table/memory/global sections are byte-identical to the base guest;
all 4,974 export names/kinds/type signatures are equivalent. Export function
indices relocate naturally. Raw generated runtime/base files match the previous
converter inventory exactly. **Every one of the 29 non-base generated Go files,
including p0–p8 function shards, was independently re-derived, formatted and
byte-compared before accepting the measurements.** All three compiled guest
identity bindings use the new guest hash. The experimental source inventory is
strictly bound to that guest and translation manifest.

Generated artifacts and profiles remain outside the public source tree. Small
[evidence/results](snapshotpreallocation/values.json),
[translation pins](snapshotpreallocation/generated-inputs.json) and
[experimental source provenance](snapshotpreallocation/candidate-provenance.json)
are retained. Historical release/platform-image pins are unchanged and are not
claimed to validate this new artifact; explicit experimental provenance does.
Canonical branch provenance remains unchanged. See the
[reproduction commands](snapshotpreallocation/README.md).

## Current mechanism and exact change

`guest/snapshot_fs.inc: snapshot_copy` obtains `lstat` before a cold regular-file
copy. It opens an exclusive new output (`wbx`), then writes in 64 KiB blocks.
Output `memFile.Write → writeAt → resizeMemData` grows a private byte slice.
Capacity doubles below 1 MiB, then grows 25% at a time. Each reallocation copies
the old buffer and leaves its backing collectible. Source tree, destination tree
and retired growth arrays coexist until collection.

For the observed ~138.17 MiB of data, the 64 KiB growth-rule replay gives
**~774.63 MiB cumulative destination allocation, 99 reallocations and ~158.16 MiB
final capacity**. Redo's 96 MiB file alone drives ~539 MiB of growth allocation.
These counts are a static replay of the actual file-size inventory, not an
instrumented dynamic allocation counter. Sampled alloc_space corroborates the
scale independently.

The only storage-semantic change is **seven added C lines**, stored separately
in `guest/experimental.patch`: before copying, call
`ftruncate(fileno(out), st.st_size)` and fail if it fails. The final size is known
because the helper runs before database opening or after full shutdown. This
uses the existing `Fd_filestat_set_size → memFile.Truncate → resizeMemData`
contract; a new empty destination receives its known size once. **No global
MemFS growth rule, public API, Snapshot format or prepared-file model changes.**

Truncate preserves the output offset zero. Newly extended regions are zero;
subsequent writes fill the same logical contents. Native helper tests verify
empty, binary, sparse/zero-region, nested and renamed-source copies byte-for-byte,
and reject an existing destination. Existing grow/truncate tests preserve zero
regrowth, sparse writes, append offsets and stable directory-FD identity.
Only private cold output objects are pre-sized: no prepared base or sibling file
is changed, no live file is resized as an optimization. Memory-allocation/error
timing changes, and a truncate error now rejects the cold copy; failures do not
publish a Snapshot.

The build support additionally moves experimental-patch application after copied
overlays and before diagnostics, recording both original overlay and final
compiled-helper hashes. Archived experiment replay establishes its explicit
experiment-branch guard. These are separate experiment/build support changes,
not part of the seven-line storage change. Do not blindly merge this branch's
harness or installer as production distribution code.

## Measurements

**MiB is 2^20 bytes.** Snapshot TotalAlloc delta covers the public Snapshot call,
not Start/fixture preparation, hash walks, child validation or diagnostic GC.
HeapAlloc below is at Snapshot return, **not a measured peak or live-object proof**.
The profile alloc_space is cumulative through preparation and Snapshot, so its
resize total includes source setup as well as the cold export.

| Measurement | Before min / median / max | After min / median / max | Median effect |
| --- | ---: | ---: | ---: |
| Snapshot total, ms | 447.05 / 459.20 / 465.87 | 367.89 / 384.69 / 400.59 | −74.51 ms / −16.2% |
| export/shutdown, ms | 161.93 / 171.05 / 194.87 | 93.85 / 97.73 / 107.30 | −73.32 ms / −42.9% |
| publish, ms | 204.59 / 209.39 / 233.25 | 193.38 / 208.61 / 222.29 | −0.78 ms / −0.4% |
| Actual Snapshot TotalAlloc, MiB | 914.83 / 914.83 / 914.83 | 278.17 / 278.17 / 278.17 | −636.66 MiB / −69.6% |
| HeapAlloc at return, MiB | 3114.82 / 3114.83 / 3114.84 | 2478.16 / 2478.17 / 2478.17 | −636.66 MiB |
| Sampled cumulative resize alloc_space, MiB | 925.05 / 925.21 / 925.40 | 288.57 / 288.67 / 288.73 | −636.55 MiB / −68.8% |
| Sampled transfer-export full-file buffers, MiB | 138.17 / 138.17 / 138.24 | 138.17 / 138.17 / 138.24 | unchanged |

Individual Snapshot times (trial 1–5):

- before: **465.871, 465.083, 459.199, 449.528, 447.049 ms**
- after: **384.690, 371.090, 400.594, 367.885, 388.863 ms**

Every after Snapshot is below every before Snapshot in this small sample; no
valid sample is excluded, and there is no ≥500 ms Snapshot here. This does not
remove or disprove the known legal InnoDB startup tail. Start was not the timing
endpoint. Raw whole-process duration and all trace checkpoints are preserved.
The diagnostic before median 459 ms must not replace the canonical 490 ms.

Profile stacks change from the recursive cold helper's
`Fd_write → memFile.Write → resizeMemData` allocations to
`Fd_filestat_set_size → memFile.Truncate → resizeMemData` allocations of the
known file sizes. The observed ~636.55 MiB resize reduction matches the growth
model and ~636.66 MiB exact TotalAlloc reduction. Transfer export's whole-file
buffers remain ~138 MiB; publication still streams/hashes OS files and its median
is unchanged. No inference about a live Snapshot ownership leak is needed.
Sampled alloc_objects is noisy for tiny allocations and is not used as an exact
dynamic reallocation count.

Published logical total is ~138.176 MiB including the small manifest. File sizes,
fixture preservation, strict manifest/file validation and per-child base-file
checksums pass. Independent MariaDB initializations and changed guest identity
can change Snapshot hashes; equal cross-run full Snapshot hashes are not a valid
requirement. Actual cold-copy byte equality is separately tested; each produced
Snapshot's own contents/hash validation is preserved.

## Correctness and construction audit

- Patched native cold helper + overlay-order + nested-installer regression:
  **3 PASS**; guest build/reproduction/helper suite: **15 PASS** after that test addition.
- Original common-base normal `internal/snapshot`, `internal/guest`,
  `internal/host` and default public acceptance PASS.
- **Correctly regenerated after candidate**:
  `MARIAMEM_TEST_DEFAULT=1 go test -p 1 -tags integration ./tests/godefault ./tests/gointegration -count=1`
  PASS (2.944 s / 4.281 s); normal snapshot/guest/host PASS;
  focused `go test -race ./internal/generatedgo/code/base -count=1` PASS (2.341 s).
- All ten valid process trials: two children, 1,000 fixture rows, committed write
  and schema isolation, rollback, unchanged prepared-base checksums, one-child
  shutdown while the other still answers SQL, normal Close and deliberate
  corruption rejection PASS.
- No full-guest race suppression or shared-memory adapter work. No SQLAlchemy/GORM
  or canonical scaling rerun is claimed for this small lane.

**Important invalid first assembly:** the first experimental installer copied
only root `.go` files and left the old nested p0–p8 function bodies. Guest identity
constants were new, but actual copy code was old. Ten initial raw trials are
retained with an `invalid-assembly.json` label, excluded only because the after
assembly was wrong, never by timing. Identical before/nominal-after allocations
prompted this audit. The corrected installer deletes obsolete non-base code,
copies every shard, retains the explicitly unchanged base, tests nested-body
replacement, and independently checks all 29 transformed files. A fresh accepted
before/after batch follows. This tooling correction is not a MariaDB/runtime fix.
An earlier acceptance invocation also omitted `MARIAMEM_TEST_DEFAULT=1`; its
legacy-test guard stopped before DB creation and the correct invocation passed.

## Limits, independence and human decision

Allocation reduction and export latency improvement are demonstrated locally;
**Darwin physical/compressed accounting, ×16 physical memory and post-Close
reclaimability are not measured or fixed by this lane**. The 2 GiB generated
constructor allocation and ~138 MiB transfer-export buffer remain. Active DB
memory and Go shared-memory race semantics are unchanged. Five trials are enough
to challenge this targeted hypothesis, not to promise release p95.

Lane A owns linked guest pipe cleanup after execution completion. This lane owns
cold guest file-copy allocation. Neither code/ownership path depends on the
other; either may be integrated alone. A does not change copying or its timing
boundary. B does not change pipe ownership, worker lifecycle or shutdown join.
The experiments do not incorporate one another.

Recommendation: **integrate the small FD fix first**, then, if the human selects
this strong candidate, adopt the seven-line helper change through the canonical
guest/generated-source/provenance pipeline. Do not ship the experimental installer
or merge its full history blindly. Supported-platform acceptance, fresh metadata
and later packaging bindings must follow that chosen integration. Run normal
acceptance and one canonical campaign on the combined selected candidate;
no integration or further architecture work is done here.

## Verdict

**PREALLOCATION IS A STRONG INTEGRATION CANDIDATE**
