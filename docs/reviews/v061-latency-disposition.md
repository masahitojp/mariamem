# v0.6.1 latency follow-up: decision still required

The decision needed is whether to investigate the observed small-workload
increase before deciding to repair or explicitly accept it for the next release.
Recommend a bounded attribution of the roughly2ms/DB Go Fresh startup difference:
it is consistent in six pairs and gives a finite target. The strongest objection
is its small absolute size and one-host scope; recording explicit acceptance is
reasonable if its cost outweighs user impact. Neither outcome has been approved.

This records a proposed0.6.1 work item, not an accepted regression, a release
blocker, an implementation authorization or a promised0.6.1 fix. The approved
v0.5.1 performance disposition is historical precedent for recording a decision,
not authorization to accept this different campaign.

## Evidence and limits

The [report](../../benchmarks/v060-latency.md) compares source commits
`4f7b18bfc00965974fcbb16ac49cbf00d9fb2b0e` (v0.5.3) and
`b3b3b46a8807482ad3f96725af86e031fe369b01` (v0.6.0), same Go1.26.10,
CGO disabled, one M1/16GiB/macOS27.2 host, six alternating ordinary pairs per cell.

- Go small Fresh:213.5→226.7ms, +6.2%, six/six slower pairs; Start sums imply
  about2ms/DB increase. This is not feature/root-cause attribution.
- Python small:+5.0%, four/six slower pairs; medium:+1.7%, six/six slower pairs.
  Both versions retain the approximately1s first small preparation observation.
- 10MiB serial/parallel Go whole-suite medians are within about0.2%; independent
  phase medians differ. The separate sparse resource cohort proves no resource
  acceptance and neither establishes nor excludes a memory regression.

MariaDB is12.3.3 in both releases; the guest build identities differ by release.
These same-toolchain source builds are not published-wheel timing observations.
No Ubuntu campaign or universal rate is claimed.

## Proposed finite next task, if selected by the Human

Reuse the same fixed Light Fresh workload and typed release pins. Bound the
question to Start/setup attribution; preserve ordinary timing and sample order.
Use at most2hours active work including30minutes tooling, one host, no heavy CI.
Exit with a supported cause and a separate repair proposal, or an inconclusive
report naming the next evidence/cost. Do not extend into resource-model work,
100MiB, a new API or broad optimization. Python investigation is a separate
choice if its user impact warrants it; no Go explanation is silently applied.

The maintainer owns the next prioritization/acceptance decision at0.6.1 scope
planning. Until that decision, status is **DISPOSITION_PENDING**, with no implicit
acceptance from report adoption or the already completed0.6.0 publication.
Existing runtime/docs CI cannot determine acceptable performance cost. The
analysis `--check` and its focused tests detect inconsistent saved evidence only.
