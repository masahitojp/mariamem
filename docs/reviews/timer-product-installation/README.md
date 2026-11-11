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

The fixed Go1.26.10 VCS scanner does not detect `.git` files in this nested
worktree layout. The first local host has no VCS stamp and is not attribution
proof. An exact147e72ae clean local clone produced a correctly stamped host;
`audit_generated_licenses.py` passed without relaxing its identity requirement.
An initial daily attempt incorrectly inherited that build-only Git environment;
it was interrupted, the product checkout stayed clean, and tests were rerun without
GIT_DIR/GIT_WORK_TREE. The failed attempt had also written shared core.worktree
and test user settings; those exact test values were removed, the original
primary-worktree dirty-file list and global user identity were verified restored.
One unpublished commit's author metadata was corrected without changing its
tree; checked-commit.json preserves the original measured object for verification. Subsequent ordinary validation identified the two actual
pin/workflow issues recorded in the checkpoint, which were fixed before CI.
