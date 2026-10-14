# Human Review — Snapshot latency residual on the current guest

**Decision now:** authorize a bounded design spike for temporary Snapshot
creation that copies MemFS output directly into the files Fork will own,
hashes the source during copying, and verifies the retained destination files
once. I recommend this over optimizing one isolated pass: the measured 100 MiB
logical fixture takes about 0.71 s to Snapshot, and its traced operation spends
94% of wall time in host materialization/copying and repeated read/hash stages.
It targets those repeated traversals while retaining the existing page-level
isolation of child DBs. The strongest alternative is pgmem-style in-memory
ownership, which could avoid file materialization altogether; direct copying
still pays that full-data cost. I nevertheless recommend the smaller scope
first because it preserves the current Fork storage model. Integrity and
independent ownership are acceptance conditions, not costs to drop: reject a
scheme that cannot explain corruption detection and partial-failure cleanup.

**Review revision, 2026-10-14:** the original report at `b2e6b3e` proposed
combining one pass. The subsequent Human discussion asked why an intermediate
copy is needed and requested reconsideration against pgmem. This revision
proposes one end-to-end temporary-creation path instead; the wider proposed
scope still awaits Human approval. Existing measurements and raw evidence are
unchanged. No new benchmark, runtime implementation, main integration or release
preparation was performed. The alternatives and finite stop conditions below
replace the earlier one-pass recommendation; they are not an adopted design.

## Answer to the research handoff

The [v0.5.0 handoff](../project-status.md#research-handoff--independent-of-v050-guest-migration)
asked what remains inside the public Snapshot cost. Reusing the
[v0.4.5 characterization](../../benchmarks/v045-measurement.md#snapshot-lifecycle-research-boundary)
and measuring the current guest gives a practical answer: repeated file
reading/hashing and materialization dominate the large fixture; the final
manifest and normal source cleanup are below 1 ms in every traced trial.
Guest shutdown versus guest-side copy is still not isolated, but their entire
unseparated host interval is only 30–38 ms in the three current traced cases.
That is not a universal bound; it is enough to deprioritize guest-internal
instrumentation for the present optimization decision. Fork startup/recovery
remains a separate operation. The pgmem ~10 ms VFS Clone figure has different
lifecycle and storage boundaries and is not a mariamem target or comparison.

This is research, not a pass-removal approval. The source was clean main
`2550bbe1ccf58f9cf65cf4cd801224907a7f9469`; guest SHA-256 was
`7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09`.
`scripts/git_identity.py inspect HEAD` and the Go binary's embedded Git
revision/clean flag agreed before timing. Local machine: macOS 27 arm64,
Go 1.26.8, `GOMAXPROCS=2`. [Inputs and binary hash](snapshot-latency-residual-evidence/inputs.json)
retain the precise conditions; the published input record replaces only the
local host/path. The original unredacted input SHA-256 was
`6809363aa7637132355f5b2b397926a741c834134600fe82769350134fd466be`.
No Ubuntu measurement or new platform qualification was performed.

| Logical payload | Public Snapshot median, 3 untraced trials | Range | Traced host stop/export envelope | Within it: post-guest transfer | Remaining combined interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Minimal | 337.2 ms | 336.4–340.1 ms | 93.2 ms | 63.2 ms | 30.0 ms |
| 10 MiB | 394.1 ms | 390.4–397.0 ms | 105.1 ms | 69.8 ms | 35.3 ms |
| 100 MiB | 711.6 ms | 689.7–727.9 ms | 157.8 ms | 119.8 ms | 38.0 ms |

The table uses separate traced trials for phase attribution. Do not subtract
those phases from the three untraced medians. In the code path,
[`Server.finish`](../../internal/host/server.go) waits for guest export and
process exit; [`StartInstance`](../../internal/generatedgo/runtime_instance.go)
performs guest execution and then `exportTransfer`. Therefore `host stop/export
envelope - snapshot_export` contains guest `l4m_close`, guest `snapshot_copy`,
acknowledgement, thread joins and final runtime/descriptor cleanup together.
None of those constituents is individually measured. The [selected traces](snapshot-latency-residual-evidence/payload-100-trial-3-traces.json)
and [summary](snapshot-latency-residual-evidence/summary.json) retain exact
offsets for all three payloads.

| Traced publish/acquisition phase | Minimal | 10 MiB | 100 MiB |
| --- | ---: | ---: | ---: |
| Source inventory/read/hash | 61.6 ms | 71.8 ms | 127.7 ms |
| Host materialized copy | 55.7 ms | 64.5 ms | 198.3 ms |
| Target inventory/read/hash | 62.8 ms | 72.9 ms | 129.1 ms |
| Owned backing acquisition/read/hash | 64.0 ms | 72.7 ms | 132.2 ms |
| Manifest after target hash | 0.41 ms | 0.34 ms | 0.35 ms |
| Public source cleanup | 0.065 ms | 0.067 ms | 0.064 ms |

Source/target inventory and owned acquisition are distinct passes, not
duplicate accounting of one nested timer. The manifest/cleanup residuals do
not justify new instrumentation now. Existing counters indicate five full-data
reads, two materializations and three hash passes for temporary creation;
these are logical traversals, not five physical disk reads. The [campaign index](snapshot-latency-residual-evidence/campaign.json)
and per-trial benchmark files (for example, the [100 MiB traced trial](snapshot-latency-residual-evidence/payload-100-trial-3.json))
retain every completed SQL/Snapshot/Fork/Close run. All twelve measurement
trials completed without an oracle failure; no timing sample was discarded.
Two setup attempts stopped before measurement because the sandbox denied Go
cache writes and then local TCP binding. The same fixed input was rerun with
the required permissions; neither setup attempt produced a timing sample.

## Timeline and dominant work in the existing trace

The selected 100 MiB traced operation took **751.7 ms**. This is a separate
sample from the 711.6 ms untraced median; do not combine their numbers. Absolute
phase positions below are rounded approximations because nested traces have
separate clock origins. Operation order follows the implementation.

| Approximate time since public Snapshot entry | Work | Measured duration |
| --- | --- | ---: |
| 0–158 ms | Guest stop/export and host materialization envelope | 157.8 ms |
| Within that envelope | Post-guest `exportTransfer`: MemFS `snapshot-out/data` to an OS temporary transfer directory | 119.8 ms |
| Elsewhere within that envelope | Guest close/copy, acknowledgements, joins and runtime/descriptor cleanup combined | 38.0 ms by subtraction; not one located interval |
| 158–286 ms | Transfer-source inventory/read/hash | 127.7 ms |
| 286–484 ms | Copy transfer files to Snapshot destination | 198.3 ms |
| 484–613 ms | Destination inventory/read/hash | 129.1 ms |
| 613–619 ms | Manifest completion and return/cleanup glue | About 6 ms; manifest itself 0.35 ms |
| 619–752 ms | Acquire and verify exact owned backing | 132.2 ms |

The guest is the MariaDB code generated from Wasm into Go, using the Go host's
MemFS. After `l4m_close`, guest `snapshot_copy` copies `/mariadb` to
`/snapshot-out/data` inside that filesystem. Only after guest execution/join
does [`exportTransfer`](../../internal/generatedgo/main.go) read those files
and call `os.WriteFile` for the OS transfer directory. The 119.8 ms is this
**post-guest MemFS-to-OS-file materialization**, not network transfer or a
measurement of crossing a Wasm instruction boundary. Guest-internal copy time
is not individually known.

Existing `snapshot_export` events give a further breakdown; no new run was
needed. For each file, subtract `allocation_begin` from `allocation_done`,
then the latter from `data_read`, then `data_read` from `data_materialized`,
and sum each difference over all 11 files:

| Part of the 119.8 ms | Sum |
| --- | ---: |
| Allocate a file-sized read buffer | 2.796 ms |
| Read MemFS bytes into that buffer | 20.112 ms |
| `os.WriteFile` including file open/write/close | 96.274 ms |
| Remaining traversal/timing glue | 0.626 ms |

These steps repeat per file, rather than being four contiguous bulk stages.
They are wall intervals, not pure CPU or physical-device I/O times; writing
through the OS cache does not establish durable media completion. The trace
counts **274,746,713 bytes** (about 262 MiB), not 100 MiB. The separately
exported proxy artifact below has 274,746,682 bytes; they are different
artifacts, so its manifest must not be attributed to this trace.

Three read/hash stages sum to **389.0 ms (52%)**; export materialization plus
host copy sum to **318.1 ms (42%)**. These disjoint groups account for about
94% of this sample. Allocation and traversal are included in their envelopes;
the percentages are not pure SHA CPU or disk-write attribution. The design
bottleneck is repeated traversal and materialization of the same logical
files across export, publication and ownership boundaries. The measurements
justify investigating those boundaries, not simply disabling their checks.

To estimate hash CPU without changing the runtime, one explicitly exported
100 MiB fixture was read by a [read-only Go probe](snapshot-latency-residual-evidence/read_hash_probe.go)
using two workers and 32 KiB buffers. It contained 11 regular files and
274,746,682 bytes. Seven alternating pairs followed one retained warmup pair;
every read counted the same bytes and all SHA-256 digests remained stable.
The [artifact manifest](snapshot-latency-residual-evidence/artifact-100-manifest.json)
binds the exact file hashes; its SHA-256 is
`9d2f27d2a7074f86b6685537535844b76c9ef0a1d64b886af8b517337c11eae4`.

| Same-file pass, warm-cache proxy | Read only | Read and SHA-256 |
| --- | ---: | ---: |
| Median wall | 13.3 ms | 74.2 ms |
| Median process CPU | 26.0 ms | 143.5 ms |

The matched-pair CPU difference was 116.8 ms and wall difference 60.7 ms per
full pass. Process CPU sums both workers, so it can exceed elapsed wall time.
This supports SHA-256 as a material CPU component, but it is **not**
an exact split of the live `inventory/read_hashed` timer: the probe reads a
persisted artifact through the OS cache, while the live path includes MemFS,
file enumeration, scheduling and ownership work. [All proxy samples](snapshot-latency-residual-evidence/read-hash.json)
are retained. An exact in-operation CPU attribution remains open, but the
observed proxy and 127–132 ms live read/hash intervals are sufficient to route
the next design question toward pass count rather than guest shutdown.

## Two candidates after reconsidering pgmem

The [pgmem review](pgmem-vfs-design-review.md) inspected source commit
`3433a40bd4167daea2d8e364666bd5fcf18ef654`. Its public Snapshot stops the server,
clones filesystem metadata while sharing file byte arrays, then restarts the
source. Fork clones that tree and starts a new server. The first in-place write to a
shared regular file copies its logical contents at file granularity. Thus its
advantage is avoiding serialization at Snapshot creation, not faster copying.
Archive persistence is a separate operation. Its reported Clone time cannot be
compared to mariamem's public Snapshot including ownership and verification.
No new pgmem performance measurement was made here.

| Candidate | Creation path and potential benefit | Cost / limitation | Recommendation |
| --- | --- | --- | --- |
| **A: direct materialization with integrated verification** | Copy stable MemFS Snapshot output directly into final private backing, compute expected source hashes during that copy, then verify the exact retained destination descriptors once. Avoid intermediate OS-file copying and separate repeated inspections. | Full materialization and final reread remain. Ownership handoff and partial failures must be redesigned together. | First bounded spike; retain existing file-backed `MAP_PRIVATE` Fork. |
| **B: in-memory Snapshot ownership inspired by pgmem** | Retain the stopped filesystem data as the baseline, avoiding OS-file materialization for ordinary creation. Since mariamem consumes the source, a source-restart clone might be unnecessary. | Child writes need a new sharing/detachment design; pgmem-style file CoW may move cost into child SQL and memory. Existing acquisition verification, Go/Python paths, persistence and explicit release still need a design. | Keep as an alternative; no implementation in the proposed A spike. |

Candidate B is not rejected as inherently slower. The
[architecture review](memfs-architecture-decision.md#4-architecture-trade-offs)
already notes workloads where in-memory Clone is attractive. Current evidence
makes Snapshot traversal worth revisiting, but does not measure the child-write
and lifetime tradeoffs needed to select B. Nor does a persisted API requirement
force every temporary Snapshot to use files: that is the current internal
representation, which B would change.

Candidate A's intended path is:

```text
stable guest-produced MemFS snapshot-out/data
  -> copy once into final private files, hashing the source stream
  -> stop all writers, retain read-only descriptors, remove path aliases
  -> verify inventory/content/guest identity against expected source records
  -> return ownership of those same descriptors for existing Fork mapping
```

"Copy once" describes **host materialization**. Guest `snapshot_copy` stays
unchanged in this first scope; direct reading of `/mariadb` and its shutdown
protocol would be a separate change. The expected digest must describe source
bytes, not be replaced by a digest generated solely from potentially damaged
destination files. Combining hash and copy also has a cost; subtracting old
phase durations does not predict the new public latency.

The earlier smaller option (combine destination verification with ownership
verification) remains a possible implementation step inside A, not a third
parallel design. The recommendation changed because leaving the intermediate
copy intact fails to address an avoidable full-data traversal. Candidate A
applies pgmem's ownership lesson while keeping existing child page isolation.

The initial target is the measured **temporary Snapshot** path. Explicit
destination creation and `LoadSnapshot` must retain independent internal
backing: editing/deleting the persisted source after acquisition must not
change Fork. Candidate A is not permission to unlink user-requested persisted
outputs or silently narrow support to Go. Public APIs, format and the
[consumed-source contract](../decisions/snapshot-product-contract.md) remain
constraints, including precondition rejection preserving the live source.

## Proposed bounded next step and stop condition

The next decision is authorization for **one design/feasibility spike on A**,
not production adoption. Allow a minimal isolated prototype only to settle its
ownership and performance questions; no guest/VFS replacement, B implementation,
main merge or release action is included. Estimate: roughly one engineer-day
for the design and minimal prototype/evidence, not production integration or
both-platform qualification. If that is insufficient, report the exact
remaining issue and revised scope/cost instead of extending the investigation
or declaring it complete because time was spent.

Finite deliverables and checks:

1. Map current checks to the new source/hash/copy/descriptor lifecycle, including
   who owns files during export and after host cleanup. Show how all producer
   writers stop and mappings remain alive until the final source read ends.
2. Before timing, establish fault oracles for destination corruption, short or
   failed writes, missing/extra files, guest-identity mismatch, and cleanup after
   partial failure. Preserve completed-publication semantics: partial output
   must not become an accepted manifest or successful Snapshot handle. Retain
   the existing successful-source consumption and busy/
   transaction rejection behavior. A copy stream hash alone is not validation
   of the written file.
3. Verify the temporary path can return the exact fully checked backing while
   keeping parent/sibling isolation, child use after parent Close, child-to-new-
   Snapshot, and descriptor/map cleanup. Cover affected Go/Python callers and
   keep explicit-destination/Load independence checks. If this needs a new
   storage backend or broader protocol, stop and bring that boundary to review.
4. If the prototype passes those checks, make one identity-bound paired local
   comparison using the existing minimal/10/100 MiB fixtures. Measure public
   creation, Fork/use/Close, allocation and peak memory; record instrumentation
   separately. Do not count moving cost to first Fork/SQL or retaining resources
   longer as a creation-only success. macOS evidence is not Ubuntu qualification.
5. Return one of: **feasible and worth production integration**, **reject A**, or
   **incomplete with a named blocker and bounded follow-up cost**. No material
   benefit means retain the current implementation; broken integrity/ownership
   means reject even if faster. If unavoidable materialization prevents meeting
   a Human-agreed creation budget, propose a separate B review with lifecycle
   comparisons rather than silently expanding A.

Runtime design, prototype correctness and speedup remain **unverified** today.
Exact in-operation read-vs-hash CPU separation also remains open, but is not a
prerequisite to testing removal of whole traversals. The original small macOS
sample remains the only performance evidence; no projected savings are adopted.

## Reproduction

The [normalized campaign script](snapshot-latency-residual-evidence/campaign.py)
documents exact measurement operations; only its local root/work paths differ
from the executed script (raw script SHA-256
`082d82a88f10ac9b601d14ba08e0344abcd96c449aaaecf58efb9d18cc6b7284`).
To reproduce, run that script from a clean checkout of the named source commit
with `MARIAMEM_EXPERIMENT_WORK` pointing to a disposable directory containing
`temp/` and `evidence/`, using Go 1.26.8. The script builds and verifies the
benchmark binary, runs three untraced and one traced trial per payload, and
writes the [trial index](snapshot-latency-residual-evidence/campaign.json) and
per-trial records.
The read/hash proxy takes the explicitly exported Snapshot's root and a JSON
output path; its [source](snapshot-latency-residual-evidence/read_hash_probe.go)
and [samples](snapshot-latency-residual-evidence/read-hash.json) are retained.
