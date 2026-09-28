# v0.2 FAST status after the Aria cache experiment

## Decision

**Reject Aria page-cache reduction from 128 MiB to 16 MiB.** Production stays at
128 MiB. At ordinary ready state, the paired saving was only about 4–6 MiB per
DB. A separate Aria workload whose `.MAD` file was about 62.5 MiB saved about
108 MiB on macOS and 116 MiB on Ubuntu after workload execution, but regressed
wall time and CPU in all five pairs on each platform: about 6–7% on macOS and
10–11% on Ubuntu. Correctness, Snapshot/Fork isolation, temporary-table checks,
repeated cleanup and the existing lifecycle suites passed. The memory trade-off
does not justify the latency/CPU cost. Do not continue by tuning other MariaDB
caches in v0.2.

The complete A/B protocol and evidence are in [Aria cache results on run
36371206896](https://github.com/masahitojp/mariamem/actions/runs/36371206896).
The report's macOS CPU counters were corrected using the recorded Mach timebase.
The control used the production-effective 128 MiB setting; the 16 MiB condition
does not appear in the latency waterfall below. This was an experiment harness
and guest carrying a test-only selector, not a newly accepted production build.
The common WASM was reused at build identity `54b046bc3059b14d114192e10c5b1b21d38b8b24`;
the measurement/harness source was `b2e84fe94fc60d13feaee39cfad9e10bebf1b975`.
The downloaded macOS and Ubuntu result JSON SHA256 values are respectively
`c7f63584dd9d2ade6143b1742da63e37b63714b2e3f6e6dc5e35ab1f689bec8c` and
`19d60810f9ae5cbfa3fefe20dcd63f2c0b8bd718fef9d7ffc4cd75044d8de72d`.

## Current scoped CPU and memory baseline

The same successful control run recorded host plus runtime CPU from G(0) to
all-ready collection, and incremental ready memory relative to G(0). CPU is
CPU-sec per DB, p50. Memory is MiB per DB, p50. ×4/×8 averages use
`(G(n)-G(0))/n`; they are not independent concurrent marginal samples.

| Platform / primary memory measure | CPU ×1 / ×4 / ×8 | Incremental memory per DB ×1 / ×4 / ×8 | Marginal growth per DB, 1→4 / 4→8 |
| --- | ---: | ---: | ---: |
| macOS 15.7.9 arm64 / physical-footprint accounting | 0.379 / 0.499 / 0.554 | 243.96 / 245.50 / 250.73 MiB | 246.0 / 254.8 MiB |
| Ubuntu 24.04 x86_64 / PSS | 0.520 / 0.562 / 0.572 | 398.81 / 342.34 / 331.67 MiB | 321.6 / 322.1 MiB |

At ×1 the corresponding CPU p95 values were 0.397 sec on macOS and 0.550 sec
on Ubuntu. CPU includes host/runtime work and benchmark sampling in the same
collection interval; it is comparative, not complete process accounting.
At ×8, CPU amplification was 1.492× on macOS and 1.092× on Ubuntu (matched
rounds, p50). The memory measures are platform-specific: macOS footprint is an
accounting charge, Ubuntu PSS can shift with sharing, and neither is a globally
unique physical-memory measurement. Raw RSS and Linux private bytes remain
secondary evidence. Brief peaks may be missed by sampling.

The FAST product latency KPI remains ×1 p50 ≤500 ms and p95 ≤750 ms on both
platforms. The 250/500 ms figures remain a longer-term stretch; 600/900 ms is
only a regression/debug red line. The measured CPU and memory values above are
baselines, while <0.5 CPU-sec/DB, ×8 amplification ≤1.5×, <256 MiB/DB and <2 GiB
incremental at ×8 are provisional budgets, not hard CI gates or promises.

## Current 128 MiB control waterfall

This is the ×1 control from the final Aria run: 20 balanced rounds, two warmups,
the standard 1,000-row fixture, Go 1.26.8, embedded MariaDB 13.1.0, macOS
15.7.9 arm64 / 3 visible CPUs and Ubuntu 24.04 x86_64 / 4 visible CPUs. Each
stage's p50/p95 is computed from its own per-instance samples. Parent and child
intervals overlap, and percentile columns must not be added as if they were one
sample.

| Stage | macOS p50 / p95 ms | Ubuntu p50 / p95 ms |
| --- | ---: | ---: |
| Fork → first successful SQL | 358.9 / 394.8 | 532.2 / 557.1 |
| Caller/API work outside the host trace, derived | 49.8 / 56.6 | 65.9 / 66.7 |
| Host artifact/metadata/snapshot validation | 74.0 / 78.4 | 105.2 / 106.1 |
| Remaining host preparation + process spawn | 1.1 / 2.0 | 0.4 / 0.5 |
| Spawn returned → guest ready, host-measured inclusive interval | 226.0 / 250.5 | 353.2 / 378.6 |
| └ Guest snapshot restore | 122.9 / 144.1 | 222.6 / 235.0 |
| └ MariaDB `mysql_server_init()` | 54.4 / 72.0 | 91.0 / 111.0 |
| └ Outside guest-recorded events within spawn→ready, derived residual | 39.7 / 45.3 | 39.8 / 42.0 |
| Guest-ready → host startup end | 0.2 / 0.5 | 0.1 / 0.1 |
| Client connect after Database return | 5.4 / 7.6 | 6.4 / 9.3 |
| Connection ready → first SQL | 0.8 / 3.0 | 0.9 / 1.0 |

The derived caller/API interval is total public startup duration minus the
measured host startup duration. The current trace does not split it into work
before host startup and work after host return. The spawn→ready residual is the
host-measured wait minus the duration covered by guest events; it is not
attributed to Wasmer, runtime initialization, or any single subsystem. These
are the two principal attribution gaps. Guest open/bootstrap/ready events
outside restore and MariaDB initialization were each sub-millisecond at ×1.

### Interpretation against the accepted production baseline

The accepted canonical baseline in [the first FAST tranche report](fast-tranche-baseline.md)
remains 516.9/688.7 ms on macOS and 539.2/566.4 ms on Ubuntu. In the latest
unchanged 128 MiB control, Ubuntu measured 532.2/557.1 ms: around 32 ms above
the p50 target, while p95 remains below its target. The accepted Ubuntu run was
about 39 ms above p50. The latest macOS control measured 358.9/394.8 ms, but
another unchanged control measured about 576 ms; retain 516.9/688.7 ms as the
canonical reference and treat that spread as hosted-runner variability, not a
product improvement.

On Ubuntu, restore (223 ms), host validation (105 ms), and the derived
caller/API interval (66 ms) are individually large enough to investigate for a
30–50 ms contribution. MariaDB initialization is 91 ms, but the cache experiment
shows that shrinking Aria to 16 MiB is a poor trade. On macOS, the latest
control's measured components were all lower than the accepted run; that
cross-run difference does not establish a code-level cause. The smaller
connection/first-SQL stages cannot plausibly close a 30–50 ms gap by themselves.

## Candidates for the final v0.2 latency improvement

1. **Split and inspect caller/API work outside the host trace.** It measures
   about 50 ms on macOS and 66 ms on Ubuntu, enough in scale to cover the
   remaining gap if an avoidable operation is present. The trace combines
   pre-host and post-host work, so removable cost is not yet known. Attribution
   is low risk; optimizing it before splitting the interval would be guesswork.
2. **Investigate the existing host validation implementation without skipping
   integrity checks.** Its measured ×1 interval is 74 ms on macOS and 105 ms on
   Ubuntu. It is large enough, but repeated validation was already reduced
   within a startup call; the remaining checks are mandatory. Correctness risk
   is medium/high, and no safe removable portion is established.
3. **Revisit the restore source-read boundary with a tail-safe narrow probe.**
   Restore costs 123 ms on macOS and 223 ms on Ubuntu here. Direct WASI reads
   previously yielded only about 30–40 ms end-to-end and were rejected because
   parallel-tail behavior was unresolved. Potential scale is relevant, with
   medium/high regression and maintenance risk; no production change is
   justified by the current evidence.
