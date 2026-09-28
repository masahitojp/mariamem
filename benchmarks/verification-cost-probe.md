# Fork verification cost decomposition

Status: source investigation complete; sub-stage measurements pending the focused
both-platform CI run. No verification work is skipped, cached or optimized.
Reference: [completed outer-boundary probe](fork-gap-probe.md), measured main
`80d922b`: native Resolve p50 57/59 ms and snapshot validation 80/93 ms
(macOS/Ubuntu). These are historical totals, not new sub-stage measurements.

## Source path and interval relationship

Public `Snapshot.Fork` locks/checks the snapshot handle, then calls `start`:

1. `artifacts.ResolveTimed`: platform detection; capture native file metadata;
   read/parse native manifest; validate platform; stat and SHA256 each required
   native file; read/parse AOT sidecar; compare its AOT hash and guest build ID;
   recheck captured metadata.
2. Prepare a private runtime directory and claim the single-use verified native
   identity. This claim rechecks metadata, not artifact contents.
3. Host `StartVerified`: recheck native identity; `snapshot.ValidateTimed` checks
   root/manifest types, root inventory, manifest format/version/guest build/storage,
   walks all data entries, hashes every regular file, and compares full inventory.
4. Prepare transfer directory; recheck native metadata directly before launch.
5. Launch Wasmer; guest reads the validated snapshot through `/snapshot-in` and
   copies it into its own memory filesystem, then initializes MariaDB.

**Source fact:** native and snapshot verification are sequential, disjoint
operations in one Fork. Native verification is inside API startup before host
startup; snapshot verification is inside host startup. They are additive at the
individual-duration level, but adding their separate p50/p95 values does not
reconstruct a measured percentile. Guest restore happens later and is another
read of snapshot bytes, not part of either verification interval.

## Guarantees and repeat work

| Work | Required guarantee | Repetition / ownership |
| --- | --- | --- |
| Native manifest and platform checks | Expected supported bundle layout/platform | Once per startup; Go does not validate an unused packaged host |
| Runtime + AOT + sidecar SHA256 | Bytes match the bundle manifest | Each required native file hashed once; previous redundant AOT scans remain removed |
| Sidecar parse/build comparison | Sidecar's AOT hash matches verified AOT; snapshot guest identity is compatible | Small sidecar reread after its hash; distinct interpretation check, not another large AOT scan |
| Metadata capture/rechecks | Detect mutation/replacement during startup | Repeated inode/size/mode/mtime/ctime checks at distinct handoffs; not content hashing |
| Snapshot manifest/types/inventory | Cold snapshot structure and guest build compatibility; no extra/missing/special entries | Required for this Fork |
| Snapshot per-file SHA256 | Contents match snapshot manifest at validation time | One complete content scan in this Fork |
| Prior Snapshot publish scans | Exported and copied bytes agree before a snapshot is returned | Earlier lifecycle, not trust in a possibly mutable snapshot at later Fork |
| Restore reads | Materialize isolated MariaDB state | Reads the same snapshot data again (~138 MiB / 11 files historically); cannot simply substitute for pre-launch verification |

The native manifest is an integrity/compatibility contract, not independently
signed remote provenance. Release provenance checks remain in release tooling;
this probe does not introduce claims of cryptographic provenance authentication
at startup. Native metadata handoffs preserve the existing concurrent-writer race
boundary; they are not atomic protection against a hostile writer. Snapshot
validation similarly must not be described as atomic verification of all later
restore reads.

## Diagnostic boundaries and measurement plan

Reuse `guest-build-boundary.yml`, `fork_gap_measurement=true`: 30 measurement
samples after two warmups, ×1, 1,000-row fixture on macOS arm64 and Ubuntu 24.04
x86_64. No ×4/×8 or expensive memory diagnostics are needed at this point.
Guest source/toolchain/settings are unchanged; verified WASM/AOT reuse applies.

Two new nested traces, `native_verification` and `snapshot_verification`, retain
monotonic timestamps for metadata/manifest work and per-file open, read+SHA256,
close and comparison. `bytes_read` counts actual logical content bytes returned
by existing `io.Copy` or `ReadFile`; `files_touched` counts file visits, including
repeated metadata/open visits, not unique files. Snapshot entry event names allow
unique data file/directory counts and the bytes/time per file to be recovered.
No extra file reads or stats are added for measurement. Read+hash is deliberately
one boundary: separating hashing from reading would change the operation and
requires a different experiment. Directory walking/stat time is between file
boundaries. Close includes small digest-format/deferred-return bookkeeping.

Existing `stage_summary` reports p50/p95 for each ending boundary and raw JSON
retains counts; the existing stage renderer adds logical-work totals. No per-stage
CPU is fabricated: existing runner/runtime observations retain their original
interval/resolution limitations, including sub-second Ubuntu `ps` CPU zeros.
Diagnostic output is outside each trace end and inside the enclosing lifecycle,
so instrumentation perturbation must be considered when comparing old totals.
New measured sub-stage figures will be filled in after CI; they are not inferred
from file sizes or the historical totals.

### Verification optimization candidates

1. **Native read+SHA256 implementation:** historical whole Resolve 57/59 ms;
   per-artifact attribution pending. No duplicate large-file hash remains.
   Preserve every manifest/content/identity check. Smallest possible boundary:
   ordinary hashing/read implementation, if measured evidence supports it.
   Benefit unknown (not the entire Resolve interval); integrity and mutation risk.
2. **Snapshot per-file inventory/hash implementation:** historical whole
   validation 80/93 ms; metadata versus hashing attribution pending. No duplicate
   snapshot content hash in this Fork. Preserve full inventory, format/build and
   content comparison. Smallest possible boundary: ordinary inventory/hash
   implementation. Benefit unknown; resource use and integrity risks.
3. **Verification-read versus restore-read ownership:** historically ~138 MiB
   read in both operations, with different purposes. No measured removable time
   yet. A fused boundary would have to preserve fail-closed validation and exact
   isolated restored contents; it changes trust/transfer ownership and is **not**
   authorized as a simple redundant-check removal. Require architecture review if
   results show that this is the only meaningful improvement available.

The small sidecar reread and metadata rechecks are not assumed to provide a
30–50 ms saving. This note does not select an optimization or weaken guarantees.
