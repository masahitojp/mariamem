# Prepared UCA tables — bounded candidate adopted

On2026-11-05 the Human approved: “採用でいきましょう。0.7.0の成果が少しでも出そうだね”.
This adopts the bounded candidate `cbd25f027e804bbd529a85208589ba2dd2899b86`
for the v0.7.0 workstream after the
[review](../reviews/uca-prepared-canonical-adoption-review.md) and
[CI41961766293 receipt](../reviews/uca-prepared-ci-41961766293/README.md).
It authorizes preparation of protected main integration. Main merge approval,
Qualification, version metadata and publication are separate; none is claimed here.

Keep the original comparison readers and producer fallback. Reuse exactly the
fixed default UCA1400 tables for the two checked builtin identities, with source,
archive, Unicode and emitted-data hashes pinned. Verification is private and
separate from ordinary profiling. Each Fork still creates its own engine and
memory; this is avoided table construction, not a clone of a running InnoDB or
a prewarm pool. No public API or supported wire/profile scope changes.

The accepted evidence is two identical C source builds and106-file Go regeneration
with actual table/corruption/profiling/worker, native SQL, independent children,
Snapshot and cleanup controls on both supported platforms. Incoming development
origin275c1807 remains an UNQUALIFIED historical bootstrap; the actual canonical
acceptance source stays CBD above, never relabelled to later bookkeeping heads.

Five paired Mac fixtures show Fork -23.4%, CPU -15.5%, whole fixture -5.3% and
one-held-child RSS increment -5.0%. ASCII SQL median +2.0% and mixed +0.7% are
accepted as that small-cohort tradeoff. This does not assert SQL equivalence,
Ubuntu speed, parallel scaling or a general regression threshold. The extra
2.75MiB initialized image and maintained numeric input remain explicit costs.

Before integration, preserve current main, reconcile acceptance labels and run
normal app-bound `check`, `integration`, `Live required gate` on the actual head
under strict-base protection. Runtime/guest/input identity may reuse the fixed
canonical receipt only with a recorded byte-equivalence check. Retire automatic
pushes of the completed one-off candidate campaign; its manual workflow and all
oracles remain available. Normal CI and future Release build guards are unchanged.


## Protected integration authorization — 2026-11-07

The Human requested main integration through PR112 after confirming the adopted
candidate had not yet merged. Fix the Development workflow-classification
omission, preserve the original canonical runtime receipt and merge only through
the protected PR after required checks succeed on a fresh base. This authorizes
the main merge; qualification, version choice and publication remain separate.
