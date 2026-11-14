# Canonical output gate43450619130 — PASS

Exact candidate d8f66d9a5605b3b738b2175268a3734ee1c89a4a passed all four jobs:
independent guest generation, native reference, macOS15 arm64 and Ubuntu24.04
x86_64. Both product OSes independently regenerated all120 inventory files to
the canonical tree. Two C builds produced identical linked/optimized hashes.

Each platform also passed raw/C/binding controls, build-guard negative controls,
CRC differential, actual dictionary/UCA/lexer/worker regressions, worker ownership
controls and normal/binary SQL/child/Snapshot public regressions. Per-step logs
and JSON receipts are retained under each platform. SHA256SUMS within each
artifact refers to original bytes; normalization.json records original and
normalized hashes and the sole CI runner-home prefix replacement recipe.
Historical failures43442267676 remain unchanged in their own folder.

This closes the fresh-source/translation/installation/reproduction/platform
checkpoint. It does not close the full#132 scope: ordinary whole-product checks,
broader prepared limits/consumer/installed distribution and same-condition
performance remain. No release or main adoption is implied.

Normal Development checks43457263372 was submitted next on the same runtime
candidate. User requested five-minute monitoring and repair until successful,
then continuation of remaining acceptance. No extra C build is needed merely
to run normal checks against the canonical checked-in guest.

## Storage update (#158, 2026-11-14)

The preceding text records the original gate context. Per-platform raw copies
and normalization inventories were removed from the current tree after adoption;
[their original source](https://github.com/masahitojp/mariamem/tree/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/prepared-output-product/ci43450619130)
remains historical. The accepted decision and remaining limits now belong to
[the ADR](../../../decisions/prepared-output-reuse.md). No CI outcome is relabeled.
