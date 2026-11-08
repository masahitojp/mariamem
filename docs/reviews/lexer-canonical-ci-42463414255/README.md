# Canonical prepared lexer acceptance:42463414255

**PASS bounded product candidate** at source_commit
`b04b49dbc3dee5e2773b8d775d2202ca1eccff92`.
[Canonical CI](https://github.com/masahitojp/mariamem/actions/runs/42463414255)
and [Development42463420122](https://github.com/masahitojp/mariamem/actions/runs/42463420122)
passed. Main integration, Qualification and release remain separate.

`assessment.json` owns the conclusion. `receipt.json` retains structured observed
results, source/run/job/artifact identities, original hashes and reconstruction
references. `SHA256SUMS.json` covers the published compact files.

| Gate | Compact evidence | Result |
|---|---|---|
| Two independent C builds | guest job128677392694; two equal repetitions | PASS |
| Native12.3.3 normal/binary-prepared SQL | reference128677392880; native_reference | PASS |
| macOS15 arm64 / Ubuntu24.04 x86_64 | native128680408235 /128680408276 | PASS |
| Independent Go regeneration |110-file inventories equal each other and pinned source | PASS |
| Build-evidence mutations |18 shared outcomes, separately observed on both hosts | PASS |
|638 lexer maps, corruption, ambient/profiling separation, UCA, worker isolation | actual_guest_passed_tests per host | PASS |
| CRC |832 length/alignment and80 page cases per host | PASS |
| Forced J1 |6 per-host schedule outcomes:2 expected failures,4 protected successes | PASS |
| Normal/binary prepared SQL, two pristine children | sql_children_cleanup matches native reference | PASS |
| Cleanup and Fresh/Snapshot smoke | refs0/exit0/reaped/root removal; smoke PASS per host | PASS |

Guest `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`;
linked `69dbde341c47149463d57b9f6cd4d2683506e7936dc756a4793f5425b788a722`.
Prepared output on native and both hosts includes
`text_hex=4100275ce697a5e69cace8aa9e` and arithmetic output7.

## Reduction and integrity

Verified ZIP digests remain in receipt.json: macOS artifact13611003967
`009d61c7344f36f357e00f9786439ecaad5b7bbeb250ba012fbb7858137f33e2`;
Ubuntu13610743078 `c84cb9c2cecba3ab014c0b287091d16bc8a28dec27ebda129026c582abc25b17`;
native13610104871 `b5fec454e42d3fa138b8cc5863204325004e13e0314b65dd6d11c06f9e89785d`.
Original ZIP/per-file checksum verification preceded reduction. The prior
representation is pinned at full source381c0ae0 with every published file hash.
Original/published hashes and normalization rules remain identified.

Repeated110-file inventories,51-file translations and build/toolchain metadata
were compared to exact committed source before replacing them with source paths,
counts and canonical JSON digests. Negative-control messages, per-host worker
outcomes, native/guest SQL values and cleanup states are retained as structured
results. Raw console logs and full API payloads are omitted under
[compact CI receipt policy](../../development.md#compact-ci-receipts); they are
not hidden in a compressed blob. The acceptance facts survive artifact expiry.

Earlier42448601842 stays at fd615a53; experimental42437059943 stays at
host6134274a / C origin b1a265cc. No receipt is relabelled. Receipt/ledger/status
and GitHub display updates retain runtime, guest, adapter, workflow and test-body
equality with b04b49db; current protected-PR checks still apply. No new performance
run, stable P4/RSS/Ubuntu-speedup claim, actual dynamic XML-loader coverage,
Qualification or release is introduced.
