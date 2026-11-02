# WASM buffer-pool allocation alignment

On 2026-11-03 the Human approved incorporating Issue63 because its cause is
clear and a local change removes known unnecessary work. Adopt it as a scoped
allocation correction with a small observed retained-RSS saving. Do not promise
a speedup or reinterpret the earlier four-field performance verdict as PASS.

The reviewed experimental result is
[source964a4cab](https://github.com/masahitojp/mariamem/blob/964a4cabcb6f2b2b0fa6828319ae3c362dfc8908/benchmarks/buffer-alignment-source.md).
The observed duplicate large zero-fill disappears and held RSS decreases in
all five pairs. CPU/batch effects conflict; queue latency is unmeasured. The
strongest objection is the small saving and inconclusive performance. The Human
accepts the narrow waste-removal rationale despite that limitation; this does
not establish that the observed adverse batches are harmless or caused by noise.

Only the WASM buffer-pool reserve passes its existing extent alignment to an
internal allocator helper. The existing entry stays4KiB aligned. Zero-filled
memory, NULL on allocation failure, unchanged requested size, original-pointer
free and the existing pool retry/commit/release paths remain required. Other
callers and non-WASM behavior remain unchanged. No public API is added.

The canonical candidate starts directly from main
`f09d5167172f091ccc0b20f78b817fe870d3cadf`; exploratory history is not merged.
Promote only the three-source-file portability patch, its exact input hashes,
necessary canonical guest/binding/generated/provenance updates and regression
checks. The experiment-specific installer and benchmark observer are excluded.

This decision authorizes preparing and verifying that minimal product candidate
for normal protected-PR integration. Source preparation, canonical generation,
supported-host correctness and failure-path checks must report their actual
results. Existing identities/body checks are retained. Historical receipts stay
bound to their original sources. Incomplete checks remain incomplete.

No new performance campaign or queue investigation is required by this narrow
adoption rationale. The missing queue field remains a named limitation of the
performance comparison. Qualification, a release version and publication remain
separate decisions.
