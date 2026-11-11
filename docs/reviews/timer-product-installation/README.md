# Timer candidate installation proofs

The product checkpoint owns status and remaining gates. These are mechanical
source/input proofs, not runtime PASS or release approval. Regeneration follows
`scripts/build_generated_guest.py`, the pinned `translate_guest.py`,
`setup_candidate.py --source-only` and the strict `scripts/generate_runtime.py`.
Both-platform CI independently repeats generation and compares every file.

The canonical-source bootstrap is run42955063307 at498e186e; its receipt is
retained separately. WASM/converter binaries, raw generation and compiler caches
remain disposable. Only compact identity/proof summaries are retained here.

Local preparation initially encountered a moved generated partition (Fn82),
which was resolved by full-body equality, and an already-completed workspace
cache selection, before installation succeeded with explicitly owned cache
paths. An inefficient all-function scan was stopped before mutation. No failed
preparation attempt is counted as runtime acceptance.
