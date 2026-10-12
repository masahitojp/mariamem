# v0.5.0 shared-memory technical judgment for Human Review

**Original question:** R1–R5 support the reviewed Wasm access/order/ownership
mappings for this fixed guest and runtime. Two reproduced wait/thread-spawn
boundary violations still prevent an unconditional positive judgment. J1 remains
an unresolved completion/reclamation argument on normal shutdown; **no
Wasm-forbidden translated outcome or user harm is established for J1**.

**Condition for final verification — recommended:** fix T1/T2 and verify canonical
independent regeneration; complete one bounded comparison of the actual optimized
Wasm and translated J1 exit/join/free path before Qualification. Repair J1 only
if that comparison establishes a translation violation or unsafe guest lifetime.
I recommend additional confirmation first. This tightens the earlier “T1/T2
fixes, J1 left to Human acceptance,” which lacked an assessable normal-use and
last-access case. It is a correction to the recommendation, **not a newly
reproduced J1 failure**. “Close three points” means two fixes and a supported
J1 decision, not three mandatory fixes.

**Strongest objection:** no J1 translation counterexample exists, the optimized
Wasm itself lacks the disputed fences, and host join protects backing retirement.
A speculative patch could change guest identity without fixing a mismatch.
That rules out declaring J1 broken or demanding redesign; it does not establish
safe guest allocation reuse before host join. Recommend a **2–3 engineer-hour
J1 task, capped at three hours**, with an exact result or explicitly unfinished
premise. The cap never becomes PASS.

[Detailed consequences, ordinary reachability, evidence, missing premises,
work/acceptance criteria and repair costs](v050-join-decision.md);
[R1–R5 results](v050-semantic-audit.md#per-item-disposition) and
[fixed identities](v050-semantic-audit.md#scope-completion-and-identities).
This update adds no runtime experiment or implementation.
