# v0.4.6 bounded product validation

The question is whether measured time differences make disposable isolation useful,
not which MariaDB engine is faster. See the [Human Review](../docs/reviews/v046-human-review.md)
for the suite table and product recommendation. Results are observations, not performance promises.

## Inputs and boundaries

macOS arm64, 16 GiB RAM, Go 1.27.1 (`GOTOOLCHAIN=local`), Python 3.14;
Docker Desktop arm64 VM ~7.75 GiB. Native image was pre-pulled (pull excluded):
`mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1`,
MariaDB 12.3.3 versus embedded 13.1.0. No native 13.1 image was available in the probe;
the PO accepted this limited comparison. Native/default embedded InnoDB buffer pools
were 128/16 MiB. Server settings are in competitive raw JSON; architecture, version,
durability/storage and VM differences prevent causal engine-speed attribution.

One campaign at a time; explicit workspace budget 12 GiB/minimum free 8 GiB,
per-cell timeout 900 seconds. Python native containers bounded to 768 MiB/2 CPU,
maximum four workers. Image pull, compilation and tool installation excluded.
Three trials per normal cell; one 100 MiB supplementary trial. Four tests per suite.
Rows have deterministic payload, fixture/large use eight tables; two application
connections exercise commit/rollback, point reads and COUNT. These are setup-heavy
synthetic workloads, not real migration-framework acceptance.

Go Fresh/Fork uses existing ownedprepared, native Go uses competitive (a separate
1,000-row ×32-byte, one-table fixture), Python is a small adapter, not a new framework.
Preparation and Snapshot are charged once to Fork. Fresh setup is charged per DB.
Shared mode charges one container start, then schema creation/drop per test; it is
not transaction-only rollback isolation. It cannot discard shared server-global state.

Go suite_product_seconds excludes diagnostic counter helpers/GC. Go CPU includes
benchmark/diagnostic overhead and excludes counter-helper child CPU. Python wall
includes one-shot resource observations (~40 ms for a serial suite); Python CPU is
runner+reaped host/helper children and excludes Docker VM/container CPU. Container
CPU/memory samples are separate and cumulative for shared mode, not peaks.
Do not compare Go versus Python totals as a language-speed result.

Go binaries were built from `5824ed1f205c84fc67574d6896afba412b57188b`;
Python final adapter/caller was `ff43ffef6ded67b3f37079831acc9f8e5bad8226`.
Only Python observation changed between these commits: unchanged Go measurements
were reused. A caller source_commit in competitive records is distinct from its
embedded go_build_info source. Library source fingerprint remained
`8f19dd85cd6e39b94c32b6bf66ae0c9b03e09e6b56687b4dc9e375088fc212c2`.

## Supporting observations

Go four-way 1,000-row suite medians: Fresh 0.632 s, prepared 1.891 s,
Testcontainers fresh 24.441 s, shared schema reset 6.873 s.
These are not the 10 MiB matrix; preparation is too light to justify Snapshot there.

Go 10 MiB four-parallel ranges: Fresh 1.350–3.473 s, Fork 1.727–6.171 s.
Python same class: Fresh 2.012–2.131 s, Fork 1.667–2.483 s.
Do not remove slow samples or claim universal parallel gains.

Go median suite CPU seconds:

| Case | Fresh | Fork |
| --- | ---: | ---: |
| Light | 0.342 | 0.851 |
| 10 MiB serial | 3.546 | 2.346 |
| 10 MiB four-parallel | 4.940 | 3.117 |

Go after-Close plus diagnostic-GC physical footprint medians (MiB):
light 176.1/431.8, fixture 328.3/392.1, parallel 446.6/485.6 (Fresh/Fork).
These are process-level samples, not retained DB allocation or peak measurements.
FD 5→6 reflects one-time network poll initialization; warmed consumer FD remained
13→13. Prepared mapping extents returned to the initial binary-mapping extent.
Neither RSS nor physical footprint must return to zero. Existing harness did not
record HeapAlloc; no HeapAlloc comparison is asserted.

Snapshot amortizes preparation; a broad COUNT still pays scan/read costs, especially
beyond the embedded 16 MiB buffer pool. Keep ready latency separate from query cost.

## Measurement corrections

An initial Python parallel container pilot failed due to concurrent Ryuk singleton
initialization (HTTP409); initialize the reaper before parallel workers.
A subsequent diagnostic attempt used Docker stats with an observation interval;
one-shot sampling removed that instrumentation delay. Neither incomplete/biased
attempt is pooled. Their reasons and bounded fixes are retained in validation.json.
No product/runtime optimization was made to improve these measurements.

[Compact raw results, summary and reproduction](v046-usability-evidence/README.md)
contain 72 non-pilot successful cells, including the six large supplementary cells.
