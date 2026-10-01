# Generated-Go integration FD gate and selected local candidate

All Go templates are isolated from ordinary package discovery. The normal
runtime is unchanged. No command below enables a default runtime or publishes
an artifact. The release source/build pipeline and both-platform acceptance
remain pending.

## Deterministic FD regression

The original gate failed at `023796b9e357ff2dfae9894c3b4e52d75c39db20`:
`replacement` was read instead of `original`. The same rename/name-reuse sequence
now runs after pinning the opened directory object and must PASS. A gate assertion
ensures the test actually performs the rename. No guest addresses, scheduler
assumptions or MariaDB symbols are used.

```sh
python3 benchmarks/spikes/generated-go-integration/setup_audit.py \
  --source-module benchmarks/results/wasm2go-execution/import-patched \
  --output build/generated-go-fd-audit
cd build/generated-go-fd-audit
GOTOOLCHAIN=go1.26.8 go test -race -v ./generated/base
GOTOOLCHAIN=go1.26.8 go test -v . -run TestReadlinkRegularAndMissing
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o audit-probe .
```

The installer validates the entire accepted Go/assembly inventory, then applies
exact, fail-closed source adaptations automatically. The diagnostic driver keeps
I/O tracing for debugging; do not benchmark it or distribute it.

## Selected production-like measurement boundary

```sh
python3 benchmarks/spikes/generated-go-integration/setup_candidate.py \
  --source-module benchmarks/results/wasm2go-execution/import-patched \
  --guest build/wasm2go-legacy-eh/artifact/mariamem-legacy-eh-O2-compatible.wasm \
  --output build/generated-go-selected-candidate
GOTOOLCHAIN=go1.26.8 MARIAMEM_NATIVE_DIR=build/generated-go-selected-candidate/native \
  python3 scripts/verify.py integration
GOTOOLCHAIN=go1.26.8 python3 benchmarks/v04_candidate.py \
  --native-dir build/generated-go-selected-candidate/native \
  --json benchmarks/results/v04-selected-candidate.json
GOTOOLCHAIN=go1.26.8 build/sqlalchemy-dogfood/py314/bin/python benchmarks/v04_orm.py \
  --native-dir build/generated-go-selected-candidate/native \
  --json benchmarks/results/v04-selected-orm.json
```

This separately named bundle contains the real compiled generated-Go executable,
not a shell adapter or Wasmer. Its historical `wasmer-headless` filename permits
selection with the unchanged public resolver. The manifest labels it
`runtime_kind=generated-go`, `public_release_ready=false`; this is an unpublished
local layout, not the decided v0.4 distribution format.

The candidate checks that the supplied module hash equals the compiled guest's
pinned input hash before entering guest code. Existing wrapper/host artifact and
Snapshot checks still run. Prepared files are independently opened, privately
mapped (`MAP_PRIVATE`), and attached to new MemFS nodes; no heap, FD, offset,
thread, TLS or waiter state is cloned. Mappings are released after normal guest
shutdown, all worker joins and snapshot export. Fatal process termination relies
on OS resource reclamation. Diagnostic I/O overrides are removed from this driver.

`provenance.json` records source SHA, pinned guest/converter, template and generated
source/assembly inventory and final bundle checksums. Rebuilding the original
WASM from canonical MariaDB source and rebuilding the converter from its pinned
source/patches remain the release pipeline's responsibility. For replaying those
experimental inputs see [the accepted wasm2go recipe](../wasm2go/README.md#legacy-eh-generated-go-execution).
The correctly patched executable is `wasm2go-import-shim` (both imported-memory
and function-index fixes), not the earlier `wasm2go-memory-shim` alone. A fresh
translation reproduced all 48 converter output files byte-for-byte during this
FD follow-up; separate wait/join helper and primitive tests are inventory checked.

## Contract and limits

Directory FDs retain a MemFS node identity. Relative lookup/open, stat and
readlink operate from that node; no pathname search/retry is used. A single FS
lock covers component traversal and opening. Parent identity follows rename;
unlinked objects remain alive while referenced. Creation in an unlinked directory
fails. FD close and dup/reuse operate on the same descriptor table, including
preopen FD3. Path strings are only diagnostic/access-hook labels.

Tests cover deterministic and concurrent rename, pathname reuse, nested relative
open, parent traversal, unlink of files/directories, stat/readlink, invalid FDs,
close/dup/reuse and preopen close/rebinding. Private-file tests cover base/child
isolation, growth, rename, one child's mapping close and partial setup failure.
After a failed mapping setup its incomplete filesystem tree must be discarded.

This fixes the demonstrated identity loss, not the complete WASIX filesystem
surface: unneeded non-root directory mutation paths, full rights/capability
resolution, symlinks, signals and abnormal thread lifecycle still need release
hardening. Unsupported filesystem directory binding returns ENOTSUP, never a
path fallback. MemFS currently has no symlink nodes. SetFS is initialization-only,
before guest execution. The legal InnoDB condition-variable timeout race is
unchanged. Do not infer production readiness from these local gates or numbers.
