# Dump comparison exit — comparison complete, conditional on experimental host correction

The Human requires the reader SQLSTATE gate and a recorded experimental host
delta before closing the spike as comparison complete. Route choice,
productization and host correction adoption are post-spike decisions. The prior
[comparison report](v06x-dump-comparison-completion.md) and CI40192797648 remain
historical evidence for9494e75, not evidence of the new deterministic assertion.

New candidate source_commit `c417e21ba7dabefa5d95600ea322091732430c97`, parent
`9494e755a5e7d79a9702e1d1dc7c1caae993e801`, on experiment/dump-import:

- Reader sql_failure now requires SQLSTATE42S02 as well as errno1146, exact
  cause/phase/span, partial DDL, cleanup and no Snapshot/test admission.
- Positive controls accept42S02. Negative mutations reject HY000,42000 and
  absent state for both reader and native classifiers.
- Runtime, guest/generated, producer/options, canonical bytes and SQL oracles
  are unchanged. The bounded workflow reruns the full existing matrix.

The [experimental host record](v06x-dump-sqlstate-evidence/approved-host-delta.json)
pins before/after hashes for the decoder and its two regression files. It records
unsigned32 input0..4294967295, low16 protocol projection, invalid-input rejection,
missing-status startup behavior, nested results and preservation of all low16
flags. Those exact file hashes remain unchanged. **Every spike PASS is
conditional on that correction**; the record is not host adoption approval.

[Focused checks](v06x-dump-sqlstate-evidence/local-checks.json) passed on the
exact new candidate:38 binding/framing/classifier tests,25 acquisition unittests,
public-source and whitespace checks. Saved local binding is INPUTS_VERIFIED,
not fresh producer/comparison evidence. The checksum manifest covers these
local records independently of earlier CI receipts.

## Closure receipt

**Comparison complete.** The authorized exit criteria are met by
[CI40197606173](https://github.com/masahitojp/mariamem/actions/runs/40197606173)
on exact source_commit `c417e21ba7dabefa5d95600ea322091732430c97`. All three jobs
passed: native121181728703, Ubuntu121181983291, Mac121181983298. The new
[assessment](v06x-dump-comparison-evidence/ci-40197606173/assessment.json)
and three original artifact ZIPs are saved with run/job/artifact metadata and
independently verified archive digests. The
[checksum manifest](v06x-dump-comparison-evidence/ci-40197606173/SHA256SUMS.json)
covers all saved receipt files, including the exact experimental host delta.

| Observed host | Python / pytest | Native client | Library reader |
| --- | --- | --- | --- |
| Ubuntu24.04 x86_64 | 3.11.17 / 7.0.0 | PASS | PASS |
| Ubuntu24.04 x86_64 | 3.14.8 / 9.0.2 | PASS | PASS |
| macOS15.7.9 arm64 | 3.11.9 / 7.0.0 | PASS | PASS |
| macOS15.7.9 arm64 | 3.14.7 / 9.0.2 | PASS | PASS |

No exercised comparison cell failed or skipped. The native job log confirms38
focused tests PASS, including wrong-SQLSTATE mutations. All four reader SQL
failure records contain errno1146/SQLSTATE42S02; the new deterministic classifier
accepted them. Both native references and direct guest routes match; eight
positive lifecycle scenarios yielded16 independent child test passes. All24
negative scenarios passed their classifiers with cleanup and no Snapshot/test
admission. Original endpoint contacts are zero. The exact candidate producer
reproduced canonical SHA256081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c
and its separate BOUND receipt. No earlier receipt is relabeled.

The PASS remains conditional on the recorded experimental host correction;
comparison closure does not adopt that correction. A subsequent spike review
chooses library / external client / defer / productization and assesses host
correction adoption separately. This closure makes no route decision and starts
no productization, main integration, Qualification or release. Views/triggers,
cold Mac and setup-cost remain outside scope.
