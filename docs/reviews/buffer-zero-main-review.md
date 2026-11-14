# Buffer-pool zeroing: main adoption review

**Decision now:** adopt the descriptor-only zeroing candidate on main.
**Recommendation:** adopt, accepting the measured whole-suite limitation.
P1 Fork initialization is5.3/8.7% faster in the two fixed comparisons, and the
minimal candidate now passes independent regeneration and both-platform runtime
acceptance. The strongest objection is that the light-monitor P1 suite median
is12.6% slower and P8 Fork is effectively unchanged. The earlier guarded P1 suite
improved2.5%; the evidence does not identify the cause of this reversal.
I still recommend adoption for the bounded Fork initialization benefit and the
small localized change, without a whole-suite or parallel-Fork speedup promise.
If avoiding any observed serial-suite regression is the product priority,
retain current main instead. No additional measurement is proposed to obtain a
more favorable result.

## Reviewed object and decision boundary

Inputs reconstructed from this session and the saved plan:

- Artifact: [candidate report at2e1ecd31](https://github.com/masahitojp/mariamem/blob/2e1ecd315e4f85d5a7112112ad0858e8dc6765de/benchmarks/forkcost/buffer-zero-candidate/README.md).
- Candidate source_commit: `2e1ecd315e4f85d5a7112112ad0858e8dc6765de`.
- Measurement/base source_commit: `eeef899a296be8aa38cc9e3de0a550c428d4dca9`.
- Integration base source_commit: `291467b4fbac143093b35ea15d16cda798590f97`.
- Candidate branch: `experiment/buffer-zero-candidate`; prepared integration
  branch: `perf/buffer-pool-zeroing`.
- Cross-checks: [candidate plan](buffer-zero-candidate/PLAN.md), the report's
  “最小変更と正しさ” and “受入状況と次の判断”, parent
  [Issue122](https://github.com/masahitojp/mariamem/issues/122), and current
  [project status](../project-status.md).

The original outcome is less buffer-pool zeroing during Fork initialization,
with public SQL/lifecycle correctness retained. This review ends at a main
adoption recommendation. Release version, Qualification/publication, pgmem
remeasurement, unrelated engine tuning and issue closure are outside it.
No merge approval is inferred from CI success alone.

## Previous conditions and evidence

| Condition | Judgment and evidence |
|---|---|
| Minimal product patch; no spike modes/env/poison/abort | Satisfied: [`guest/source.patch` at2e1ecd31](https://github.com/masahitojp/mariamem/blob/2e1ecd315e4f85d5a7112112ad0858e8dc6765de/guest/source.patch#L3252), two hunks inside `buf_pool_t::create()` only. No experimental.patch. |
| Preserve common zero allocator, alignment, original-pointer free, failure paths, default16MiB, grow, non-WASM | Satisfied within bounded review: source diff retains these paths; [dirty-allocation and seven negative contract controls](../../benchmarks/forkcost/buffer-zero-candidate/build-evidence/build-buffer-pool-contract-0.json), actual large/resize/Fork/fault/redo receipts below. The C layout model is not an actual guest OOM proof. |
| Fresh identity, full worker/CRC binding and bookkeeping | Satisfied: [complete binding review](../../benchmarks/forkcost/buffer-zero-candidate/evidence/binding-review.json), negative controls and CI exact bindings. Guest, generated manifest, runtime constants, version registry and license mirrors agree. Fresh clean-host attribution is retained with its original audit SHA. |
| Independent source builds and both product platforms | Satisfied: [CI43569024494 receipts](buffer-zero-ci-43569024494/README.md): two equal C builds, full120-file regenerated inventory and both Go1.26.10 native jobs. I compared every saved generated file hash against the candidate. |
| Normal check/integration plus actual worker/CRC/SQL/Fork/Close | Satisfied: both native jobs and saved per-step results. No unit-only PASS is presented as actual guest execution. |
| Large, compressed, resize, read-fault and redo controls | Satisfied: both platforms' `large.json`, `fault.json`, `recovery-clean.json`, `recovery-dirty.json` under [the CI receipt](buffer-zero-ci-43569024494/README.md). EIO has one hit per path; repaired `.ibd` injection remains after Ready. |
| Fixed final-candidate current-main comparison with first SQL, Close and suite | Satisfied: both complete32-process matrices remain separate in the original report; later canonical code/host constants were compared to measured binaries. No newer-source execution or pgmem result is claimed. |
| Known Connector/Python/OpenSSL4 disposition | Satisfied by prior explicit Human acceptance. Raw local failure remains; supported CI integration succeeded. Do not reopen or describe the candidate as unfinished for this external defect. |

## Gaps, detection net and limits

1. **Performance uncertainty is material to adoption.** Both fixed matrices
   retain all samples; P1 Fork improves in all six paired comparisons, but P1
   suite reverses and P8 Fork is unstable. CI correctness cannot detect or
   establish general performance. The report explicitly limits the claim;
   additional benchmark rounds are not an acceptance condition.
2. **Finite initialization/failure coverage.** The producer runs
   `tests/buffer_pool_alignment_check.py`: dirty memory, exact descriptor range,
   allocation failure/free and semantic mutations. Actual large/compressed/
   resize/EIO/redo cases exercise page reuse and recovery in the candidate CI.
   These cannot prove arbitrary guest OOM, all corruption, other page sizes or
   unsupported platforms. Such universal properties were never the adoption
   condition; no stronger claim is made. The detailed buffer controls remain
   in the manual canonical candidate workflow, not every PR's daily check.
3. **Integration-source bookkeeping is subsequent work.** The prepared branch
   ports the production-quality candidate delta onto current main rather than
   merging the spike history. Main's intervening docs, benchmark and PyPI
   changes leave guest, `internal/`, toolchain and module pins unchanged.
   CI receipts stay bound to2e1ecd31; the updated build ledger closes PENDING
   using those receipts. Normal PR checks on the new integration source remain
   required before merge; the canonical run is not relabeled to that new SHA.

No other unsatisfied or hidden adoption condition was found. Current
README/Go/Python/releasing guides have no changed public contract to update.
Generated ownership, current guest pins and retained dependency attribution are
consistent; dependencies/notices are unchanged. No stale experiment-mode
comment was found in the product patch. Historical reports intentionally retain
their earlier pending/failed status and link forward through current status.

The maintenance tradeoff is localized: whole-pool initial clearing is removed;
review of descriptor initialization and page-owner initialization is added to
future upstream patch review. Existing allocation/alignment/free, converter,
CRC/worker binding and per-series generation responsibilities remain. No new
engine API hook, host algorithm or dependency is introduced. Maintenance hours
are unmeasured; source line count and CI PASS are not claimed as time savings.

## Next action

The integration candidate includes the unchanged runtime, successful exact-SHA
CI evidence and updated canonical ledger. Approve or decline main adoption with
the serial-suite limitation above. On approval, merge after required PR checks;
release remains separate. This review used saved fixed measurements, source
diffs and one successful run/job metadata read plus its actual artifacts. It
started no engine build, performance campaign or external-defect investigation.

Integration preparation verification:26 focused tooling/license tests passed;
full historical evidence verification reproduced all64 process identities and
both summary/CSV matrices; public-source and clean-diff checks passed. The new
branch's entire `internal/`, `guest/`, module and translation/input pins are
byte-identical to the CI-tested candidate. Current main's unrelated publication
and guide changes are retained. No full local runtime rebuild was justified by
the subsequent records-only delta.
