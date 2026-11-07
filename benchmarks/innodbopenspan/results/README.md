# System-tablespace open attribution (P1 diagnostic)

Conclusion: the system-tablespace `SysTablespace::open_or_create()` call is a small part of the broad InnoDB open/recovery interval. It does not explain the Fresh/Fork difference. Continue only with a bounded split of the remaining interval; no optimization candidate is established.

| Per-child mean, ms | Fresh | Fork |
|---|---:|---:|
| Broad open/recovery interval | 0.9854 | 9.1925 |
| System-tablespace open/create call | 0.0332 | 0.3328 |
| Remainder (per-child subtraction) | 0.9522 | 8.8597 |

The call accounts for 3.6% of Fork's broad interval and 0.300ms of the 8.207ms Fresh/Fork difference. In three alternating pairs, call deltas were +0.2995/+0.3003/+0.2989ms; remainder deltas were +7.8678/+7.9166/+7.9381ms. No primary API startup or these measured stages exceeded 100ms. No child or tail was excluded.

Fresh has no application transaction history initially, but creates redo/UNDO structures. Fork attaches snapshot file-block views; it still runs engine validation, recovery checks and reconstructs runtime state. This result does not establish actual redo replay or identify the dominant remaining function. Source mapping puts checkpoint discovery, UNDO initialization, dictionary loading, recovery and transaction setup among the remaining work; their individual durations are unknown.

Scope: one macOS arm64 host; P1, 3 alternating pairs x48 children (144 per route); 2 warmups, 2 positive pilots, 2 deliberately wrong-seed controls. All 12 processes /394 children retained, including complete owner logs. Correct state, wrong-seed rejection, wave ordering, trace coverage, zero residual mappings and image FDs all passed. Eight reducer mutations are rejected. Positive controls are not independent native SQL parity acceptance.

All processes use the same diagnostic binary, warm static-page image and pre-prepared baseline. Fresh creates its child schema/seed; Fork uses the baseline. Both actually enter the expected create_new_db branch. New host-clock events surround the exact mapped system-space call; they are nested within the same child's guest interval. Whole generated-file hashes, embedded data hash, alias, native source strings and argument identities are checked. No guest rebuild or tracked generated-code change was made.

Measured source: 59ef28bcf9c537a0cb61f052fee36698eaea2dfe. Guest SHA256: 6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe. Native source basis and prior analysis: docs/reviews/innodb-startup-source/ on this branch. The generated caller/callee are Fn18569/Fn16690. The latter contains inlined doublewrite/header work, which is included but not separately timed.

These are observer-on attribution results, not ordinary performance claims. Absolute times differ from the earlier campaign (~6.5ms Fork broad interval); do not combine those values or interpret the difference as a regression. There is no observer-off arm, Linux result, stage CPU decomposition, or optimization/adoption approval. The strongest limitation is instrumentation perturbation; stable paired deltas support attribution within this campaign only.

## Replay

From this results directory, run `python3 -B analyze.py . --check` and `python3 -B check_analysis.py`. Both are read-only for original evidence and require no temp/build state. summary.json has per-process p50/p95/means and all paired deltas; observations.json.gz retains child-level traces. Original process reports/logs/timings and every owner archive are retained with member/file hashes. collect.py documents original reduction (requires unpacking original-process-reports.tar.gz); normal replay does not regenerate or overwrite evidence.

For a new experiment use the measured source, `python3 -B benchmarks/innodbopenspan/build.py` then run.py with the plan's budgets and workspace layout. This is a reproduction recipe, not authorization to add repetitions. Initial generated mapping took 167.1s; one diagnostic build took 138.2s. No guest/native rebuild, CI, product integration or release occurred.

Analysis initially rejected a stale 32-process uniqueness assertion from the prior reducer. Corrected to the declared 12-process matrix before reduction; measurements were not repeated or changed.
