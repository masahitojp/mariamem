# Changes since v0.5.1 — released as v0.5.2

This describes the ownership optimization adopted on main after Human Review and
published as [v0.5.2](https://github.com/masahitojp/mariamem/releases/tag/v0.5.2)
from source `47f297cc7498625e076abb93322eb616c9560bb8`.
The published v0.5.1 baseline is pinned in
[the release ledger](../release/baselines/v0.5.1.json).

## Snapshot ownership and detection

Ordinary heap-backed Snapshot creation seals the source's same private backing
instead of reconstructing and repeatedly reading all file contents. Normal APIs
cannot modify the fixed baseline. Fork children retain independent state and
lifetimes; a child cannot change its parent or siblings. Successful Snapshot
still consumes the source. Public Go/Python signatures do not change.

This changes a detection guarantee: ordinary heap acquisition no longer performs
a full content scan to detect faults that directly alter private bytes between
freezing and acquisition. It validates identity, state and structure instead.
An error that the earlier content scan could reject during Snapshot creation
may surface later when the child reads the affected data, or may not be detected
by this boundary. A limited InnoDB-page injection produced a later SQL corruption
error on both native platforms; this is not a guarantee for every kind of fault.

Strict digest-bearing internal imports, private cross-host transfer verification
and borrowed-mapping lifetime detachment retain their content checks. There is
no new public loading/persistence API. This accepted detection boundary and the
preserved isolation contract are described in the
[product contract](decisions/snapshot-product-contract.md).

## Release handoff

[release/NOTES-v0.5.2.md](../release/NOTES-v0.5.2.md) states the detection
change above along with the preserved isolation and transfer guarantees. This
file is the change record behind that release, not a substitute for the versioned
notes or release approval.
See [the integration review](reviews/snapshot-owned-root-productization.md#qualificationとリリースの引き継ぎ).
