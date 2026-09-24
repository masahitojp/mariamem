# Wasmer runtime notices (Task 9b)

**Incomplete: `runtime_notices=false`. Do not publish the native candidate yet.**
The remaining missing notice is the MIT copyright/license text for **webc 12.0.1**.
The collected inventory is evidence of progress, not an approval of completeness.
`guest_source=true` and `platform_acceptance=false` are unchanged.

## Runtime and dependency selection

`release/wasmer-runtime-notices.json` binds the inventory to the pinned Wasmer
7.4.2 darwin-arm64 archive, full-source archive, Cargo.lock, build workflow,
Makefile and CLI manifest. The actual staged `wasmer-headless` matches the
archive member SHA256:

`ebbedfd8c43d866440b960a7b5f773b7b6932a563b6f61d043bc0c21ed535899`

The release workflow calls `make build-wasmer-headless-minimal`. For macOS arm64,
the Makefile selects `wasmer-cli`, binary `wasmer-headless`, target
`aarch64-apple-darwin`, no default features, and
`sys,headless-minimal,singlepass`. Cargo 1.95 resolves the unchanged lock with
these flags. No runtime compilation or dependency upgrade was performed.

The inventory contains **509 unique name/version identities**:

- **426** normal dependencies when proc-macro edges are excluded.
- **83** additional proc-macro dependencies, collected conservatively for
  generated-code notice coverage; these are not asserted to be linked objects.

This is the build-input dependency graph, a conservative superset of code that
survives LTO. It is not the entire workspace lock (813 packages), a build-tool
inventory, or a claim that every function is linked. The binary contains 196
crate/version source-path references. These are supporting evidence, not a
complete dependency detector. Rust's standard library explains references such
as rustc-demangle 0.1.27 and hashbrown 0.16.1 outside the normal runtime graph.
The embedded rustc commit `59807616e1fa2540724bfbac14d7976d7e4a3860` matches Rust
1.95.0; its official `COPYRIGHT-library.html` is included, covering the standard
library separately from Cargo's Wasmer graph.

Each package records name, version, source, repository, original license expression
(or original `license-file`), authors, source archive checksum, manifest checksum,
notice provenance, and bundled notice hashes/byte ranges. Registry checksums come
from the pinned Cargo.lock, not an unversioned registry query.

## Collected terms and attribution

`licenses/Wasmer-Rust-NOTICES.txt` contains source URLs/hashes and unmodified
license/notice bodies. MIT/Apache dual expressions and AND/WITH expressions
remain intact; they are not rewritten to a single license. Collection preserves
nested upstream license files, including aws-lc and other bundled native code.
MPL packages also identify the exact unmodified source archive and checksum.

Where crate archives omit license files, fixed upstream sources provide them:
Cynic, dynasm, wild, symbolic and WAI. Their input URLs and hashes are recorded.
WAI parser's recorded VCS commit was unavailable, but the v0.2.3 source tag's six
parser Rust source files match the crate; its root Apache license is retained.
For crc-catalog and yaml-edit, the full pinned upstream archives also contain no
separate legal document. Their declared Apache-2.0 terms are supplied using the
standard Apache text (crc-catalog's Apache option), with original metadata and
authors retained; this is explicitly distinguished from an upstream license file.

Separate conspicuous copies are included:

- `licenses/Wasmer-ATTRIBUTIONS.txt`: exact attribution file from the runtime archive.
- `licenses/Wasmer-Singlepass-BUSL-1.1.txt`: exact Singlepass license from Wasmer source.

**The whole runtime is not MIT.** The selected Singlepass 7.4.2 component uses
Business Source License 1.1, with non-production use rights, a conditional
production-use grant tied to Wasmer sponsorship, and a future MPL-2.0 change
license/date. The full parameters control; merely shipping the text does not
remove its restrictions. The binary includes Singlepass source-path references.
The project's GPL-2.0-only license does not relicense this separate runtime.
Public distribution documentation must preserve this disclosure and must not
promise unrestricted runtime use.

Existing native packaging copies all flat `licenses/` files and `NOTICE`, so these
texts enter newly generated candidates without changing runtime binary bytes.
Previously generated bundles remain stale until regenerated. No release approval,
publication or platform acceptance is performed by these scripts.

## Recheck recorded coverage

Offline committed-file validation (Python 3.9+):

```sh
python3 scripts/runtime_notices.py
python3 -m unittest discover -s tests -p 'test_runtime_notices.py'
```

Recheck upstream archive checksums, crate manifests/version/license metadata,
Cargo.lock identities, and regenerate notice bytes in memory (Python 3.11+):

```sh
python3.11 scripts/runtime_notices.py --verify-inputs
# Optional explicit downloads of missing, checksum-pinned inputs:
python3.11 scripts/runtime_notices.py --verify-inputs --fetch
# Also check a staged native binary:
python3.11 scripts/runtime_notices.py --native-dir python/mariamem/_native
```

`verified=true` means the recorded collection is internally consistent. The
output independently reports `complete=false` and the missing packages. Review
approval while notices are missing is rejected. These commands do not set review
flags. No full offline build, Cargo vendor, or bit-for-bit rebuild is required.

To repeat Cargo selection, unpack the pinned `wasmer-full-source.tar.gz` under
`build/runtime-notices/` and use Cargo/rustc 1.95 on macOS arm64 (in PATH):

```sh
export CARGO_HOME="$PWD/build/runtime-notices/cargo-home"
cargo metadata --manifest-path build/runtime-notices/wasmer/lib/cli/Cargo.toml \
  --format-version 1 --filter-platform aarch64-apple-darwin \
  --no-default-features --features sys,headless-minimal,singlepass --locked \
  > build/runtime-notices/metadata.json
cargo tree --manifest-path build/runtime-notices/wasmer/lib/cli/Cargo.toml \
  --target aarch64-apple-darwin --no-default-features \
  --features sys,headless-minimal,singlepass --locked -p wasmer-cli \
  -e normal --prefix none --format '{p}' > build/runtime-notices/tree.txt
cargo tree --manifest-path build/runtime-notices/wasmer/lib/cli/Cargo.toml \
  --target aarch64-apple-darwin --no-default-features \
  --features sys,headless-minimal,singlepass --locked -p wasmer-cli \
  -e normal,no-proc-macro --prefix none --format '{p}' \
  > build/runtime-notices/runtime-tree.txt
python3.11 scripts/runtime_notices.py --cargo-tree build/runtime-notices/tree.txt
# After --verify-inputs --fetch has populated supplemental input archives:
python3.11 scripts/collect_runtime_notices.py
python3.11 scripts/runtime_notices.py --verify-inputs
```

The collector uses the committed input pins, the prepared metadata/tree, and
Cargo's downloaded registry cache. Generated metadata/build files stay in ignored
`build/`; they are not published as source or treated as linked dependencies.
Generation never changes the release review and always starts as incomplete.

## Exact outstanding work

`webc 12.0.1` declares MIT and lists the Wasmer Engineering Team as authors, but
contains no license/copyright text. Its recorded repository is
`https://github.com/wasmerio/pirita`, VCS commit
`b447309d10535d24220190094e5747ebdc66097a`. That exact source archive and version
12.0.1/v12.0.1 tag URLs returned HTTP 404. A guessed copyright line or the
unrelated Wasmer workspace MIT file is not substituted.

Obtain the correct version's license/copyright notice (and any additional
attributions) from its publisher or an authoritative matching source archive;
pin its provenance/hash, collect it, and rerun verification. Then review the
complete collection, including the Singlepass disclosure, before setting
`runtime_notices=true`. Platform acceptance remains a separate next task.
