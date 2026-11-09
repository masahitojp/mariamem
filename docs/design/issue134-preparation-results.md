# Issue134: common preparation result and initial upgrade-cost judgment

Source under comparison: `cee676e8fcd77ee15db2b31639a1c100758c5b1b`,
branch `experiment/issue134-context-preparation`, based on published0.6.2 plus
the bounded resolver slice. These are source-preparation results; no guest,
runtime, consumer, performance or release acceptance is claimed.

## Actual results

| Engine/profile | Compared source members (files/directories/links) | Result |
| --- | ---: | --- |
| 12.3.3 / legacy-full | 32,201 | Complete match |
| 13.0.2 / legacy-full | 32,344 | Complete match |
| 13.0.2 / native-text | 32,353 | Complete match |

Each original frozen producer ran its original preparation script. The new
pipeline produced identical path sets, file bytes, permission modes and link
targets. This comparison intentionally excludes preparation receipts: the new
selected receipt has its own schema and is not release-eligible. It does not
relabel historical guest binaries as outputs of this candidate.
[Exact identities/hashes](issue134-preparation-evidence/comparison.json),
[focused checks](issue134-preparation-evidence/verification.json),
[input locations](issue134-preparation-inputs.json).

The selected pipeline keeps complete patch images, original function assertions,
corrected TIME proof and native unchanged-C-API images. It preserves observation
and experimental overlays. Canonical guest/input.json, guest/source.patch and
release/inputs.lock.json retain their original bytes. One common prepare function
serves both default and selected callers. Explicit context handles the lock,
archives, input view, source and receipts; version selection does not mutate
module globals or root product inputs. The selected native gate still requires
an experiment branch. The native route is not adopted by relocating its inputs.

The source-only comparison needed no SDK or compilation. Sampled owned peak was
1.47GiB; sampled minimum free space was34.00GiB (limits6GiB/12GiB). Preparation
commands took about16 seconds each with verified archives already cached; this
is not an acquisition/end-to-end/upgrade-speed benchmark. Comparison inventory
and checkout/cleanup time are outside those command durations.

Reproduce from the frozen candidate with Python3.14 and Git history:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/compare_selected_preparation.py \
  --scratch /tmp/issue134-compare --evidence /tmp/issue134-evidence
```

The driver refuses a dirty candidate, checks Git commit identity, applies a
6GiB/12GiB disk guard and60-minute preparation wall ceiling, runs original and
selected trees sequentially, and removes each compared tree. Caller preserves
the compact evidence and deletes the remaining downloads/scratch after use.
Production selected preparation itself does not use those historical checkouts.

## Initial maintenance judgment

The common preparation path is worth carrying into formal generation: it removes
per-version preparation-script edits and canonical-input swapping, while preserving
the old source result. This is a confirmed improvement in setup/selection work,
not a measured reduction in total upgrade cost. The strongest objection is that
semantic source and exact generated binding reviews can dominate the savings;
registration/proof metadata itself adds review work. Measure those remaining
steps before proceeding to a broad public campaign, and do not infer person-hours
or future engine compatibility from the three successful source comparisons.

| Recurring work | Evidence and current judgment |
| --- | --- |
| Select source/lock/patch/profile and keep old version reproducible | One registered resolver and one preparation pipeline now handle all three combinations. Engine SHA/path constants no longer need edits in selected preparation. Original canonical files stay intact. Improvement confirmed within these known stages. |
| Recreate ad hoc local input/checkouts | All selected input bytes live in this checkout, with hash references. Historical worktrees are used only as comparison oracles, not as runtime dependencies of selected preparation. UCA data/proofs and overlay bytes are retained under maintained paths. Improvement confirmed for source preparation. |
| Legacy prepared adapter repair | 13.0.2 legacy patch is195 lines/3 files; native is27 lines/2 files and leaves libmysql.c unchanged. This removes the legacy parameter/result adapters from the native repair surface. Counts identify scope, not saved time or a compatibility guarantee. |
| Upstream semantic patch review | Redo mprotect and pagecleaner sync-LSN adaptation remain. TIME/text metadata allocation checks and native internal API contacts remain. Full pre/postimages and function contracts must be reviewed for each new version. Not eliminated. |
| Descriptor/proof registration | Versioned image maps, archive/recipe identity, routine/UCA metadata and registry digests must be updated/reviewed. New registration work; corrected TIME/unchanged-file proofs are preserved. |
| Generation and binding | Whole function bodies, TLS/ABI, translation and source-origin/freshness checks remain. Formal selected receipt/build integration is not implemented by this slice. Cost still unmeasured on the new path. |
| Public/consumer verification and cleanup | Both-OS public/configuration/failure/oracle/consumer acceptance remains, with #138 stopped/unwaived. The source comparison neither runs nor replaces it. |

Historical actual upgrade evidence remains at
[1c5a6d5](https://github.com/masahitojp/mariamem/blob/1c5a6d59c70f6b5e39e1e92d0f659cb3f83b59b1/benchmarks/spikes/issue128-real/README.md).
That experiment's shared prepared/UCA setup and initial native implementation are
one-time costs, not recurring upgrade work. Its legacy/native fresh producer
1115.91s/886.02s and translation100.22s/118.82s are command durations under different
acquisition and verification conditions; they do not establish a speed/cost ratio.
No new SDK, guest/Go build, runtime test or CI was run here.

## What is still needed for the goal judgment

1. Thread the selected preparation receipt through the formal producer and
   artifact-specific binding checks; state the exact files and manual judgments
   needed to add an engine version while preserving the old entry.
2. Use the already-required fixed producer/public cohort for the generation,
   binding and acceptance observations. Record hand edits/review decisions
   separately from machine wait; avoid a separate build only for cost accounting.
3. #128 compares removed, remaining and added work with the recorded legacy
   upgrade. If binding/internal-API/proof burden outweighs preparation savings,
   revisit host/glue placement or the selected means before adoption.

The initial preparation benefit can be judged now. Total maintenance benefit
remains INCONCLUSIVE until those observations; product release is not required
to make that judgment. Performance is a separate #135 comparison. #134 itself,
main integration and release remain open decisions/work.
