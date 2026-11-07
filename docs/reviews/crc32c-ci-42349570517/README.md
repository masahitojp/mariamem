# CRC32C runtime acceptance receipt

[Run42349570517](https://github.com/masahitojp/mariamem/actions/runs/42349570517)
passed at source_commit `bb894d6658cd575f8262736698d3e9ede7f67360`.

| Job | Job ID | Artifact ID | Result |
|---|---:|---:|---|
|Runtime qualification — darwin-arm64|128334615017|13564909844|PASS|
|Runtime qualification — ubuntu24.04-x86_64|128334614729|13566030300|PASS|

Original artifact ZIP SHA256:

- macOS: `d349bc70694cedbc5f87a63eb61149a6a5a8f94a59d478ecbd07d405739149a2`
- Ubuntu: `f626ca3e4347a565add143b47b1ffb17d365b86a020bc736e8e9171258ab3367`

`receipt.json` is a compact derived assessment: it records full identities,
observed platforms/toolchain and the original artifact file hashes. The six
platform command/correctness/cleanup JSON files are byte-for-byte originals.
All original ZIP/file checksums, input source and CRC inventory bindings were
verified before reduction. Full logs/source inventories remain in the named
GitHub artifacts; this directory does not claim to contain those full archives.
`SHA256SUMS.json` covers the retained files.

Both platforms ran full `verify.py check` and `verify.py integration` with exit0,
including the generated CRC tests and real SQL/isolation/lifecycle controls.
The prepared-consumer checks retain the existing named exceptions; this is not
unrestricted Connector compatibility. Scratch cleanup completed on both hosts.
This is runtime correctness evidence, not a performance campaign or release.

Changes after measured source `1057adf8fb430f5540f9d4f420f6b3f6f2012aa9`
are the qualification workflow dependency addition and its contract test, plus
records. `internal/`, `guest/`, `release/` and `scripts/` are identical (empty
Git diff); runtime bytes are unchanged. CI evidence remains bound to
`bb894d6658cd575f8262736698d3e9ede7f67360`; later record-only commits reuse it
on that explicit basis, not as a new exact-head execution.
