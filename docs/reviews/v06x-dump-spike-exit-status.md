# Dump comparison exit — stronger SQLSTATE gate

The Human requires the reader SQLSTATE gate and a recorded experimental host
delta before closing the spike as comparison complete. Route choice,
productization and host correction adoption are post-spike decisions. The prior
[comparison report](v06x-dump-comparison-completion.md) and CI40192797648 remain
historical evidence for9494e75, not evidence of the new deterministic assertion.

New candidate source_commit `c417e21ba7dabefa5d95600ea322091732430c97`, parent
`9494e755a5e7d79a9702e1d1dc7c1caae993e801`, on experiment/dump-import:

- Reader sql_failure now requires SQLSTATE42S02 as well as errno1146, exact
  cause/phase/span, partial DDL, cleanup and no Snapshot/test admission.
- Positive controls accept42S02. Negative mutations reject HY000,42000 and
  absent state for both reader and native classifiers.
- Runtime, guest/generated, producer/options, canonical bytes and SQL oracles
  are unchanged. The bounded workflow reruns the full existing matrix.

The [experimental host record](v06x-dump-sqlstate-evidence/approved-host-delta.json)
pins before/after hashes for the decoder and its two regression files. It records
unsigned32 input0..4294967295, low16 protocol projection, invalid-input rejection,
missing-status startup behavior, nested results and preservation of all low16
flags. Those exact file hashes remain unchanged. **Every spike PASS is
conditional on that correction**; the record is not host adoption approval.

[Focused checks](v06x-dump-sqlstate-evidence/local-checks.json) passed on the
exact new candidate:38 binding/framing/classifier tests,25 acquisition unittests,
public-source and whitespace checks. Saved local binding is INPUTS_VERIFIED,
not fresh producer/comparison evidence. The checksum manifest covers these
local records independently of earlier CI receipts.

The exit gate remains open until bounded CI on this exact source passes and
its new artifact receipt is saved and verified. Then record comparison complete;
do not relabel an old receipt or require another approval merely to apply this
already authorized exit criterion. A subsequent spike review chooses library /
external client / defer / productization and assesses host correction adoption
separately. No main integration, Qualification or release follows here.
