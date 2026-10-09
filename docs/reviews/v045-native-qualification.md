# v0.4.5 native qualification and feedback latency

[Runtime qualification 37958395630](https://github.com/masahitojp/mariamem/actions/runs/37958395630)
completed successfully for exact source `8a30e184890ba686caba65d1876aee829a4a178a`.
The new `runtime-qualification-v1` contract passed on macOS15 arm64 and
Ubuntu24.04 x86_64. No old Product evidence was relabelled.

Shared `runtime_validation.fetch_qualification` authenticated workflow/repository,
run source/result, both native jobs, artifact IDs and ZIP SHA256s.
`runtime_validation.evidence` checked archive inventory/checksums, version/contract,
coverage, exact toolchain/native environment and the full check/integration commands.
The 698 tracked-input hashes matched both OSes and the exact local Git source;
Git tree/modes and guest SHA256 matched too. Both cleanup receipts report scratch removed.
[Compact receipts](v045-native-qualification.json) preserve commands and identities.

| Boundary | Ubuntu | macOS |
| --- | ---: | ---: |
| source/unit `check` | 371.58 s | 608.81 s |
| real-runtime `integration` | 518.10 s | 1203.40 s |
| qualification Actions step | 896 s | 1835 s |
| whole native job | 921 s | 1865 s |

These are one cold native CI observation, not p50/p95 or a regression threshold.
Jobs ran on separate native machines. Their commands contain compilation/tooling
and test time; they do not imply MariaDB startup itself takes minutes. Parallel
CI feedback is dominated by macOS: approximately 31 minutes after job start.
Queue delay is not included in the whole-job column. Local warm Python/source
check was 27.64 s overall (pytest 19.69 s, 486 PASS/31 skips); prerequisites, queue,
cold Go compilation and runtime qualification are outside that local boundary.
This is a responsibility map, not a like-for-like speedup claim against v0.4.4.

Artifact pins:

- macOS ID `11631835975`, ZIP `092ef7d01a8c2a288c66ab1caa9deaa4871dde53a40f6b80460974fc46251930`.
- Ubuntu ID `11630977941`, ZIP `a30b6ed2be213e7bebdf757c3e3d48fd0fccbd94a95303425ce9a45237e8acf7`.

This qualifies runtime/source commands only. It does not claim newly built wheel,
final artifact GORM/SQLAlchemy/pytest, public distribution smoke, fresh upstream
WASM generation or Snapshot performance. Those retain their separate owners.
No release reuse intent has been activated merely to record these results.

The receipt verification reproduction uses the shared helpers against the pinned
run/artifacts, then compares `source_inventory(root, tested_commit)`, the Git-tree
JSON digest and `release/generated-go-inputs.json` guest identity. Downloaded ZIPs
are temporary; compact identities/receipts and Git preserve the evidence.

Next: finish remaining historical caller/owner classifications, then use the
existing measurement primitives for full-public Snapshot/crossover/product work.
No performance optimization, main merge or release is implied by CI success.
