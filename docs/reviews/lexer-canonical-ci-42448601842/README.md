# Canonical lexer source inputs:42448601842

Source_commit `fd615a53495b615ca2fec6007006f4a24f98d902`.
[CI](https://github.com/masahitojp/mariamem/actions/runs/42448601842) completed
successfully. Independent clean builder jobs128632763844 and128632763727,
native reference128632763882 and comparison128634390912 all succeeded.

The two separately built canonical-source guests both reproduce:

- guest `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`
- linked `69dbde341c47149463d57b9f6cd4d2683506e7936dc756a4793f5425b788a722`

`artifacts-verified.json` pins artifact IDs/ZIP digests, including the two guest
ZIPs. Every downloaded ZIP was hashed before safe extraction. The reduced guest
records retain original record hashes; only the repeated full tracked-source
inventories were replaced by a canonical digest and reconstruction instruction.
`source-proof.json` independently compares both original inventories to all
actual Git blobs at the recorded commit. The compiler/toolchain, source prep,
lexer provenance and build repetitions remain in the reduced records.

`comparison.json` is the original CI output. `reference-native.json` includes
normal SQL and COM_STMT_PREPARE/EXECUTE with Unicode/NUL/quotes/backslash and
numeric parameters. This is native reference evidence; canonical installed
both-host SQL acceptance is still pending.

For local canonical authoring, raw translation from original C origin b1a265cc,
CI42433100335, was reused only after proving the new source builds have identical
linked/optimized guest bytes. All51 raw file hashes matched its fixed receipt.
`installation-continuity.json` compares resulting installed files to actual-guest
CI42437059943: runtime code unchanged, with only test/provenance differences.
Final candidate CI must regenerate independently on both supported platforms.

Development42450789310 succeeded at `cee04983`; the preceding failed
Development42448605095 caught a push-trigger policy violation, fixed by making
the input workflow manual. The above successful input run keeps its original
fd615a53 identity. It is not relabelled as the subsequent canonical runtime
candidate, Qualification, performance measurement, main integration or release.
