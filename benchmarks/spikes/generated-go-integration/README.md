# Generated-Go integration compatibility gate

This is the deterministic FD audit that stopped candidate integration. It is
isolated from normal Go package/build discovery. No template is imported by the
product. It does not build or authenticate a distributable runtime.

Use the accepted generated module from the wasm2go spike, after the imported
memory and function-index converter patches. Its generated base checksum is
verified by the installer. There are no manual edits:

```sh
python3 benchmarks/spikes/generated-go-integration/setup_audit.py \
  --source-module benchmarks/results/wasm2go-execution/import-patched \
  --output build/generated-go-fd-audit
cd build/generated-go-fd-audit
GOTOOLCHAIN=go1.26.8 go test -v . -run TestReadlinkRegularAndMissing
GOTOOLCHAIN=go1.26.8 go test -race -v ./generated/base \
  -run TestRelativeDirectoryIdentityDuringRename
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o audit-probe .
```

Expected results: readlink PASS; directory identity FAIL (`replacement` rather
than `original`). The test gates a rename after descriptor-to-path resolution
and before open. It calls the actual relative-FD adapter. It uses no guest
addresses, scheduler timing assumptions or MariaDB internal symbols.

The driver includes the two diagnostic compatibility fixes (readlink error
mapping and relative directory FD support), I/O tracing, and a cold file-transfer
adapter for testing existing Snapshot/Fork workloads. It uses fresh guest memory
and fresh execution state. It does not implement memory-image CoW or reentry.

The transfer adapter intentionally remains a preflight tool. It does not bind
its compiled guest to the supplied module argument, enforce the complete WASI
rights/path-resolution contract, or implement production prepared-file mappings.
Do not package it as `wasmer-headless`, publish it, or treat its passing ORM
cases as proof of production trust, failure hardening or platform acceptance.

The relative adapter resolves a directory object to a pathname and later opens
that pathname. Even tracking object identity during resolution does not preserve
it across concurrent rename/path reuse. Production needs an atomic,
descriptor-anchored resolver and file-operation contract. Retrying by pathname,
suppressing errors, or hiding this failing test is not an acceptable remedy.
