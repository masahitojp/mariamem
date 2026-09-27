# Prepared-key restore attribution probe

This experiment stays on `experiment/prepared-auth-keys`. Measurements are pending
its dedicated CI run; the previous ~156 ms macOS / ~226 ms Ubuntu restore medians
are context, not measurements of these subdivisions.

## Source facts: the actual restore path

`Snapshot.Fork` validates snapshot inventory and native metadata, then host startup
launches Wasmer with the immutable snapshot directory mounted at `/snapshot-in`.
These host integrity checks are outside the guest restore timer. Wasmer mount setup
before guest main is also outside it.

Before `l4m_open`, guest `snapshot_copy("/snapshot-in/data", "/mariadb", 0)` recursively
uses `lstat`, directory creation/enumeration, exclusive destination creation, and
64 KiB `fread`/`fwrite` chunks. `/mariadb` is the guest's unmounted memory filesystem.
Source and destination streams are closed afterward. No explicit fsync is performed.
There is no additional Go-host per-Fork snapshot-copy loop. Snapshot export uses the
same routine in the opposite direction after shutdown; this probe records restore only.

## Instrumentation and measurement

The opt-in `restore_copy` member of startup JSON records monotonic wall time,
process and current-thread CPU, call counts and logical bytes for:

- directory/stat metadata and enumeration
- source open
- exclusive destination creation
- source reads, including the final EOF read
- destination writes
- source close
- destination close, including possible stdio flush

A bounded inventory records each file's size, inclusive file-copy wall time, and
operation counters/times. Overflow, invalid clocks or byte reconciliation failures
reject the measurement. Per-file inclusive time starts after `lstat`; metadata is
separately aggregated. Untimed bookkeeping and instrumentation appear in the total
minus exclusive-operation wall times, not in an invented runtime attribution.

Run via the existing guest-boundary workflow's `restore_attribution=true` input.
The canonical Go runner uses 1,000 rows and workers 1/4/8, 20 measured pairs and two
warmup pairs. Both conditions use the **same** existing test RSA keys and disposable
within-call validation-reuse patch. Existing auth checks require the enabled plugin,
loaded keys and matching public key, with no generation. Alternating control/probe
order measures instrumentation perturbation: control disables restore counters;
probe enables them. No expensive memory diagnostics are requested.

This source instrumentation changes the guest identity, requiring one WASM build
and platform AOT rebuild. Subsequent matching inputs reuse verified immutable
artifacts. No production provenance is reinterpreted.

Raw pair JSON, lifecycle summaries and `summary.json.restore_copy` provide p50/p95,
raw per-DB observations, per-file rankings and CPU/call/byte observations for each
platform and concurrency. Artifacts remain ignored locally and are uploaded under
`initialization-<platform>-<candidate>`; `init-restore/` contains the results.

## Remaining blind spots and interpretation

`fread` includes libc buffering, WASIX/runtime transfer and host-volume access;
those internal boundaries are not separated. `fwrite` includes guest buffering and
runtime memory-filesystem work. Logical reads/writes do not establish physical disk
traffic or a removable duplicate copy. Process CPU can include other runtime threads;
current-thread CPU is closer to the synchronous copy path. RSS is not re-attributed.

Measured facts about largest components, dominant files, concurrency degradation,
and platform agreement must await this run. No new p50/p95 or causal conclusion is
claimed here. Compare per-file elapsed time against byte share; redo/system/undo
files are candidates, not assumed culprits. Paired control-minus-probe differences
bound instrumentation impact; do not add marginal medians to reconstruct a sample.

## Recommended restore experiment

Conditional on reads/writes dominating measured restore, the smallest next probe
is a disposable copy-only microbenchmark of the existing snapshot inventory through
this same mounted-source/memory-destination path, varying only file size distribution
at constant total bytes. This distinguishes byte cost from per-file overhead before
choosing storage architecture. Do not implement it until the attribution run is read.

## FAST tranche integration checkpoint

**Prepared RSA keys:** causal latency evidence is sufficient to stop further RSA
attribution and consider productionization separately. Production acceptance still
needs an explicit provisioning/lifetime/security policy, missing/corrupt-key failures,
actual auth-handshake coverage (current startup retains grant bypass), and packaged
Go/Python lifecycle, snapshot/fork, concurrent sessions and interrupted-query cleanup
on both supported platforms. This test-only key path is not merge-ready.

**Within-call validation reuse:** paired evidence is sufficient to consider a small
production change separately. Preserve mandatory snapshot/native integrity checks;
define ownership of the verified identity, test mutable native directory/sidecar
changes and failure paths, and run packaged lifecycle/cleanup coverage on both
platforms. The disposable read-only-input probe is not a production trust cache.
Neither change is integrated by this task.
