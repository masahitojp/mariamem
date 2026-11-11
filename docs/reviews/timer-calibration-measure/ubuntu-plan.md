# Retained timer candidate: Ubuntu and native confirmation

The Human retained this startup-improvement candidate and on 2026-11-11 asked
to proceed while investigating collation initialization independently.
This is a bounded runtime confirmation, not adoption, Qualification or release.

The orchestration source is the exact CI head on
`experiment/timer-ubuntu-native`. Its workflow checks out host source
`f225968c332a692f5bce189b31aed1fab26e642a` separately. The existing development
guest comes from source `1731c394031b781ff813190bf9c42bee63516044`,
run 42928025946, artifact 13814809081. The script pins its archive and WASM
digests and preserves the original guest source identity. No source-origin
allowlist is widened to accept workflow changes. Existing CRC, thread ownership,
data-image and generated-code guards still apply during host regeneration.

One Ubuntu 24.04 x86_64 job regenerates the development Go host and runs:

- Existing SQL/transaction/Snapshot smoke.
- PyMySQL TCP ANALYZE timing: Fresh and two isolated children, three ordinary/
  delayed pairs each; row/loop counts, subsequent SELECT and cleanup.
- The identical SQL profile on native MariaDB 12.3.3. Existing acquisition guards
  assert container binding, per-program hashes/version/architecture and source.
  Native phases recreate the two-row table; they do not claim native Snapshot
  semantics. Timings need not be equal: each delayed report must be at least
  18ms and at most its client wall plus 5ms.
- The existing Go Pipe delayed SQL probe and one lifecycle batch (8 Fresh,
  16 isolated Forks), including zero remaining mappings.

This closes platform/SQL questions only if the run passes. A single lifecycle
batch is not a before/after Ubuntu performance comparison. The six-pair Mac
startup result and inconclusive shop70 result retain their original identities.
No whole-suite speedup or absence of regression is claimed.

Budget: one host generation and one Pipe test compilation, 45-minute command
bound, 55-minute CI job, 12GiB scratch budget and 6GiB free-space floor.
All build/download/cache state is on the disposable hosted runner. The uploaded
evidence contains exact source identities, native acquisition, full development
binding, raw bounded SQL/lifecycle results, assessment and checksums. It contains
no guest or host binaries. On failure the log/assessment is retained; no retry
or exception changes PASS criteria.

UCA work proceeds on a separate source/experiment branch without the timer
patch, so its attribution cannot be combined with these measurements.
