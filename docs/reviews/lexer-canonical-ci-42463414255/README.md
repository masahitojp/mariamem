# Canonical prepared lexer acceptance:42463414255

**PASS bounded product candidate** at source_commit
`b04b49dbc3dee5e2773b8d775d2202ca1eccff92`.
[Canonical CI](https://github.com/masahitojp/mariamem/actions/runs/42463414255)
and [Development42463420122](https://github.com/masahitojp/mariamem/actions/runs/42463420122)
both succeeded. Main integration, Qualification and release remain separate.

| Input/gate | Evidence | Result |
|---|---|---|
| Two independent C source builds | guest job128677392694; both guest.json repetition entries agree | PASS |
| Native12.3.3 normal/prepared SQL | reference job128677392880 | PASS |
| macOS15 arm64 independent regeneration/acceptance | native job128680408235 | PASS |
| Ubuntu24.04 x86_64 independent regeneration/acceptance | native job128680408276 | PASS |
| Installed source identity |110-file inventories equal each other and the committed candidate | PASS |
| Build-evidence negative controls |18 per host, including prepared-lexer header provenance | PASS |
| Full638 lexer maps, corruption, ambient/profiling separation | both actual-tables.txt | PASS |
| UCA, actual worker-failure isolation, CRC | both actual-tables.txt / crc.txt;832 CRC and80 page cases | PASS |
| Forced J1 schedules | each worker-results.json:2 unsafe expected failures,4 protected successes | PASS |
| Normal and binary prepared SQL/native, two pristine children | each sql-children.json matches reference native hash and values | PASS |
| Cleanup | refs0, exit0, reaped=true, root_exists=false; Fresh/Snapshot smoke | PASS |

Guest SHA256 `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`;
linked SHA256 `69dbde341c47149463d57b9f6cd4d2683506e7936dc756a4793f5425b788a722`.
The native prepared output includes Unicode, NUL, quote and backslash parameters
(`text_hex=4100275ce697a5e69cace8aa9e`) and arithmetic output7 on both hosts.
No proposed native/prepared acceptance gap remains.

## Artifact identities

- macOS artifact13611003967:
  `sha256:009d61c7344f36f357e00f9786439ecaad5b7bbeb250ba012fbb7858137f33e2`
- Ubuntu artifact13610743078:
  `sha256:c84cb9c2cecba3ab014c0b287091d16bc8a28dec27ebda129026c582abc25b17`
- Native reference artifact13610104871:
  `sha256:b5fec454e42d3fa138b8cc5863204325004e13e0314b65dd6d11c06f9e89785d`

All three ZIP bytes were hashed before safe extraction. Original nested
SHA256SUMS were verified before publication. `artifacts-verified.json` preserves
the original per-file hashes. Known CI paths and trailing console whitespace are
normalized with original/published hashes in `normalization.json`; the root
SHA256SUMS covers published bytes. Nested manifests retain original CI hashes.
The guest artifact ID/digest is also retained in `artifacts.json`; binary guest
storage is not duplicated because native receipts retain guest/build metadata
and all canonical source inputs are pinned.

## Source identity and reuse

This receipt binds b04b49db only. Earlier canonical-source input42448601842 stays
at fd615a53; experimental acceptance42437059943 stays at host6134274a / C origin
b1a265cc. No prior receipt is relabelled. Current follow-up changes update this
receipt, current status, the build-acceptance ledger and fixture acceptance
metadata only. Runtime, guest, adapter, workflow and test-body bytes remain
identical to b04b49db. Required protected-PR checks still apply to the new head;
this documented code equality supports reuse of the heavy candidate acceptance.

No new performance run was made. Prior accepted single-Mac P1/P4 limits, absence
of demonstrated RSS/stable P4 whole-batch improvement and unassigned SELECT tails
remain unchanged. Dynamic XML loading has source/component coverage; full-loader
runtime coverage, cold/setup cost and arbitrary workload coverage are not claimed.
