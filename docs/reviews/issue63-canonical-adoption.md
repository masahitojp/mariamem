# Issue63 canonical product candidate

Human approved incorporation on2026-11-03 for the clear, local removal of wasted
allocation/zeroing, accepting the small observed RSS benefit without a speedup
claim. [The decision](../decisions/buffer-pool-alignment.md) records that scope.
The original experiment remains INCONCLUSIVE for overall performance; its
queue gap and adverse CPU/batch pairs are not relabelled.

## Selected source and actual results

Original base main: `f09d5167172f091ccc0b20f78b817fe870d3cadf`.
Integration base updated to `954231bf7451f7b45bdbeb453a144204286eea18`
(Django-only adoption; guest and Go runtime inputs unchanged). Earlier receipts
retain their original source identities; candidate CI checks the final head.
Canonical C input source_commit: `1b0a0c5c569c49f3643550911d62d85d351f15fb`.
Expected-inventory authoring: `5f8a6682ea2f96611bde135eb285aca90e62f913`.
Normally generated runtime / clean native build:
`8b641cfba060f2bede1cda9c45d09ca5764df32d`.

The source change is exactly the reviewed three-file allocator/header/pool patch,
now an ordered canonical portability entry with exact pre/postimage hashes.
No experimental.patch or experiment-specific installer is included. Source,
converter and old whole-function/data guards remain fail-closed; only the exact
new guest identity is registered. The prior accepted identity is now explicitly
rejected by the binding controls.

The single canonical-source bootstrap took1211.63s and produced guest
`96129c76872ab0891329e8e356233d691208195654e878a2853139901712d05f`, matching the
previous experimental guest. It is inventory-authoring evidence, not independent
reproduction or Qualification. All actual prepared C postimages match the prior
contract-checked files. Normal converter output matches the expected inventory,
and the normal installer produces byte-identical executable Go/assembly to the
previously tested guest (103 files; provenance metadata differs).

Local macOS27.2 arm64/Go1.26.10: actual-prepared C contract and4 semantic mutations
PASS;114 focused Python tests PASS; all19 worker body hashes and initial memory/
TLS binding PASS; original J1 heap/mmap unsafe failure and protected/race controls
PASS in all6 expected outcomes; real SQL/transaction/Snapshot/Fork/Close smoke
PASS. A clean-source native symbol audit confirms all12 recorded component
families. The audit records source8b641cfb, not a later bookkeeping SHA.

The first nested-worktree host build carried the parent repository's VCS metadata
and was rejected by the license audit. The same exact source was rebuilt from an
independent clean checkout; correct8b641cfb/modified=false metadata and the fresh
symbol audit then passed. The clean-host SQL smoke was repeated successfully.
No identity/body guard was disabled. A temporary pip pin conflict was corrected
by using the repository's requirements unchanged. These preflight failures do
not become successful source receipts.

The first daily source check detected a stale Python package license-inventory
mirror (1 failed, 66 passed before stopping). The mirror was synchronized with
the newly audited release inventory; the check is rerun on the updated source.

## Remaining acceptance and detection

| Boundary | Current evidence / required check |
| --- | --- |
| Local allocation semantics | C contract exercises dirty backing, exact alignment, size, ENOMEM return and free; actual full WASIX build succeeds. Real whole-guest OOM is not claimed. |
| Source correctness | Four canonical patch postimages plus existing prepared owners; pre/postimage mismatch fails prepare_guest.py. |
| Independent canonical reproduction | Pending candidate CI:2 fresh source builds, normal Go regeneration and every-byte comparison. Current build ledger honestly remains pending. |
| Supported hosts | Pending candidate CI: macOS15 arm64 and Ubuntu24.04 x86_64, existing integration and original J1 controls. Local Mac27.2 is not substituted. |
| License/source/provenance | Clean local native attribution PASS; CI repeats attribution and positive/17-negative build guards on its exact source. No new library/notice classification. |
| Performance | Previous five-pair result unchanged; no new campaign. Queue missing and adverse pairs remain named limitations of the evidence. |
| Product/API scope | No public API, default I/O thread setting, Snapshot/Fork ownership or teardown-policy change. |

The canonical builder now runs the prepared allocator contract before each source
compilation, so future zeroing/alignment/size/legacy-entry regressions fail there.
The candidate-only workflow does not duplicate daily Ubuntu source checks; it
adds the required fresh source/native acceptance for this guest change. Its
experiment-branch trigger and contents:read permissions cannot publish a release.
Remove that one-off workflow and its policy test during final candidate selection
before main merge; retain the permanent canonical-builder allocator check.

Normal protected PR checks and this bounded candidate CI must succeed before
integration. The Human's adoption direction persists; no repeat decision about
speedup is requested. Qualification, version selection and publication remain
separate, and no release transaction is started here.
