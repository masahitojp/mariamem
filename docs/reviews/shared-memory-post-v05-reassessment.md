# Shared-memory follow-up after v0.5 — existing-evidence reconciliation

2026-10-17. Documentation review against published v0.5.2 source
`47f297cc7498625e076abb93322eb616c9560bb8`. No new execution, census or fix.

## Conclusion and next Human Review

The old census is complete for its pinned inputs. Post-update investigation also
exists: R1–R5 reviewed the fixed 12.3.3 guest's narrow targets and supporting
access, synchronization and lifetime paths. The subsequent exact-width and
T1/T2/J1 repairs were adopted. Calling all post-update reassessment unstarted
would discard that work.

That investigation did not reclassify all 149 old conflict signatures against
the released guest. General shared-memory translation correctness remains
unestablished. Neither "half complete" nor "only a Human acceptance remains"
accurately describes both scopes together.

The recommendation is to start the next Human Review from this distinction:
retain the completed current-guest work and the accepted product contract;
decide the scope of any broader shared-memory design separately. Do not launch
a new full census, change runtime behavior, or reopen release acceptance merely
because a historical report still says a decision was pending.

The strongest objection to treating this as technical closure of the general
question is concrete: the old other-scalar and SIMD groups do not have a
signature-by-signature disposition for current inputs. The table below records
that gap rather than treating functional PASS or detector silence as its answer.

## What the existing records cover

The [old census](../../benchmarks/direct-link-race-scope.md) binds a different
guest hash and converter identity. Its 5,373 reports, 149 signatures and seven
groups are historical observations, not current defect counts. Function numbers
and addresses must not be transferred between those guests.

| Old group / signatures | Relevant later evidence | Limit of this comparison |
| --- | --- | --- |
| Wait precheck / join polling: 23 | R1/R3 wait comparison and registration; R4/J1 completion and reclamation repair | Protocol-level follow-up, not a new mapping of all 23 signatures |
| CAS retry / waiter counters: 21 | R1 classifies waiter/release CAS consumers; R3 covers rwlock protocols | Does not establish every old CAS-retry site's current alias and lifetime |
| Lock polling / wake hints: 46 | R1 classifies mutex type, ownership, hints, successful-CAS wake decisions; R2 records compiler/native ordering | These bounded arguments do not automatically cover allocator polls or every old inline caller |
| Thread lifecycle / registry: 22 | R4/R5 launch, host drain and lifetime work; T2/J1 owner repairs | No signature-by-signature revalidation of the old registry set |
| Other scalar state: 34 | R5 records the narrow target protocols and their supporting ordinary readers | Target-related coverage is not a disposition of every old scalar/global access |
| Wide-memory overlap: 2 | R5 supplies object-specific bulk/SIMD exclusions for its targets | Does not establish ownership and synchronization for the old two overlapping-vector examples |
| Subword atomic-load widening: 1 | Exact-width load correction removes writing identity CAS; later exact-width writers address the related store/RMW footprint | Lowering defect class repaired; not evidence that all ordinary/atomic overlap disappeared |

Sources: [R1–R5 and its coverage boundary](v050-semantic-audit.md),
[access-review finite contract](v050-access-review.md),
[load correction and observation limits](v050-correctness-fixes.md),
[exact-width writer integration](v050-exact-writers-integration.md),
[T1/T2 and bounded J1 comparison](v050-boundary-join-fixes.md),
[J1 repair](v050-join-lifetime-fix.md), and
[v0.5.0 Human Review](v050-human-review.md).
The table reconciles report scopes; it is not a fresh code/PC remapping or new
verification of the original source arguments.

## Separate decisions and completion criteria

- Accepting the limited product and its bounded current-guest evidence does not
  establish a general Wasm-to-Go shared-memory model. Existing adoption/release
  approvals must not be relabelled as that broader guarantee, or reset to pending.
- Detector visibility is distinct from semantics. Heap, mmap and assembly have
  different visibility; no reports on mmap/assembly do not establish safety.
- The old scope verdict remains evidence that one precheck rewrite did not cover
  its observed set. Its specific counts are not evidence that the current guest
  has exactly the same conflicts or requires exactly the same implementation.
- This documentation reconciliation is complete. Current-input remapping of the
  old remaining groups, a new full census and a general design are not performed.
  If broader work is selected, define its fixed inputs, per-group dispositions
  and finite exit conditions before executing it; do not use universal absence
  of failures as the completion condition.

The separate 100 MiB Go Fresh investigation was explicitly closed until
recurrence in [the Human decision](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-heap-reuse-attribution.md).
An unresolved explanation there is not unfinished authorized profiling work.
