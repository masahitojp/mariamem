# Routine canonical adoption candidate — in progress

Baseline: de0e08a9c4248969a7522abebfdee8aea6ef9657. Selected adoption source:
experiment/routine-bootstrap@9250ff5; do not merge its experimental history.
The approved scope is procedures/functions and bounded DEFINER, with packages
and events excluded by the [scope decision](../decisions/routine-support-scope.md).

This branch prepares the canonical source/generation/provenance candidate.
Binary prepared code and its unapproved prototype limits are excluded; the
prepared production requirement remains a separate task. The text result-chain
and option paths are required to support ordinary CALL/multiple results and
default consumer connections. The experiment's128-result cap is not adopted;
existing32MiB guest transport and ordinary failure invalidation remain in force.

Initial source changes are authored owners only: routine bootstrap, source-bound
DDL extraction, explicit boot context, text-chain serialization and wire framing.
No generated Go is hand-edited. Source/hash and exact J1 binding must be reviewed
on fresh compiler output before canonical generated artifacts can be promoted.
Build, regeneration, boundary/runtime tests and identity receipts will be recorded
here as they run. This initial source commit is not a completed adoption or
merge-ready claim. Main integration, final Qualification and release are excluded.
