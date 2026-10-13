# v0.5.0 Human Review — completed J1 candidate

**Decision now: adopt the J1 repair candidate and proceed to the already planned
final Qualification and Product Validation. I recommend adoption.** An exiting
worker can no longer overwrite a replacement allocation in the preserved failure
oracle: reclamation waits for the last guest/host memory access, including unwind
and detached self-exit. The previously identified T1/T2 fixes remain intact.

**Strongest objection:** the repair adds allocator lookup/synchronization and
changes deallocation timing; its performance/resource cost has not been measured.
The original failure was shared by Wasm and Go, not a demonstrated Go-only defect.
I still recommend the limited owner repair because it removes the concrete
lifetime failure without changing guest inputs or broadening the engine design.
Product Validation must assess its cost before a release decision.

For the original question, the agreed current-guest R1–R5 investigation now has
no outstanding identified access/ownership correction after T1/T2/J1. Scoped
repair verification is complete; final platform/artifact/consumer Qualification
and Product Validation are not. No whole-guest re-investigation is recommended
on these fixed inputs. This candidate adoption is separate from release approval.

[Implementation, lifetime argument, semantic differences and limits](v050-join-lifetime-fix.md);
[exact identities and verification](v050-join-lifetime-evidence/verification.json);
[historical J1 before/after decision](v050-boundary-join-fixes.md);
[R1–R5 evidence](v050-semantic-audit.md).
No main merge, tag, publication or RELEASE READY judgment is included.
