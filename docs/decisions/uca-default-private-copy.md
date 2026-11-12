# UCA default private-copy: Human acceptance

On 2026-11-12 the Human decided: 「変更を受け入れした上で、原因を追いましょう」.
Accept the bounded UCA default contraction/flags/hash private-copy optimization,
including the measured tradeoff; pursue residual PREPARE waits separately under
[Issue140](https://github.com/masahitojp/mariamem/issues/140).

The accepted experimental evidence is source_commit
`e556c36570e1be023f8a9c8243381c6605079592`, using experimental guest origin
`f43257225e1fd65c58ea8f5d7b220c3a509c203b`. It is not a canonical product build.
Only five default collation IDs, no parsed tailoring, and the checked layout
use the prepared data. Arrays remain privately allocated per DB; descriptor,
ready/lock, fallback, page processing, booster and disposal contracts remain.
This accepts avoiding repeated construction, not shared mutable guest memory.

The Human accepts the measured startup saving and the unresolved P8 cost:
[initial comparison](../../benchmarks/uca-copy-performance/README.md) has lifecycle
Fork improving in 6/6 pairs (median paired -6.76%), P4 suite improving in 4/5,
and P8 worsening in 4/5. The separate
[ten-pair P8 attribution](../../benchmarks/uca-p8-attribution/results/README.md)
has candidate slower in 8/10 pairs, median paired +15.70%, with sample spans
>100ms in 7/10 candidate versus 4/10 baseline batches. These unfavorable results
remain accepted evidence, not noise deleted from the decision. CPU and typical
Fork improve; process RSS does not. No uniform whole-suite speedup is claimed.

Bounded correctness passed Ubuntu CI43137408120 and Mac CI43148033625 with the
original source/artifact bindings in [the execution record](../reviews/issue154-uca-data/execution-stage.md).
Mac reused the Ubuntu native reference. Real-guest OOM, lazy initialization order
and complete BSS-name proofs remain the documented source/stub limitations.

The prior recommendation to hold adoption is historical, superseded by this
Human decision, not rewritten in the measurement report. The reason for more
observer-off tails in the candidate is still unknown; the captures identify an
existing read-completion wait, not proof that the optimization is causally unrelated.

Next implementation is the smallest canonical candidate from current main,
with preparation/binding tests and generated provenance. Do not merge exploratory
history or relabel experimental CI as canonical acceptance. Protected integration
and canonical validation remain to be completed; release is separate. Solving
Issue140 is not a new prerequisite for assembling that accepted candidate.
