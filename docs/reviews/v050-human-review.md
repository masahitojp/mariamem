# v0.5.0 Human Review — after final Qualification

**Decision now: proceed to Product Validation on the qualified candidate.
I recommend proceeding.** Exact source
`bb637c49e6d6b50ec6761dead172a35f0b051f7e` passed final Qualification on
macOS15 arm64 and Ubuntu24.04 x86_64. Both native runtime/consumer suites and
the aggregate artifact/source guard passed. The agreed current-guest R1–R5
investigation has no outstanding identified access/ownership correction after
T1/T2/J1; final Qualification found no new blocker.

**Strongest objection:** tests can pass while startup, parallel test throughput
or resource use becomes worse. The guest upgrade and the J1 reclamation owner
have not yet been measured in the final configuration. This is a reason to run
the planned Product Validation before release approval. It does not call for
repeating the completed access-path investigation on the same inputs.

Use the existing [v0.4.7 paired product scenarios](../../benchmarks/v047-product-validation.md)
to compare released v0.4.7 with this candidate on the same machine/toolchain:
Go/Python Fresh and Fork, light setup, 10 MiB serial/four-parallel, and the
100 MiB supplementary scenario. Retain SQL/commit/rollback/isolation oracles,
timing distributions, CPU and separately interpreted memory/FD/cleanup evidence.
Measure the complete upgrade's user cost; do not attribute every difference to
J1. A concrete failure or material regression needs a bounded diagnosis and
Human decision; it must not be hidden by averaging or changing the oracle.

[Qualification evidence and exact candidate identity](v050-final-qualification.md);
[J1 implementation and limits](v050-join-lifetime-fix.md);
[R1–R5 technical judgment](v050-semantic-audit.md).
CI's `READY` is its artifact/qualification verdict. Product Validation and the
Human release decision remain pending. The prior candidate-adoption review is
[preserved at its original commit](https://github.com/masahitojp/mariamem/blob/c427ed7619e07fae080037d7e254bb0cf5a0fb25/docs/reviews/v050-human-review.md).
