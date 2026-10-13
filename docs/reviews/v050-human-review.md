# v0.5.0 shared-memory technical judgment for Human Review

**Original question:** T1/T2 now repair the two demonstrated Wasm/helper-ABI
boundary violations. R1–R5 support the reviewed mappings for this fixed guest;
this is not general shared-memory conformance. The bounded J1 comparison finds
premature allocation reuse in both original Wasm and translated Go, with a later
write changing a replacement byte. It does not demonstrate a Go-only outcome
forbidden by the original Wasm, or a normal SQL failure.

**Condition for final verification — recommended:** complete a limited
worker-completion/reclamation repair and its existing failure oracle before
Qualification. T1/T2 repair and independent regeneration are complete. J1's
technical comparison is complete; its production repair is not implemented.
This replaces the earlier unresolved J1 handoff: the previously stated
“repair if shared unsafe lifetime is found” condition is now met by evidence.
I recommend that repair, not acceptance based on functional PASS or detector
silence. A reviewed completion protocol is a separate 4–8 engineer-hour task,
not another whole-guest investigation or an approval to publish.

**Strongest objection:** the original Wasm shows the same failure, and the
forced schedule is not a natural SQL reproduction. That prevents calling this
a new converter mismatch or assigning a failure probability. It does not supply
safe reclamation: the exiting worker can write after guest join/free while host
backing drain occurs later. This judgment concerns the candidate's lifetime
contract, not whether users should stop using mariamem for development.

[Changes, exact reproduction, verification, unperformed scope and finite remedy](v050-boundary-join-fixes.md);
[R1–R5](v050-semantic-audit.md#per-item-disposition);
[historical J1 work/decision plan](v050-join-decision.md).
No final Qualification, Product Validation or release readiness is claimed.
