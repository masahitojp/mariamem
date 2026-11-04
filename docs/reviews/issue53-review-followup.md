# Issue53 — Human review G1/G2 follow-up

Current status: G1 implemented with focused regressions passing; canonical
clean-source daily/smoke and actual-host checks are next. A fresh exact-source
full matrix is still required before adoption of this runtime delta. Batch that
submission after the Human's remaining review findings; no new heavy run is
submitted for this checkpoint. Existing c53771cd receipts remain unchanged.

## G1 — cap and occupied-slot diagnostics

The design's diagnostics paragraph required this even though the old eighteen-row
exit did not name a diagnostic assertion. The previous review missed that prose
requirement. The correction puts its checks inside the existing Admission row;
it adds no resource campaign, periodic logger or nineteenth acceptance theme.

The internal pool samples the immutable resolved cap and lease-map size under
one mutex. Reserved, starting, live and unconfirmed-cleanup leases are counted.
Observing diagnostics does not reserve/release a slot or reopen admission.

Go Snapshot/Fork errors, shared-control wait errors and both Go/shared-host Live
capacity errors include, for example:

```text
max_forks=1, occupied_slots=1; close owned children or increase max_forks
```

This is readable error detail rather than a new public options/status API.
Go context error identity remains reachable through errors.Is; public code,
stage and consumed/closed classification are preserved. The capacity remedy is
not recommended for cleanup debt, because increasing a cap cannot reopen that
admission latch.

Private nonblocking fork_reserve full replies also include integer max_forks and
occupied_slots fields. The Python capacity-wait error displays its immutable cap
and last responsive full-reply observation, with the same remedy and existing
pool_timeout/fork_wait/closed=False. If a positive deadline expires before any
capacity reply, occupied_slots is explicitly unknown, never invented as zero.
A missing field from an older development host also remains unknown. All counts
are observations; a concurrent cleanup can change occupancy before an error is
read. They are not a second admission mechanism or a diagnosis of leaked children.

Detection now includes:

- Pool usage across reserved/active/unconfirmed-cleanup/settled owners; diagnostic
  reads cannot reopen admission. ErrFull, deadline and cancellation identity and
  the distinction between capacity tuning and cleanup debt are checked.
- Public Go TestSnapshotCapacityProgressAndWaitDeadline requires both counts and
  the remedy in the HostError, alongside the existing code/stage/errors.Is checks.
- Control TestCapacityReplyAndWaitErrorReportCapAndOccupiedSlots checks integer
  full-reply fields and the direct control wait failure.
- Python test_cap_timeout_retains_child_and_next_close_releases_slot checks the
  public message and existing child survival. Deterministic clock cases require
  last-observed counts or explicit unknown before any reply.
- Existing actual remote-cap and Go consumer / installed Python consumer owners
  now assert the capacity diagnostics as well as their previous behavior. These
  new actual/installed assertions still need execution on the new source; old
  successful artifacts are not relabelled to include them.

Focused local results on macOS arm64 / Go1.26.10 / Python3.14:
Go -race pool/control/public Snapshot targeted owners PASS;61 Python unit,
framed-transport, handoff and Live tests PASS. No guest, generated source, WASI implementation,
SQL wire behavior, version or release-ledger change is part of this follow-up.

## G2 — historical index and current results

The detector map now opens with current source boundaries and links to the later
adoption review / c53771cd assessment, followed by an explicit Historical detector
index —8566c8ad heading. Its no-matrix-PASS / future-execution statements are past
tense and confined to that old checkpoint. Recorded local1870-test evidence and
old source pins are preserved.

The original adoption review is explicitly labelled as the c53771cd review and
links here for the later correction. Project status and usage/release notes state
that c53771cd passed its own matrix, while this G1 runtime delta still requires
new-source verification. The old docs-only tree-equality reuse applied to7c0f6c32;
it cannot cover this later code change. Prose freshness required review; ordinary
CI did not detect the contradictory tense. Documentation/public-boundary and
reference checks apply to this correction.

## Completion boundary

The Human is still reviewing. This follow-up closes G1 implementation/detector
work and G2 wording; it does not claim the new full installed/platform matrix,
Human adoption, main integration, a new version or publication. Collect further
findings, finish the stable candidate's local checks, then run its exact matrix
once. Any failure remains an unfinished condition, not an accepted exception.
