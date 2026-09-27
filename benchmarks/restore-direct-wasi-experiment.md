# Direct WASI source reads in actual restore

## Status

Implementation and local checks are ready on `experiment/restore-host-volume`.
**A/B results and accept/reject decision are pending the measurement workflow.**
Nothing is integrated into main. The rationale is recorded in
[the decision note](restore-next-experiment-decision.md); prior read-only results
are in [host-volume attribution](restore-host-volume-investigation.md).

## Only the import reader changes

One experimental WASM/AOT supports two private modes:

- `stdio`: production-style `fread` of the source, then existing destination
  `fwrite` into the guest memory filesystem.
- `direct`: the same source opened with `fopen`, read through its descriptor
  with one 64 KiB WASI `fd_read` iovec, then the identical destination `fwrite`.

The direct path retries WASI interrupted calls and handles short reads without
treating them as EOF. It fails on other read errors, and closes input/output
through the existing cleanup path. `fclose`, exclusive destination creation,
directory traversal, snapshot inventory, file sizes and destination filesystem
are retained. Export continues using stdio, with the import counters inactive.
RSA provisioning, engine configuration, validation and SQL/session behavior are
unchanged. No Wasmer/runtime modification is made.

Changes to guest helpers live in `guest/experimental.patch`. Preparation now
applies experimental diffs after canonical overlay installation so the helper
diffs are reproducible; their actual hashes and patch identity are recorded.
Canonical `guest/source.patch` and overlay files remain unchanged. Existing
release verification still rejects experimental provenance.

## Correctness separately from timing

Before measurement, the public Go fixture helper creates the normal 1,000-row
snapshot and verifies a real Fork/SQL. For each reader mode a diagnostic import
copies the snapshot into `/mariadb`, then uses the unchanged stdio export to
return that copied tree before MariaDB can alter it. Python compares every
directory/file entry, byte count and SHA256 against the verified snapshot
manifest and rechecks the source. This additional export/hash cost is recorded
as separate correctness setup, never treated as a restore optimization.

Both modes additionally run the maintained Go race/Python integration path:
Snapshot/Fork, sessions, multi-client isolation, interruption/unusable semantics
and cleanup. Missing/incorrect timing or mode evidence and byte/count mismatches
fail the experiment. Normal startup still requires the prepared keys.

Native C tests apply the exact experimental diff, checking byte-identical import
and export, empty/partial-chunk files, simulated short reads/EINTR, read errors,
occupied destinations and symlinks. Those tests validate the copy algorithm;
actual WASI ABI/runtime behavior is exercised by the two CI platform jobs.

## Paired measurement

`benchmarks/goisolation --restore-ab` reuses the canonical public API startup,
batch, SQL-readiness, sampler and cleanup implementation. One prepared snapshot
is shared across all batches. At ×1/4/8, two warmup rounds and 20 measurement
rounds execute both modes, reversing their order each round. Conditions switch
only after the preceding batch has closed completely. No global trust cache,
pre-staging or extra per-chunk checksum is introduced.

Raw samples include Fork → first verified SQL, read/write wall and process/thread
CPU, total copy wall/CPU, bytes/files/calls, guest-main → ready CPU, and canonical
runner CPU/approximate descendant observations. Guest-main CPU excludes runtime
pre-main, first SQL and shutdown; runner CPU is host/harness work, not guest CPU.
Process/thread clock brackets include diagnostic overhead. Both modes use the
same counters; absolute latency may differ from the less-instrumented production
baseline. A close acceptance result needs confirmation without per-read timing
before production integration.

`benchmarks/restore_read_ab.py` preserves canonical Go raw samples and adds
identity/environment, correctness results, p50/p95 per mode, and same-round
differences. Parallel paired differences use per-batch means, because worker
arrival order is not a stable pairing identity. Component percentiles must not
be added as a measured total. No expensive mapping/memory diagnostics run.

Dispatch `guest-build-boundary.yml` on this branch with
`restore_read_comparison=true`, other measurement inputs false. This guest change
requires a new verified WASM and both AOTs once; unchanged identities are reused
thereafter. Artifacts are `initialization-<platform>-<candidate SHA>`, containing
`init-restore-read-ab.json` and manifest/AOT provenance. Raw results stay ignored.

## Decision after artifacts arrive

Accept as a **production candidate**, not an integrated change, only if:

1. All content and lifecycle checks pass on macOS arm64 and Ubuntu 24.04 x86_64.
2. ×1 Fork → first SQL paired-median saving is at least approximately 25 ms on
   both platforms, with a consistent direction across the interleaved run.
3. Relevant read/copy/guest-startup CPU improves consistently, with host CPU and
   accounting limitations inspected rather than interpreting coarse zeros.
4. ×4/8 p95 latency and CPU show no reproducible regression. Conflicting/noisy
   evidence requires a bounded confirming run; it does not establish acceptance.

Otherwise reject the change as a production candidate. Read-only speedups alone
are insufficient. Results tables and the explicit decision will be added after
CI completes; this implementation does not assume the hypothesis is true.

If accepted, remaining production work includes a clean import-only helper on
main without experimental flags/instrumentation, focused error/cleanup tests,
uninstrumented confirmation, and exact packaged Go/Python acceptance on both
platforms with updated provenance. That integration and any restore architecture
changes are separate tasks. No productionization or release is authorized here.
