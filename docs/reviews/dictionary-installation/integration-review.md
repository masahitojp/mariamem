# Dictionary wait candidate — integration recommendation

Decision now: adopt this narrow correction for main integration. I recommend
proceeding: the actual guest now reports a contended dictionary wait to its pool,
queued work progresses without releasing the dictionary owner, and the approved
canonical/both-platform correctness gates pass. The strongest objection is the
single-Mac P4 slowdown (paired median+2.79%, slower in4/5 pairs), alongside no
typical sample/CPU improvement. I still recommend the correction because the
approved direction is this bounded scheduling fix, with no uniform-speedup
gate; the P8 comparison and removed observed long PREPARE support it only
partially. If avoiding that measured P4 cost is the product priority, defer
integration. This review does not authorize a merge, Qualification or release.

Reviewed source_commit: `a8389b6d543e449906e8064b8f37200c74c2c394`.
Base/current remote main: `8df45792a927e440972266ee799d6f7223713e14`.
The decision document, candidate diff, installed evidence and successful
CI43330322013 are the reviewed artifacts. These inputs and the integration
question were reconstructed from the approved [decision](../../decisions/dictionary-wait-notification.md)
and this task's continuation; the Human supplied the completed-CI notification.
The reporting checkout was `experiment/dictionary-install`, not main. Evidence
bookkeeping appended after this source keeps all CI claims pinned to this SHA.

## Prior conditions and detection

| Approved condition | Assessment and evidence | Existing detection |
|---|---|---|
| Exact canonical patch/profile/prepared dictionary bytes, no experimental overlay | Satisfied. [Bootstrap](bootstrap.json) and [new canonical guest record](ci-43330322013/guest.json); guest5f8b711f and linked7f34f467 agree across both independent builds. | `tests/test_dictionary_wait_source.py`, the canonical precompile prepared-source guard, `verify_build` and20 evidence mutations on each OS. |
| Normal installation with unchanged complete worker/CRC body/table guards and provenance | Satisfied. Only accepted guest IDs change in `scripts/runtime_thread_lifetime.py` and `runtime_crc32c.py`; matcher/body/table hashes remain unchanged. Both independent regenerations match all120 installed files. [Assessment](ci-43330322013/assessment.json), [binding](binding.json). | Exact source inventory, normal generator, CRC/thread guards, full regeneration; six actual J1 ownership controls on each OS. |
| Actual patched guest progress, exclusion, balanced wait accounting, uncontended/nonpool and disposal | Satisfied within the agreed boundary. `TestDictionaryWaitActualGuest` invokes actual `p6.Fn17744(c,0)`, never supplies begin/end;21 local cases cover pending/late-submit/uncontended at concurrency1/16 and nonpool, three repeats. Both CI logs execute its selector. | `tests/test_dictionary_wait_runtime.py` rejects removed begin/end/lock bodies and missing ordering; actual guest assertions cover queue progress, exclusive owner, WAITING reset, worker/ref retirement and mapping debt. |
| Two-build/full-regeneration and both-platform SQL/lifecycle/ownership acceptance | Satisfied at the reviewed SHA. All four jobs in [CI43330322013](https://github.com/masahitojp/mariamem/actions/runs/43330322013) pass. [macOS integration](ci-43330322013/macos-15/integration.txt), [Ubuntu integration](ci-43330322013/ubuntu-24.04/integration.txt), [checksummed assessment](ci-43330322013/assessment.json). | Daily Go/vet/Python, focused race/runtime integration,54 Python runtime cases, native SQL/prepared/UCA comparison with two children and zero cleanup debt, snapshot smoke. |
| Fixed30 installed-candidate comparison without rerolls | Satisfied. [All30 observations and report](performance.md): P4 median607.80→611.60ms, P8 551.68→535.45ms; paired median+2.79%/−7.68%. Separate PREPARE >100ms1/189→0/189. Runtime/guest/API bytes are unchanged between measured4e2ac423 and revieweda8389b6d. | Committed fixed matrix and compact analyzer validate all30, metadata, cleanup and four negative controls. CI is not a performance acceptance oracle. |

## Material limits and remaining judgment

- P4 regression is observed in this finite workload; broader benefit is unknown.
  P8 is faster in4/5 pairs, while its sample median rises79.764→88.716ms and
  cleanup maximum rises11.715→27.922ms. Those observations are retained, not
  excluded. Existing correctness CI cannot detect future performance regressions;
  this fixed comparison is the available evidence, not a numerical adoption gate.
- Natural-tail attribution, purge, and the owner/pending/read-generation/recovery
  sequence remain outside this correction. No check here proves full causal
  coverage; the approved decision explicitly accepts that boundary.
- LONG/nested and exceptional termination inputs remain outside the notification
  contract. The controlled caller asserts neither WAITING nor LONG on entry.
  The normal generated caller `Fn18236` has the same whole body after whitespace
  normalization as baseline (hash in assessment), and remains the only direct
  caller with its two existing eviction call sites. The regression exercises the
  shared lock prologue through argument0; it does not independently force every
  later eviction-body branch. Exact source/guest guards catch unreviewed changes,
  but do not establish arbitrary future caller safety.
- Prepared-consumer logs explicitly retain existing accepted Python functional
  exceptions; PASS here is the existing bounded oracle, not universal protocol
  compatibility. No new exception or relaxed test was introduced.

## Missing-things scan

No unsatisfied or unlisted implementation/verification condition was found.
The separate Human integration decision remains open. No product API/default
change was found, and the version-gated README/Go/Python/releasing documents are
unchanged; no new contradictory user contract was found. No ownership omission
was found: the actual-guest test is in `HANDWRITTEN_FILES`, source guards are in
normal verification, and both CI generation inventories include it. Complete
worker/CRC guards, selected12.3.3 source pins, prepared-source records, initial
data and license mirrors are checked without weakening their boundaries.

Independent regeneration, opposite-OS acceptance and the fixed comparison are
complete. Build evidence is now reconciled to the successful source while the
UNQUALIFIED bootstrap, failed runs and old UCA receipts keep their original
identities. No stale comment changing the meaning of removed behavior was found
in the touched runtime/installer boundary. No new benchmark or runtime build was
run for this receipt review; metadata-only follow-up uses focused source/license
checks. Qualification, release, Issue140/156 closure and main integration have
not been performed. If the Human approves integration, use normal protected-main
checks and retain these performance/semantic limits; release needs its own later
explicit versioned request.
