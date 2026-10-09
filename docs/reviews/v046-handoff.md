# v0.4.6 handoff — agreed scope, not implementation

Begin only after v0.4.5 stabilization is accepted. This handoff does not create or
release v0.4.6, and does not authorize a guest upgrade or Snapshot optimization.

1. **Go API completeness.** Add a Go persisted-Snapshot loading equivalent for
   prepare → persist → load → Fork → test → Close. Keep verify-on-acquisition,
   exact owned backing, source-path independence, immutable baseline and child
   isolation. Go/Python scenario equivalence matters more than identical syntax.
   Cover malformed/corrupted/incomplete/mismatched import and lifecycle cleanup,
   then run relevant platform qualification for the actual changed boundary.
2. **Documentation usability.** Make product-level README language-neutral and
   show comparable Go/Python acquisition flows. Keep pytest/fixture details in
   Python docs; avoid Python explanations leaking into Go docs. Validate published
   examples against actual supported APIs, minimize archaeology and agent tokens.
   Do not rename Snapshot/Fork or expose backing/manifests as ordinary user concepts.
3. **Product Validation, after Go scenario coverage.** Reuse established workloads
   and lifecycle parts for Fresh, Snapshot/Fork, Testcontainers Fresh and shared
   rollback/reset. Include comparable realistic migration/data/application/parallel
   work, actual versions/environment, setup/SQL/cleanup/CPU/memory and reset burden.
   Independent application commits can escape test rollback; shared server/session
   state is not disposal isolation. Existing four-test Docker pilot is limited
   historical input, not completed comparable validation. No new campaign in v0.4.5.

Inputs: [v0.4.5 final review](v045-verification-economics.md),
[measurement conditions/raw data](../../benchmarks/v045-measurement.md),
accepted product contract and unchanged guest pins. No assumption that a report's
latest SHA was runtime-qualified. Final artifacts retain their distinct release owner.

Acceptance should demonstrate equivalent persisted-baseline use in both languages,
clear executable documentation and comparisons with explicit isolation guarantees.
FD pressure from many baselines, source-evidence schema, hard-failure containment,
race model and broad Fast Feedback remain separately bounded questions.
