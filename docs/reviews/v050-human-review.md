# v0.5.0 Human Review — after Product Verification

**Decision now: accept the qualified/measured candidate as the v0.5.0 basis and
proceed to integration/release preparation. I recommend acceptance.** The agreed
current-guest investigation has no outstanding identified correction after
T1/T2/J1. Both-native final Qualification passed. The approved Product
Verification completed all 80 cells and eight pilots with passing unchanged SQL,
transaction/isolation oracles and balanced Go memory reclamation.

**Strongest objection:** Go four-parallel Fresh median increased from 0.953 to
1.763 s (+0.809 s); Python Light Fresh increased 0.374 to 0.481 s. These are
user-visible costs in the measured samples. Phase records place the major Go
variation in the existing approximately-one-second startup tail; Python parallel
Fresh has the opposite median change. Three trials cannot establish tail-rate
equivalence. I assess this as non-blocking under the existing startup-tail
contract: no new functional/resource failure appears, allocation/cleanup remains
bounded, and the adverse samples are retained. No zero-overhead promise follows.

[Product results, adverse CPU cells, phase evidence and limits](../../benchmarks/v050-product-verification.md);
[both-native Qualification and exact source](v050-final-qualification.md);
[J1 implementation](v050-join-lifetime-fix.md);
[R1–R5 technical judgment](v050-semantic-audit.md).
The measured/qualified runtime source is
`bb637c49e6d6b50ec6761dead172a35f0b051f7e`; observer source is
`f24bc942628eeabe391cfcbc6300bcb175157b17`. Later report commits do not inherit
exact-SHA READY by relabeling receipts. The prior pre-Product-Validation review
is [preserved](https://github.com/masahitojp/mariamem/blob/5d8ecddd70603dfee7c14cca1a453a717898edc5/docs/reviews/v050-human-review.md).
Main integration and release approval remain Human decisions; this task creates
no tag or publication.
