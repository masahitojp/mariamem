# D1 prepared entry — defer from0.6.0, consider in0.6.1

Human decision,2026-10-31: after the wire/D1 reconciliation, the Human approved
D1 deferral and said to consider it in0.6.1. [Issue43](https://github.com/masahitojp/mariamem/issues/43)
tracks it in the [v0.6.1 milestone](https://github.com/masahitojp/mariamem/milestone/2).
This is a planning target, not implementation authorization, a delivery promise,
a runtime PASS or release approval. The original diagnostic/isolation guarantees
are not silently weakened; D1 is explicitly deferred rather than called complete.

The adopted standard-runner Django recipe remains available. The missing
additional boundary is an entry that supplies every admitted test with the
user-declared prepared schema/seed, after prior commits or ordinary failures.
The current parent owns a server per runner invocation; Django owns test DB
creation, rollback, flush, fixtures and serialized rollback. Default transactional
flush correctly yields SEED then empty, so its existing PASS cannot close D1.

Concrete remaining questions: preparation's position relative to Django test DB
creation/migration; ordinary versus transactional restoration policy across both
runners; physical connection/transaction retirement before an owner changes;
and owned error/admission/cleanup behavior. Selected serialized rollback and
fixture cases restore their own bounded seed subsets; no arbitrary prepared
schema restoration or dedicated D1 capture/admission oracle is established.
A large custom adapter or guest change is not presumed necessary.

User impact: continue using the ordinary documented Django runner and explicitly
choose framework fixtures or serialized rollback as appropriate. No automatic
D1 prepared-Snapshot lifecycle or universal seed replay is promised in0.6.0.

Next0.6.1 work begins with a bounded minimal-boundary design comparison using the
authored orders app, not an automatic Oscar/external-project campaign. Original
failures, first/second/reverse/commit isolation, failed-setup admission and honest
cleanup would need acceptance if implementation is later selected. Issue43 owns
the actionable checklist and future cost/exit decision.

P1/G1/EP1/EG1 remain required. EP1 is not deferred because its example uses
Django. Shared lifecycle, cleanup, isolation or wire defects must still be
assessed against those required entries; this decision excludes no common defect.
Detailed resource tuning remains0.7.x. No product/API/guest/generated changes
are made by this decision record. Wire-completion interpretation is a separately
labelled proposal in the reconciliation, not granted by this D1 approval.
