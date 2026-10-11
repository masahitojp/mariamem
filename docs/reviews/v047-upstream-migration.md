# v0.4.7 upstream wasm2go migration — qualification in progress

This candidate uses goccy upstream plus nine managed patches, with the exact
v0.4.6 MariaDB Wasm. It does not update the guest, public API, Snapshot format,
minimum Go, mysql driver, VFS, or handshake-version behavior. Publication and
main integration require the final Human decision.

## Input and migration identities

- Pinned main: `386a62c3669e37bb8aaad58cd0aca8da893b3d80`.
- v0.4.6 source: `b56be17206b6beef18f55c8ea39b254638da8590`; annotated tag
  `09d7b82e1900318dde45d08bebd9328ea35e6ef7` (verified separately).
- Track A final evidence: `9a130274bff87d4a814cc1cac6c6cb6c1cc62a5f`, tested
  implementation `c06e908aef1055ca718b6da0212bb578c51a1a48`.
- Upstream: `730057c146463f663e8774587bc96fb2bea91af8`; archive SHA-256
  `1adc74bb1594ed1d300d9382b9da27402728939fc021024d977e9c98afd2467f`.
- Previous fork: `ac98bcf00c17d8531f0c071a9836d0b50975e7ff`.
- Unchanged guest SHA-256:
  `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
- Canonical Go1.26.8, WASIXCC0.4.7/LLVM23.1.0, Binaryen133 pins unchanged.
  No local guest compile or guest patch change. The accepted Wasm was retrieved
  from v0.4.6 Release run 38040418075, artifact 11665901597; ZIP CRC and SHA verified.

[The ordered patch inventory](../../benchmarks/spikes/wasm2go/PATCHES.md) records
all nine responsibilities. Five existing patches remain byte-identical, two are
upstream context ports, and two retain required helper/export capabilities.
The production pipeline downloads upstream only; historical fork pins remain in
historical experiments and attribution, not current generation inputs.

Only generated `code/base/base.go` changes: bulk fill/copy directly load logical
MemSize; the bridge consistently uses logical size and retains contention tests.
All generated MariaDB function bodies, data, mmap owner and Snapshot/Fork source
remain byte-identical. The unused non-shared whole-backing alias contract is not
adopted. Shared memory behavior is verified by fixtures and the concrete guest,
not inferred solely from a small diff.

## Reproduction and source attribution

Use the disposable workspace guard (24 GiB budget, minimum free 20 GiB), pinned
Go1.26.8 and a checksum-verified v0.4.6 guest directory. The initial migration
ran translate_guest.py, the source-only setup_candidate.py adapter and the canonical
generate_runtime.py installer; accepted inventories were reviewed from that output.
Subsequent independent reproduction uses the unchanged canonical entry point:

```sh
python scripts/regenerate_release_guest.py \
  --guest-dir /absolute/accepted-guest \
  --output /absolute/fresh-regeneration
```

Independent extraction, nine patch applications, converter build, memory32
fixtures, translation, adapter and installation reproduced all committed bytes.
The only generated-file delta is recorded with before/after SHA-256 values in
`release/generated-license-evidence.json`. Existing guest/symbol audits remain
historical; upstream MIT text matches the preserved notice. Corresponding source
still includes upstream archive, ordered patches and guest/runtime inputs.
No release guard or evidence trust model has been weakened.

## Qualification status

Local source checks and canonical integration passed on macOS arm64. Detailed
consumer, race and paired product evidence is being collected. Native macOS15 /
Ubuntu24.04 final-artifact qualification remains a separate CI gate; this newer
local macOS host is not evidence for the minimum macOS release.

The existing zero-length bulk-memory bounds edge case and full-generated-guest
shared-memory race limitation remain known boundaries. Focused race PASS is not
full guest race freedom. No general forced termination/reclaim work is included.

## Race observation boundary

The same `-race` default Fork/isolation and repeated-concurrent-lifecycle tests
were run against exact v0.4.6 and the candidate. Both completed with zero
reported signatures. This does **not** mean the historical 149 guest signatures
were fixed: that old census used a different guest and Go-heap backing.
Go1.26.8 `runtime/race.go:isvalidaddr` accepts heap/data ranges, not arbitrary
syscall mmap memory. A separate positive-control probe performs the same
unsynchronized byte update on Go heap versus anonymous mmap: the heap run
fails with race reports; mmap exits without a report. The difference is
observability, not correctness.

Consequently: no newly reported race in this pair, no resolved historical
signature claimed, and full mmap guest-race coverage remains unproven. The
focused owner/thread tests, controlled-trap fixtures and byte-identical guest
access instructions provide complementary evidence, not a race-freedom proof.
No race suppression, address-specific patch, alternate production backing or
translator race adaptation was introduced.
