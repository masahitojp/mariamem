# v0.4.3 final generated-Go-only baseline

Measured source: `10fa4d1157c673f7eb7830802c584b774f221f00`; release metadata and production code clean before runs.
Retirement integration: `11353247d9bfda50d1309fd821dadafb50e45f3c`. Final report-only commit follows; it changes no production behavior.

macOS arm64, Go1.26.8, 8 CPUs (`GOMAXPROCS=8`). Unchanged public 1000-row v04_candidate scenario: 2 startup warmups +30 measurements; one warmup and one measured group per 1/4/8/16. All40 accepted trials pass. Compilation/installation precede timing. No other benchmark was observed in the monitored execution window.

| Boundary | p50 ms | p95 ms |
| --- | ---: | ---: |
| Fresh Start→SQL | 53.40 | 57.00 |
| Start→1000-row fixture | 66.65 | 72.29 |
| Snapshot | 351.01 | 368.10 |
| Fork→connect+1000-row COUNT | 124.74 | 133.47 |

Fork API-return p50: 121.29 ms; this is separate from subsequent client connection/query. Standalone SELECT1 p50: 0.165 ms. Fork group Close p50: 2.98 ms.

| Prepared children | All-ready ms (1 sample) | CPU s/DB | Incremental physical MiB/DB | Ready physical MiB | After-Close physical MiB |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 134.02 | 0.1591 | 80.33 | 504.44 | 429.50 |
| 4 | 183.34 | 0.1817 | 79.97 | 743.80 | 439.53 |
| 8 | 303.60 | 0.1993 | 78.27 | 1050.30 | 444.03 |
| 16 | 896.20 | 0.2020 | 76.98 | 1655.86 | 442.61 |

Physical footprint is primary on macOS; RSS is separately retained in JSON. Incremental subtracts the post-preparation baseline. CPU ends at all-ready counter collection and includes observer/version-query work; it is not pure guest CPU. After-Close retains prepared-base/Go filesystem/allocator state: no forced GC and no claim of zero total memory. This unchanged harness does not sample FD/goroutine/HeapAlloc; their existing deterministic/lifecycle evidence remains separate.

## Historical context and limits

| p50 ms | v0.4.2 mmap accepted campaign | v0.4.3 |
| --- | ---: | ---: |
| Start→SQL | 52.20 | 53.40 |
| Start→fixture | 63.46 | 66.65 |
| Snapshot | 374.87 | 351.01 |
| Fork→COUNT | 122.07 | 124.74 |

[v0.4.2 evidence](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md) used ten scaling measurements per size; this bounded closeout has one. Its ×16 ready median563.29ms versus this sample896.20ms is not a controlled regression estimate. Physical ready/after-Close are comparable (~1656/~443MiB historically). Existing startup tails remain: one Start→fixture exceeds900ms here. No tail optimization or broad repeat is justified by one scaling sample and unchanged generated/mmap/Snapshot code.

An initial GOMAXPROCS=2 calibration was accidentally inherited from compile throttling. It remains checksummed separately and is excluded from the canonical table; no slow trial within the accepted default-CPU campaign is removed.

## Verification and readiness

Focused Python SDK/artifact/release/source/license/workspace boundary tests:239 PASS. Go artifact/platform resolver tests PASS. Generated input/inventory/guest identity, version, public-source inventory, four retirement evidence hashes, skill validators and diff checks PASS. Prior retirement SQL/auth/sessions/Snapshot/Close/mmap/race/installed-wheel/SQLAlchemy44/GORM32 evidence is reused because product code is unchanged from the accepted retirement source; this is not final-source artifact READY.

Live Wasmer runtime selection/provisioning/packaging is retired; historical sources/notices and disabled reference scripts remain. Snapshot/Fork API, integrity validation and generated guest are unchanged. No OwnedPrepared/new ownership implementation, hash optimization or v0.5 upgrade is included.

One-shot release CI still must build/qualify this exact final SHA on macOS and Ubuntu, including consumers, corresponding GPL source/NOTICE/licenses/provenance, READY guard and (only when authorized) publication/public smoke. No tag/publication or redundant acceptance/guard dispatch occurred in this task.

Budget:6GiB owned disk,8GiB minimum free,8GiB sampled process-tree RSS, bounded timeouts. Both calibration and canonical campaigns complete without a budget violation; canonical sampled peak RSS is ~1.88GiB. Preserve these compact JSON/CSV/checksums and reproduction; delete binaries, cache/toolchain copies, venv and completed worktree.

Reproduce with the experiment-workspace prepare/run lifecycle, owned GOCACHE/GOMODCACHE, Go1.26.8, explicit disk/resource budgets and exclusive benchmark window. Run `python3 benchmarks/v04_candidate.py --json <evidence>/canonical.json --runs 30 --scaling-runs 1` with GOMAXPROCS=8. Full per-trial records are embedded in canonical.json; duplicate scratch JSON/logs need not remain.
