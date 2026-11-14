# UCA default private-copy: adopted on main, unreleased

On2026-11-12 the Human accepted the bounded UCA default contraction/flags/hash
private-copy optimization: 「変更を受け入れした上で、原因を追いましょう」.
The subsequent request puts main integration before further wait investigation.
[Original decision and evidence](https://github.com/masahitojp/mariamem/blob/0196163714841e3b6a22ead413fe9893bc92681f/docs/decisions/uca-default-private-copy.md)
retain their experimental source identities; they are not canonical acceptance.

Five default collation IDs, no parsed tailoring and the checked layout use
prepared data copied into private per-DB allocations. Descriptor, ready/lock,
fallback, page processing, booster and disposal ownership remain unchanged.
Allocation failures propagate and partial descriptors are invalidated before retry.
This removes repeated construction, not per-DB ownership or mutable memory.

The accepted measured tradeoff is lifecycle Fork median paired -6.76% (6/6
improve), with the separate P8 comparison slower in8/10 pairs, paired median
+15.70%. CPU and typical Fork improve; RSS does not. No universal whole-suite
speedup is claimed. Bounded experimental correctness passed Ubuntu43137408120
and Mac43148033625. Source/stub OOM and lazy-order limitations remain as recorded.

[The canonical candidate](../reviews/uca-copy-canonical.md) starts at main500020e7.
Do not merge the exploratory history. Formal regeneration/provenance, supported
platform acceptance and protected integration remain required. No release is
approved. #140/#156 own residual PREPARE waits; solving them is not an additional
UCA adoption condition. The latest diagnostic's NOT_REPRODUCED is not a fix or a
withdrawal of the unfavorable observer-off P8 result.

## Protected main integration — 2026-11-12

[PR157](https://github.com/masahitojp/mariamem/pull/157) merged the minimum canonical
candidate as `8df45792a927e440972266ee799d6f7223713e14`. The required conditions above
are now satisfied: two-build/both-platform canonical CI43190662084, explicit
runtime-identical reuse for the image-test correction, and all three protected
Development checks at a8dd2f1c in CI43201340611.
[Completion and evidence](../reviews/uca-copy-main-adoption.md). The accepted P8
tradeoff and source/stub failure limits remain unchanged. No release is approved.
