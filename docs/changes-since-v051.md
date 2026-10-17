# Unreleased changes since v0.5.1

This describes the ownership optimization adopted on main after Human Review,
not a new published version. The release version remains a Human choice.
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

The eventual versioned release notes must state the detection change above along
with the preserved isolation and transfer guarantees. This file is an unreleased
change record, not `release/NOTES-<version>.md` and not release approval. Commit
this record before versioned release preparation, whose allowed diff is narrower.
See [the integration review](reviews/snapshot-owned-root-productization.md#qualificationとリリースの引き継ぎ).
