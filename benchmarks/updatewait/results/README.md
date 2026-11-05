# Load-OFF slow UPDATE observation: not reproduced

**Answer to the original question:** the saved366ms UPDATE cannot be placed in execution, autocommit/commit or flush from its existing client timings. The bounded new observation did not reproduce a natural UPDATE>100ms, so that phase and its relationship to the previous COUNT queue stall remain **UNDETERMINED**. The finite investigation is complete, not the root-cause diagnosis. No more runs or fixes were added.

Original source-bound case: [buffer-load-off result](https://github.com/masahitojp/mariamem/blob/11cdb5df4f199af177348b7015b68296e94a4f31/benchmarks/bufferloadoff/results/README.md), P8/OFF round3 child41: COUNT1.235ms, UPDATE366.443ms, check SELECT0.896ms. ExecContext includes the guest statement/autocommit and response; no guest stack was captured then.

## Fixed new observation

Same adopted-UCA product1862f4a89397bddfa1820d835106d3437a438cf7, origin guest6d744220…; same experimental load-OFF26-argument configuration, Pipe,1,000-row seed, P8/48children. Maximum3 processes, stop after first usable natural capture or3 processes. A100ms UPDATE-only timer may capture at most one2MiB labelled goroutine profile/process. No detailed queue/futex instrumentation, setting change, explicit transaction, extra primary SQL or canonical guest rebuild. This observer is not a performance comparison.

| Process | Children | UPDATE p50 ms | UPDATE max ms | UPDATE>100ms | Natural snapshots |
|---|---:|---:|---:|---:|---:|
| natural-0 |48|0.538|20.486|0|0|
| natural-1 |48|0.533|21.248|0|0|
| natural-2 |48|0.372|8.970|0|0|

All144 natural children pass pristine COUNT/SUM, independent UPDATE/verification and cleanup; no COUNT/check SELECT exceeds100ms either. Zero occurrences under this observer is not proof of resolution, a probability estimate or evidence that the old366ms was noise. Timer goroutines and profiler labels can change scheduling even when a profile is never triggered. No retries beyond the fixed3 natural processes.

## Controls and limits

- Effective-setting preflight: root+8children, load OFF/read1/write2/purge1/buffer pool16MiB confirmed; all SQL/isolation/cleanup pass.
- Artificial control: one200ms client hold before UPDATE. Profile began101.115ms, ended101.907ms, wrapper returned201.937ms,21,095bytes, no truncation. Actual runtime child0 labels appear on generated guest execution stacks. This validates timer/label capture only; it is deliberately **not an engine stall**.
- Wrong-seed control: fails pristine oracle before UPDATE, no snapshot, cleanup passes.
- Selector unit tests and child-label parser wrong-child/non-guest/malformed/cross-group rejection pass.

**Metadata naming limitation:** the measured collector field `whole_profile_inside_exec` refers to the observation wrapper window, which includes the artificial pre-Exec hold. The artificial snapshot therefore occurred before the SQL call despite that legacy field being true. No natural snapshot was accepted or used for an engine-phase claim. Reuse as an engine-phase gate must first add an actual Exec-entry timestamp and distinguish wrapper versus SQL bounds; the current control does not validate that classification branch. Original metadata is retained rather than rewritten.

Same-guest CI artifact41961766293/13386565859 was inspected and mariamem.wasm SHA256 verified as6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe. It has no function-name section. A bounded standard-library DWARF inspection found no known SQL anchor names or supported mapping to canonical generated indices. The old guest function numbers are not silently reused. Source-backed function-phase correspondence would still be required if a natural case is later captured. The archived artifact is an input check, not new CI acceptance.

## Provenance and what remains

Measured harness source_commit `f00c506da34c247045a2a51bbd8879ae68168cfa`; clean commit object identity checked using git_identity before build. Only benchmark source differs from product. The same UNQUALIFIED translated-Go load-OFF argument overlay and existing startup observer are used; ordinary timing directory remains disabled. Go1.27.3/CGO0/GOMAXPROCS8/GOGC100, macOS arm64, one local host. Binary/overlay/input hashes are in inputs.json. Six DB processes total: preflight8children, artificial1, wrong-seed1, natural144. All positive oracles/cleanup pass; the deliberate negative is not relabelled PASS.

Recommendation: retain the original UPDATE as an unresolved residual and keep load-OFF adoption/tradeoff judgment separate. Do not continue repeating this observation to force a capture. A selected future task needs a newly captured natural UPDATE (or an explicitly controlled fault that is not misrepresented as natural), an Exec-entry marker before reuse, and a verified current function map or a few source-level execution/commit/flush hooks. The present bounded runtime cost was at most3×120s plus build; further-capture success is not guaranteed. Recovery of the linked name-bearing Wasm/full symbol map or canonical guest rebuild/hook cost is not yet estimated and is outside this round. No new budget is silently opened.

This does not overturn the preceding OFF batch improvements or its failed P8 Fork guard. No canonical guest/product/API/default change, main merge, new CI, Qualification or release.

## Saved evidence and replay

receipts.zip retains the six reports, labelled artificial profile and metadata, fixed plan, collector/build/reducer and symbol-inspection input/assessment. Complete guest Wasm and compiler/module caches are reproducible scratch. Extract ZIP into an empty directory and run `python3 analyze.py --check` for read-only3-process/control/negative/CSV/summary verification and missing-process rejection without temp/build trees. Use measured source and archived build.py/run.py only for a separately authorized new observation. SHA256SUMS.json covers published artifacts. The original artificial metadata naming limitation is explicit in summary.json.
