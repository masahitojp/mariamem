# Issue #68: read4 residual queue / worker diagnostic

2026-11-02 bounded diagnostic; no scheduling/configuration correction.

**Inconclusive on the original question:** the residual read4 ~400ms COUNT
wait did not reproduce in the three authorized diagnostic processes. We cannot
say whether those residual waits use the previously observed pool mechanism.
Do not change another parameter, shorten timers or implement waiting-accounting
corrections on the strength of this trace. Keep #68 open and stop at the fixed
budget. If continuing, first reduce observation overhead rather than increase
runtime scope.

The material limit is that the recorder itself changes scheduling. The previous
[phase trial](read-io4-evidence.md) observed read4 COUNT waits of367–388ms; these
remain evidence of an unresolved symptom. This new zero-tail sample does not
supersede them with a success claim. It also does not disprove a common queue
cause: the slow COUNT/queued-task/pool-policy timeline needed to decide it is
missing. The new child-specific slow-case reduction branch therefore has no
real residual case exercised by this receipt; normal span/binding checks and
negative controls are the mechanically verified part.

## Results

| Fresh process | Children | COUNT maximum | Queued task maximum, all instances | Page-read wait maximum | Dropped |
| --- | ---: | ---: | ---: | ---: | ---: |
|0 |48 |51.109ms |39.776ms |39.611ms |0 |
|1 |48 |53.874ms |38.053ms |39.906ms |0 |
|2 |48 |50.462ms |59.722ms |49.487ms |0 |

No COUNT, queued task or instrumented page-read wait exceeds100ms. All144
children pass pristine rows, independent mutation, effective settings and cleanup.
Each process has49 unique instance bindings (root−1 plus48 child indices),48
client COUNT spans and every child's expected pool sequence
16→4→16→4→16. The trace records1,037,785events in total, capped at1million per
process; no dropped events. Duplicate binding and dropped-event negative
controls are rejected.

| Exposure check | Process0 | Process1 | Process2 | Total |
| --- | ---: | ---: | ---: | ---: |
| COUNT begins with effective pool concurrency4 |40 |38 |32 |110/144 |
| COUNT overlaps startup background buffer-pool loading |40 |38 |34 |112/144 |

Thus this was not simply a test where all background loading ended before SQL.
The overlap/low-concurrency condition occurs without the long symptom here.
The additional worker/queue state combination that produces the residual wait
is not identified. The observation does not establish that instrumentation caused
the absence, nor estimate the natural failure frequency.

## What remains missing and a bounded next option

A deciding case needs the **same child** to show slow COUNT, pending task
submit→start delay, contemporaneous active/waiting/long-task accounting,
concurrency changes and maintenance/worker-start events. The recorder supports
those associations, but there is no such slow case in this receipt.

If the Human continues #68, a focused next option is a lighter per-instance
queue/pool recorder: retain task, binding and pool-state events while removing
routine full stack capture and AtomicWait/Notify event volume. It must still
retain the pre-stall sequence; a stack captured only after100ms cannot recover
an earlier scheduling decision. Reuse the same source/workload with at most
three fresh P8/48-child processes again. Expected cost is one same-size local
Go rebuild (several minutes), three short observations and no heavy CI. This is
an estimate/proposal, not a launched or approved extra campaign. No change to
read/write/purge/timer policy is justified by this checkpoint alone.

At source level, `maybe_wake_or_create_thread` compares active−long−waiting
against configured concurrency; `set_concurrency` only updates the value, and
maintenance also has a separate stall fallback. These are alternatives to check
in a captured case, not a declared cause of the uncaptured residual COUNT.
The reduction keeps normal-policy versus maintenance-fallback add-thread call
stacks separate and records preceding/during-COUNT policies when a case exists.

## Observation contract

Product source remains v0.6.0. Read I/O is4, effective write2/purge1/nativeAIO0;
cache loading and the400/500ms pool policy are unchanged. The same pre-start
argv selector and optional guest-file bridge from the preceding trial remain.
Existing queue/read/pool/AtomicWait/Notify instrumentation is reused. A new
instrumentation-only binding copies each public caller's child pprof label to
its per-instance transfer key, then records the newly constructed Module's
instance ID before guest execution. Root is labeled−1. This associates client
COUNT child indices directly with the guest pool; temporal overlap between
independent DBs is not used to guess the association.

Three fresh processes, parallel8 with48 children each, are the complete runtime
budget. Missing slow cases do not authorize additional repeats. All SQL/seed,
independent update and cleanup oracles are unchanged. Trace cap is1million
events/process; dropped events or missing/duplicate child-instance bindings fail
the observation. Queue counters are pool workers, not a count of physical Go OS
threads. Event timestamps share the host monotonic origin; optional guest phase
marks keep their own clock and are not subtracted from host offsets.

This recorder takes stacks/locks, retains data and changes scheduling. Its timings
support event attribution, not a performance comparison against plain runs. No
setting/timer/wait-accounting fix is tested here. Native parity and Ubuntu are
not part of this bounded local diagnostic.

## Identity and retained evidence

- Product source commit: `b3b3b46a8807482ad3f96725af86e031fe369b01` (v0.6.0);
  tag object: `b57183b08d48884840111e8b53daa500734337f0`.
- Measured harness source: `28343c8ca79e15ebd1202b90e386fe343847ed24`.
  Exact clean product/tag/source is checked with scripts/git_identity.py before
  build. Go1.27.3, macOS27.2 arm64, Apple M1/16GiB, GOMAXPROCS8, CGO0.
- One diagnostic binary for all3 processes, SHA256
  `418a716f33525ca061c868470f549c5d0b617f57ae618fdcdc4127233c5a2c0c`.
  All13 overlay before/after hashes and clean Go build information are in compact
  inputs. The pre-start argv selector sets read4; canonical guest WASM remains
  unchanged, not relabeled as a newly built guest. No main/product/API patch.
- Pinned MariaDB source: `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`.
  tpool_generic.cc, buf0rea.cc and srv0start.cc hashes are in source-identity.json.
  They are verified against the prior source archive. Generated-function names
  are structural source correspondences, not a new original-WASM symbol map.

[Compact](forkcompare/results-read4-queue/compact.json),
[summary](forkcompare/results-read4-queue/summary.json),
[source identity](forkcompare/results-read4-queue/source-identity.json),
[negative controls](forkcompare/results-read4-queue/analysis-verification.json),
[raw reference](forkcompare/results-read4-queue/raw-reference.json),
[checksums](forkcompare/results-read4-queue/SHA256SUMS.json).

Raw archive is raw.tar.gz at commit
`d0ecbb8cc597acd615c6225ed1192c3d2ba51e47`, ref
`evidence/read4-queue-20261102`,11,022,773bytes, SHA256
`4f6dd9ee3489cbb639d1fc80d1dd67c8416ad978cc898023ace0631174c2d4a8`.
Its477members retain full events/stacks, reports, phase files, samples and
pinned upstream source, with original/published member hashes for workspace
prefix normalization. Raw events remain on the evidence ref; this branch keeps
compact knowledge. Old receipts and their source identities are not relabeled.

Read-only check after disposable build cleanup:

```sh
python3 benchmarks/forkcompare/analyze-read4-queue.py --results benchmarks/forkcompare/results-read4-queue --check
```

For full reduction, extract the checksum-verified archive and add
`--evidence <raw-directory>`. The checker validates client/instance bijections,
normal task/wait span pairing, zero dropped events, exact compact/summary and
checksums. Submitted background tasks canceled during ordinary shutdown are
reported as unexecuted, never given invented start events. The analysis code
was optimized/extended after execution; measured runtime/binary identity stays
bound to the earlier harness commit.

A fresh runtime reproduction uses the measured harness source in a disposable
workspace, the pinned product clone at temp/product and queue-run.py copied to
evidence/run.py. Run --phase build then --phase measure. Three processes is the
fixed cap; a new run needs a new evidence directory/receipt. No extra repeats,
engine/host policy fix, guest rebuild, native/Ubuntu comparison, CI, main
integration, qualification or release were performed.
