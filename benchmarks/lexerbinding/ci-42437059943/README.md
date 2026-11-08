# Actual prepared-lexer C guest acceptance

**PASS on macOS15 arm64 and Ubuntu24.04 x86_64.**
[Run42437059943](https://github.com/masahitojp/mariamem/actions/runs/42437059943)
used host source_commit `6134274a268155379329d9bd1ae394897e1f7e8e`, immutable C
origin `b1a265cc30a8603ced743c8aeb59c752751ff9d6`, guest SHA256
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.

| Gate | macOS | Ubuntu |
|---|---|---|
| Fresh transaction/Snapshot smoke | PASS | PASS |
| All638 compiled descriptors ×512 bytes | PASS | PASS |
| Corrupted prepared table rejected | PASS | PASS |
| Ordinary/diagnostic execution does not enable verification | PASS | PASS |
| Original CRC differential and page validation | PASS | PASS |
| Actual worker trap, notification, peer isolation | PASS | PASS |
| J1 unsafe controls fail as expected, heap/mmap | PASS | PASS |
| J1 protected controls, including race | PASS | PASS |
| Native SQL differential and two pristine children | PASS | PASS |
| Connections retired, host reaped, owners/temp removed | PASS | PASS |

Both hosts independently reproduced the same51 raw files and the same108
installed runtime files. Only installed `provenance.json` differs, due to
host-specific paths/record hashes. Host executables differ by OS/architecture.

- macOS job128598050713, artifact13600537187,
  ZIP SHA256 `74a79dec3a3f935e0a423166d72fb949e5b4619b05c64e11f2458c2102976254`.
- Ubuntu job128598050833, artifact13600162552,
  ZIP SHA256 `44dace064bfd225366f455ba9caecd0c3f7700776d3ec99a5342f8b4165f2ca7`.

The original run/jobs/artifact metadata and complete original file hashes are
retained. Runner-home prefixes in logs are normalized; `normalization.json`
records original/published hashes and reversible prefix components. Per-host
`SHA256SUMS.json` retains the **original CI checksums**; the top-level checksum
file covers the published receipt.

To reduce duplicate evidence, `development-reduced.json` retains runtime/tool
inventories, binary hashes/build information and source commit identities.
Three large source inventories are represented by canonical JSON digests after
exact verification. `../preserve_host.py` reconstructs them from the prior C
receipt's full inventory, exact Git diff C..HOST, installed runtime inventory
and the single staged guest-identity replacement. It rejects any discrepancy
before reducing. The input ZIP hashes and original development.json hashes
remain recorded; no acceptance assertion is inferred from a reduced count alone.

Recommendation: proceed to a bounded paired measurement of the actual C
candidate versus the adopted product bytes. The previous Go-overlay timing is
still historical. This receipt covers one C build with both-host translation and
execution; independent two-C-build reproducibility, dynamic XML-loader coverage,
performance and product adoption/main integration/Qualification/release remain
separate. No full framework or arbitrary-dump support is inferred.
