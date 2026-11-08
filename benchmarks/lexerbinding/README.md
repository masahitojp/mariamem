# Lexer C-input acquisition complete; host binding inspection

The next implementation step is the bounded host-stage binding, followed by
actual guest acceptance on both hosts. The existing CRC calculation replacement
and worker-completion handoff can retain their reviewed algorithms: the target
function bodies differ only by concrete relocated references. Input acquisition
is complete; the proposed pins have not been installed, and actual guest/native
SQL differential/worker tests still need to run.

[CI42433100335](https://github.com/masahitojp/mariamem/actions/runs/42433100335)
passed guest, reference, macOS translation and Ubuntu translation on original
source_commit `b1a265cc30a8603ced743c8aeb59c752751ff9d6`.
All five downloaded artifact ZIPs matched GitHub's SHA256 digests; exact run/job/
artifact identities are saved in `ci-42433100335/`.

- New guest: `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
- One UNQUALIFIED C build; no independent two-build reproducibility claim.
- Both host inventories are identical:51 raw generated files, including data.
  Their native converter executable hashes differ by host, as expected; no other
  input-manifest field differs. Neither native converter binary is copied here.
- Standalone component replay uses the actual upstream const typedef and passed
  all638 full512-byte maps plus fallback/OOM/corruption and wrong-type rejection.
- Native12.3.3 lexical SQL reference passed. This is still a reference, not a
  comparison against an installed new C guest.

## Exact correspondence

| Target | Finding | Proposed use |
|---|---|---|
| Free/reclaimer `Fn153` | Same function name, non-address bytes exact;12 unique global references move+14464 | Keep the existing deferred-free handoff; require the new complete-body hash |
| Worker entry `Fn131` | Complete body unchanged | Keep its exact old hash and guest ABI |
| Allocation/entry `Fn214` | Same function name, non-address bytes exact;9 unique globals move+14464 | Keep +16/+40/+44 field offsets; require new complete-body hash |
| CRC validator `Fn18145` | Same branches/operators/calls;11 unique references relocate; diagnostic text pointer moves+64, others+14464 | Keep the exact computation-only replacement and every other validation block |
| CRC table | Exactly the same4096 bytes, unique in new data | Pin the new data offset7180928 (old7166464) and the unchanged table hash |
| Memory initializer `Fn67` | Concrete addresses and first segment length move+14464; stack base, TLS505 bytes and zeroed BSS8982576 bytes unchanged | Pin new exact initializer/layout; retain worker ownership contract |

The recovery-message pointer stored in data1 also relocates; following that
pointer resolves the exact same NUL-terminated diagnostic text. BSS globals are
at the same relative offsets in the unchanged-length zeroed region. The
inspection does not merely normalize all large numbers: every changed token in
the four target functions is recorded, and every non-address byte matches.
Runtime acceptance must use complete new hashes, never a +14464 range rule.

Generic runtime base/FS helper preimages pass the original strict source edits
after normal source adaptation/gofmt. Generic base bytes excluding guest-specialized
SIMD functions match the old runtime; relative/prepared FS helpers match exactly.
284 of1024 specialized SIMD functions have generated changes. Their semantic
equivalence is **not** claimed: raw new inventory hashes cover them, and actual
guest table/SQL/worker oracles are still required. This is not an equivalence
proof of the entire new guest.

## Offline checks and next gate

`python3 -m unittest discover -s benchmarks/lexerbinding -p test_bindings.py -v`
passes7 tests. Configured **copies** of the unchanged binding modules exercise
the proposed exact pins, CRC non-computation-block preservation, one-more-address
mutation, missing/duplicate function, changed comparison/LSN, bad guest/table,
missing required file and worker handoff. The canonical modules are untouched;
a separate test confirms that they still reject the new guest.

Before actual host execution:

1. Bind the host-stage adapter to the new guest, complete raw inventory and exact
   target-body/table hashes. Keep C originb1a265cc distinct from adapter origin.
   The current source-origin verifier deliberately rejects unrelated changes;
   do not widen it to all benchmarks/scripts just to reuse an artifact.
2. Run actual638-map verification/corruption, profiling/ambient separation,
   native SQL differential, two independent Snapshot children, worker ownership
   and cleanup on macOS15 arm64 / Ubuntu24.04 x86_64.
3. Measure the actual C candidate afterward; the earlier Go-surrogate timing is
   not a speed claim for this Wasm. Independent C reproducibility, adoption,
   main integration, Qualification and release remain separate gates.

Cost of the next gate: two native Go installation/build/acceptance cells, zero
additional C builds while the pinned artifact is available. If artifact retention
expires, rebuild the original pinned C source and verify its identity rather than
claiming the old receipt for new bytes.

## Reproduction and retention

`fetch.py` downloads the five exact artifact IDs and verifies ZIP/file digests;
`analyze.py` validates both source-bound inventories, computes the exact
correspondence and records generic-helper boundaries. Run from this report's
pinned checkout with workspace-owned sibling `temp/` and `evidence/`; inspection
requires Go's gofmt, not host/guest execution. The script uses the original
canonical pins and fails if a later checkout changes that baseline.

The compact receipt contains decoded source/job/native controls, a bounded
lossless text envelope of the C guest record, and five small function preimages.
The original guest-record file hash is separate from the envelope's canonical
JSON payload hash. Large Wasm/binaries/raw generated trees and archives are
recreatable inputs and are removed after this inspection; ZIP digests and all
file inventories are retained. No benchmark process or new C build ran here.
