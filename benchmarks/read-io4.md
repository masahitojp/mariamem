# Issue #68: read I/O threads 1 versus 4

2026-11-02 bounded configuration experiment; product adoption remains separate.

**The read-I/O setting of 4 is a promising minimal guest configuration candidate.**
In the fixed six-process plain trial, read=1 had three COUNT delays of
375.960 / 401.760 / 784.487 ms; read=4 had none above 100 ms (maximum 51.928 ms).
All three paired batches were shorter, and all 288 children passed data,
isolation and cleanup checks. The recommendation is to prepare the smallest
reproducibly rebuilt guest candidate using read=4 for adoption review.

The strongest limit is the small local sample: zero slow cases among 144
children does not prove the tail is eliminated across platforms/workloads.
The candidate is supported by both its targeted mechanism and matched before/
after results; this is enough to continue to a candidate, not claim a universal
fix or integrate the experimental generated-byte overlay into main.

## Fixed primary results

Each cell is one fresh process running 48 children at parallelism8; pair order
was 1→4, 4→1, 1→4.

| Pair | read=1 batch | read=4 batch | read=1 / read=4 COUNT >100ms |
| --- | ---: | ---: | ---: |
| 1 | 734.460 ms | 644.650 ms | 0 / 0 |
| 2 | 1,442.091 ms | 672.742 ms | 1 / 0 |
| 3 | 922.241 ms | 761.979 ms | 2 / 0 |

| Metric | read=1 | read=4 |
| --- | ---: | ---: |
| Batch median | 922.241 ms | 672.742 ms (−27.1%) |
| COUNT median | 4.393 ms | 4.460 ms |
| COUNT p95 (floor-index empirical) | 18.011 ms | 13.011 ms |
| COUNT maximum | 784.487 ms | 51.928 ms |
| Batch CPU time median (summed across cores) | 3,840.460 ms | 3,776.880 ms |
| 20ms-sampled peak RSS median | 698.609 MiB | 697.609 MiB |
| Lifetime peak RSS, highest of 3 processes | 699.281 MiB | 732.953 MiB |

Median COUNT latency hardly changes; the observed benefit is the long tail and
whole batch. CPU time does not show a consistent penalty in these three pairs
(the third read=4 process uses more CPU). Sampled RSS medians are close, but the
candidate's highest lifetime peak is about34MiB higher. Sampling can miss short
peaks, and these numbers do not establish resource equivalence or a v0.7 resource
acceptance campaign.

## Diagnostics and setup correction

Two fresh P8/8-child diagnostic pilots each have zero dropped events and all
SQL/isolation/cleanup oracles pass. All children show
`16→read_io→16→read_io→16`, confirming that read=4 changes both startup recovery
and background buffer-pool-load restrictions from1 to4. These effects cannot be
attributed solely to the latter path by this experiment.

Diagnostic batch times were928.143 /181.605ms for read1/read4, but their COUNT
maxima were26.908 /32.875ms. The diagnostic batch difference is **not** an
800ms COUNT reproduction; only the separate plain primary records above
establish the long COUNT waits in this trial.

Before those two pilots, one initial baseline diagnostic completed its SQL and
cleanup but failed the driver's expected-write=1 assertion. SQL observes write=2;
pinned upstream `ha_innodb.cc` lines19649–19652 sets its minimum to2. The failed
setup observation is preserved under `preflight/` in raw evidence, excluded from
the accepted pilots and primary comparison, and never relabeled PASS. The
corrected driver then ran two fresh pilots. Actual execution was therefore
one setup diagnostic + two accepted diagnostic pilots + six primary processes
(8 +16 +288 children), with no extra primary repeats.

This also corrects the earlier conversation's distinction: **recipe arguments**
are read1/write1/purge1, but the baseline **effective SQL values** are
read1/write2/purge1/nativeAIO0. The candidate is read4/write2/purge1/nativeAIO0.
Wrong-write-profile and false-oracle analysis mutations are rejected.

## Change and validity boundary

The only guest-policy difference is the startup argument
`--loose-innodb-read-io-threads=1` → `=4`. Write I/O remains argument 1 / effective 2, purge remains 1, native AIO
remains disabled, and startup buffer-pool loading and pool timer policy remain
unchanged. SQL observes all four settings on the root and every child.

For a small experiment, a Go build overlay changes exactly one byte in the
pinned generated guest's embedded startup-argument data. It preserves segment
lengths and pointer offsets. This executes the existing MariaDB option parser;
it does not assign an internal concurrency field directly. A canonical guest
patch, rebuilt WASM and reproducible generated candidate have **not** been
produced, so this receipt supports a configuration hypothesis, not adoption of
new release artifacts.

Two diagnostic P8/8-child pilots verify pool configuration events; detailed event
hooks are absent from the six primary P8/48-child processes. Those plain builds
only add no-op compatibility functions for the existing harness calls. Both use
the same client-side timing/wire observations; latency-triggered stack capture is
disabled for primary timing. Profile-query observations after child verification
add the same work to both variants' total time/CPU. This is a small local
comparison, not an isolated-machine benchmark or native MariaDB comparison.

The fixed order is 1→4, 4→1, 1→4, each pair in fresh processes. No extra repeats
are allowed to obtain a desired result. GOMAXPROCS8, TCP, the 1,000-row seed,
Snapshot/closed root, isolated child mutation and cleanup are shared. The root
and each child use one application connection. No canceled/failed run is
counted as a normal PASS.

## Identity and reproducibility

Product v0.6.0 source commit `b3b3b46a8807482ad3f96725af86e031fe369b01`;
tag object `b57183b08d48884840111e8b53daa500734337f0`. The driver checks exact
source/tag identity and a clean clone using `scripts/git_identity.py` before
build, then records clean harness VCS identity and binary hashes. Go1.27.3,
darwin/arm64, Apple M1, 16GiB, macOS27.2, CGO0, GOMAXPROCS8.

The earlier [source attribution](sql-concurrency.md) owns the upstream/recipe
correspondence. This trial changes the setting it identified, not the old receipt.

The binary harness commit is `cba5bff8` (full SHA in compact inputs); the corrected
execution driver is `01d3c7d2` (full SHA in driver identity). Their only differences
are run.py, analyze-io4.py and plan.json, asserted before execution: runtime,
probe and overlay source trees are identical, so already-built binaries retain
their original clean build identity. The build-time plan retains its original
write=1 expectation as historical input; executed-plan.json records the corrected
effective-value assertion. No receipt source identity is relabeled.

[Compact records](forkcompare/results-io4/compact.json),
[summary](forkcompare/results-io4/summary.json),
[driver identity](forkcompare/results-io4/driver-identity.json),
[executed plan](forkcompare/results-io4/executed-plan.json),
[analysis controls](forkcompare/results-io4/analysis-verification.json),
[raw archive identity](forkcompare/results-io4/raw-reference.json),
[checksums](forkcompare/results-io4/SHA256SUMS.json).
Compact retains the configuration event stacks and selected per-child fields;
full wire/operation timings and unrelated diagnostic stacks remain in raw.
All variant binary hashes and generated-overlay before/after hashes are in
compact inputs. Plain baseline adds only the compatibility stub; plain candidate
adds that identical stub plus the single-byte startup string change.

Raw archive: commit `e400bb9bb433be3530ca01e347de3a02f816de08` on
`evidence/read-io4-20261102`, path raw.tar.gz, 1,972,167bytes, SHA256
`08220e5d7942b5daa7054027ac4f22801efa8929158bf84064dc7a0fc907de11`.
Its60members include raw reports, diagnostic events, 20ms RSS samples,
failed-setup observations, input/config/overlay hashes and the write-minimum
source excerpt. Workspace prefixes are normalized with original/published hashes.
Raw events are not frozen into this report branch.

Read-only verification after build/temp cleanup:

```sh
python3 benchmarks/forkcompare/analyze-io4.py --results benchmarks/forkcompare/results-io4 --check
```

To verify full reduction, extract the checksum-verified raw archive and add
`--evidence <directory>`. Checks assert the fixed profiles and child counts,
SQL/cleanup oracles, diagnostic pool sequences, exact compact/summary bytes and
all retained checksums. They do not impose a performance threshold on later runs.

Reproduction uses the corrected driver commit, a disposable workspace and the
pinned product in temp/product. Copy benchmarks/forkcompare/run.py to evidence/
and run --phase build, --phase pilot, --phase measure. A fresh build records its
own clean harness source identity; it does not inherit these binary identities.
The driver enforces Go/platform/source pins and disk/process deadlines. Repeated
execution must use a new evidence directory and produces a new receipt.

No guest WASM rebuild, product/API/main integration, hosted CI, native comparison,
qualification or release was performed. The experiment ends at the fixed
comparison and candidate recommendation.
