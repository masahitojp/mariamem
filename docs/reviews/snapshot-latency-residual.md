# Human Review — Snapshot latency residual on the current guest

**Decision now:** authorize a bounded design spike on reducing redundant
Snapshot data passes, without implementing or integrating an optimization yet.
I recommend that spike if Snapshot creation latency is a product priority: on
the current MariaDB 12.3.3 guest, the measured 100 MiB logical fixture takes
about 0.71 s to Snapshot, and its traced operation spends about 0.39 s in three
read/hash stages plus 0.20 s in host copying. The strongest objection is that
these passes help enforce content integrity and independent ownership. A faster
path is unacceptable if it weakens corruption detection, atomic publication or
the consumed-source contract. The spike should stop if it cannot show how those
properties survive; this report recommends no runtime change or release action.

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

To estimate hash CPU without changing the runtime, one explicitly exported
100 MiB fixture was read by a [read-only Go probe](snapshot-latency-residual-evidence/read_hash_probe.go)
using two workers and 32 KiB buffers. It contained 11 regular files and
274,746,682 bytes. Seven alternating pairs followed one retained warmup pair;
every read counted the same bytes and all SHA-256 digests remained stable.

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

## Proposed bounded next step and stop condition

If the Human wants lower Snapshot creation latency, limit the next spike to
one proposed host-side pass reduction on an experiment branch. Map each current
read/hash/copy pass to its integrity and ownership purpose; identify one pass
that might be combined; construct corruption, partial-copy, source-consumption
and independent-Fork oracles before timing it. Compare against the exact
current guest and stop at a design/reject/integrate recommendation. A safe
scheme that cannot preserve these checks is rejected even if faster. This is
roughly a one-engineer-day feasibility task, not an estimate for production
implementation or cross-platform qualification.

If that work is not a product priority, retain the current behavior: the
measured 0.34–0.71 s Snapshot cost is paid once when a prepared baseline is
created, while repeated Fork readiness is separate. Reopen optimization when
a representative fixture/reuse count and target latency make the cost material.
No source restart, InnoDB shutdown-mode change, pass removal or public API
change is made here. The [normalized campaign script](snapshot-latency-residual-evidence/campaign.py)
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
