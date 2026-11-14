# Issue #63 final selection for protected integration

Decision being executed: incorporate the approved scoped allocation correction
through PR #76, after its normal protected checks. Recommend proceeding because
the known discarded allocation/zeroing is removed locally and the canonical
source and both supported hosts now pass the bounded correctness acceptance.
The strongest objection remains the small RSS saving and inconclusive CPU/batch
performance. The Human explicitly accepted known waste removal as the rationale;
this selection adds no speedup claim or performance campaign.

Reviewed runtime source_commit: `365a082bada9b5d3740d467739718d10cd155ca4`.
Original selection base: `954231bf7451f7b45bdbeb453a144204286eea18`.
Before integration, main advanced to
`b7d4f90ece837a422d2ea8217dfd09a61ee7feaa` (PR #80, D1 usage documents only).
That base is merged into the final candidate; runtime/generator objects remain
identical to the accepted source. The earlier daily PR run 41598512834 passed
all three required checks; strict freshness requires a new PR run after this
base update. No heavy guest acceptance is repeated for documentation alone.
[Run 41571252134](https://github.com/masahitojp/mariamem/actions/runs/41571252134)
succeeded in all three jobs. The [checksummed receipt](https://github.com/masahitojp/mariamem/blob/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/issue63-canonical-adoption/ci-41571252134/receipt.json)
contains exact source, job URLs, four verified ZIP digests and unchanged runtime
Git objects. [Earlier failures](issue63-canonical-adoption.md) remain historical.

| Approved condition | Result and detection |
| --- | --- |
| Minimal canonical source, no experiment installer/history | Three-file WASM-only patch in the ordered guest inputs; expected pre/postimages and prepared allocator contract fail closed. The permanent builder contract is retained. |
| Zero-fill, alignment, size, failure and free contracts | Both actual prepared-source allocator checks PASS, including four semantic mutations, dirty backing, controlled ENOMEM and C/C++ linkage. Real whole-guest WASIX OOM remains unverified; these checks do not detect it. |
| Independent canonical reproduction | Two source builds have identical guest/linked hashes; both hosts regenerate all 104 installed files byte-for-byte. Hash/inventory oracles detect mismatch. |
| Supported-host behavior | macOS15 arm64 and Ubuntu24.04 x86_64 pass original six J1 controls, Go race/integration, Live, Python/Snapshot and prepared consumers, including accepted-exception tripwires. CI step failures block acceptance. |
| Source/license/provenance | Both clean-source native audits cover 12 component families; positive and all 17 mutated build-evidence controls PASS. Source/guest/generated identities remain bound. |
| No performance overclaim | Prior performance stays INCONCLUSIVE, queue remains unmeasured and adverse pairs remain recorded. Wording is review-owned; CI cannot prove speedup. |
| Final protected PR checks | Still required on final PR head/base; no bypass. GitHub protection detects missing/failed checks. |

Final selection restores `v044-product-validation.yml` byte-for-byte from the
base and removes only the temporary candidate-workflow policy test. It updates
acceptance ledgers, exact-source license evidence, fixture result annotations
and documentation. Runtime, guest, converter and canonical builder code are
unchanged from the successful source. Runtime object IDs in the receipt are
compared to the final selection before commit, so the old run is reused by exact
runtime-tree continuity, never relabelled as a later-source run. Final daily PR
checks validate the metadata/workflow changes; a third heavy guest campaign is
not required for this selection.

No further missing implementation condition was found. No usage contract/API,
I/O default, Snapshot/Fork ownership, generated ownership classification or
version metadata changes; no corresponding usage-document contradiction was
found. No library or license classification is introduced. One-off CI is absent
from the final product diff, and the canonical allocator regression remains.
Unchanged body/data guards remain strict, including rejection of the old guest.

This review inspected the selected source/metadata diff and downloaded CI records,
including ZIP/file checksums, regeneration inventories, J1 and build/license
results. It did not measure new workloads, queue latency, low-memory WASIX failure
or cold setup. Acceptance is for this correction; Qualification, version choice
and publication are separate. The Human's incorporation approval persists.

Final-selection checks: 176 focused inventory/license/binding/guest-input/scope
and retirement tests PASS; normal generated-runtime verifier PASS; all saved
receipt checksums PASS; public-source check PASS. These checks cover the
metadata/workflow selection; they do not repeat or relabel the earlier hosted
runtime acceptance. Main protection was read back with required `check`,
`integration`, `Live required gate`, strict base freshness and admin enforcement.
