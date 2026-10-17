# mariamem v0.5.2 — Snapshot ownership without repeated content scans

This release reduces Snapshot creation work by fixing the same private backing
after MariaDB and its workers stop. It avoids reconstructing the ordinary heap
baseline and repeatedly reading all of its file contents. Public Go and Python
API signatures are unchanged from v0.5.1.

## Snapshot behavior

Capture is bound to its source before execution. Acquisition checks source and
guest identity, completion, inventory, layout and seal state. Normal APIs cannot
modify the fixed baseline. Fork children have independent mutable state and
lifetimes; child writes cannot change the parent or siblings. Successful Snapshot
still consumes its source, and an already started child survives baseline Close.

## Integrity boundary

Ordinary heap acquisition no longer performs a full content scan to detect
faults that directly alter private memory bytes between freezing and acquisition.
It enforces ownership and immutability and checks identity, state and structure
instead. A fault previously rejected during Snapshot creation may surface later
when a child reads the affected data, or may not be detected at this boundary.
This change concerns internal memory faults; normal API isolation is preserved.

Strict digest-bearing Heap imports and private cross-host transfers retain their
content checks. Borrowed file mappings are copied into owned memory, checked
against their source contents and detached from the source instance's lifetime.
There is no new public save/load API. See the
[ownership contract](../docs/decisions/snapshot-product-contract.md) and
[changes since v0.5.1](../docs/changes-since-v051.md).

## Validation and distribution

Before version preparation, exact source
`a390b6e496b5fa1d272dc46a9aecffe6129fcec4` passed independent guest builds,
Generated Go reproduction, both native platforms' runtime and external consumer
acceptance, and aggregate READY in
[Qualification run 39006279807](https://github.com/masahitojp/mariamem/actions/runs/39006279807).
That evidence is not relabelled as the final v0.5.2 source. Release CI must accept
the exact versioned source and its artifacts before publication.

MariaDB remains 12.3.3. Guest/converter inputs, public API signatures, supported
platforms and minimum Go version are unchanged. Supported platforms remain
macOS 15+ arm64 and Ubuntu 24.04 x86_64. Assets remain host-only Python wheels,
common corresponding source, provenance and SHA256SUMS. This release does not
publish to PyPI.
