# Purge head/view comparison — pre-execution protocol

Approved scope: one small original-Wasm/Go comparison, at most two hours.
Production guest input is v0.5.2 source_commit
`47f297cc7498625e076abb93322eb616c9560bb8` (base package must be byte-identical).
No product source changes, full-guest runs, census, qualification or release.

## Failure oracles fixed before execution

1. **Compatibility failure**: a byte not supplied by any initialized/concurrent
   source value, a trap on the fixed in-bounds addresses, or a stale/hybrid result
   after an explicit completion handoff/common exclusive lock. These observations
   violate this fixture's Wasm permitted set or synchronization premise.
2. **Application coherence observation**, not a compatibility failure: with
   distinct locks, head combines fields from A=(100,900) and B=(101,0).
   In particular (101,900) is ahead of either complete published head in the
   iterator's lexicographic order. Such a bound could permit premature undo
   truncation *if used by the real algorithm*. We do not execute reclamation or
   establish that the real guest produces either this interleaving or SQL harm.
3. **View observation**: plain aligned 8-byte read versus plain 8-byte write.
   Initialized/source words are 0x1111111111111111/0x2222222222222222.
   With distinct locks, each byte may come from either value. No assumption of
   an atomic 8-byte Wasm ordinary access or an invariant relating view to head.
4. Positive/negative oracle controls must accept both complete heads and allowed
   hybrids as byte-valid, distinguish the ahead hybrid, reject injected unrelated
   bytes and reject hybrids under the protected/ordered premise.

## Correspondence and deliberate abstractions

- Wasm fixture uses real shared-memory v128.load/store, i64.load/store and
  seq-cst i32.atomic.rmw.cmpxchg/i32.atomic.store opcodes. It runs via Node/V8
  worker_threads, not a JavaScript reimplementation of the data accesses.
- Go head operations call the unmodified production Simd_p_fx262 and
  Simd_p_v128_load helpers. The view read/write statements use the same uint64
  MemoryEA lowering as the selected guest endpoints. This is not a newly
  translated guest, and no equivalence of the entire guest is asserted.
- Actual global offsets/alignment: head=24020976, view.low_limit=24020776;
  reader's latch=24020736; head writer's end_latch=24020864.
  View reader's per-rseg lock is represented by a separate scratch lock at 256.
- Each lock is abstracted as one 0/1 seq-cst CAS mutex. With one reader and one
  writer this preserves the exclusion/HB distinction relevant here, but does not
  validate the production srw slow path, waiter counters or tpool scheduling.
- `distinct` models no common lock; `shared` is a stronger mutual-exclusion
  control; `ordered` invokes the reader only after writer completion. Neither
  control is a proposed production patch.
- Stress alternates A/B. A real purge head should advance; alternation increases
  sampling opportunities and is not a faithful MariaDB workload. A finite model
  separately enumerates one monotonic A→B transition, and whether a mixed bound
  lies ahead of both published values.
- Go heap and the production NewMemoryMapping backing are run separately.
  Diagnostic -race runs have small counts and halt at the first report. Detector
  output is recorded separately from semantic values, never used as the failure
  oracle and never used as evidence of mmap safety.

## Exit categories

Report independently: Go-only forbidden observation; outcome permitted by Wasm
(including actual reference observation if any); protection control established;
comparison incomplete. A finite reference sample is not the complete Wasm set.
No-observation is not impossibility. Real task ordering, actual SQL impact and
production lock implementation proof remain outside this fixture.

Primary semantic references: [Wasm relaxed model](https://webassembly.github.io/threads/core/exec/relaxed.html)
and [Go memory model](https://go.dev/ref/mem). The Wasm threads draft explicitly
permits tearing of ordinary accesses wider than four bytes; v128 is not atomic.
