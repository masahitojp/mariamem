# v0.5.0 A–D — MariaDB 12.3.3 integration

Status: implementation and local verification in progress. This task does not
qualify v0.5.0 for release. No tag, publication or merge into main is authorized.

## Baseline and adopted work

Main starts at `098b0144ed50835da792ba811d11e0a1c8b000b2`.
The v0.4.7 tag object is `c201bf577440440253155e665def9c25ac5064f0` and its
source commit is `e0be06f3a20c72cbb5a9be27971280c80a3ec357`. Main differs only
by the approved guest patch policy and its documentation navigation.
[Preflight](v050-ad-integration-evidence/preflight.json) preserves the old guest,
converter, toolchain and canonical build records. The original checkout was
clean, with no other worktrees or running Docker containers. Other sessions'
processes and unrelated Docker images were left alone.

Only needed source/recipe/portability inputs were extracted from
`5f14221463b6400e72e72a115bd1cc1a3acee88d`; the tested common layout comes from
`06ad7abf8c38248ceff0b0105af02c010f51f4fc`. Handshake and ORM assertions were
cherry-picked from `920c5bdaf14ae3a6126aeb2a79a36f5382cccda5` and
`fc6f4ad88f2a1622ed138a98c18a7cd250c1b69d`. No experiment branch was merged.
Historical [12.3.3 feasibility](https://github.com/masahitojp/mariamem/blob/5f14221463b6400e72e72a115bd1cc1a3acee88d/docs/reviews/v05-stable-guest-feasibility.md)
used the old converter plus seven patches. Its runtime results do not qualify
this upstream-converter combination. Historical LTS wording is not an input
assumption for this adoption: the selected input is exactly MariaDB 12.3.3.

## Fixed source and patch ownership

[guest/input.json](../../guest/input.json) selects one official MariaDB archive
by source commit and SHA256 and the pinned lite4 recipe by commit and SHA256.
[inputs.lock.json](../../release/inputs.lock.json) owns acquisition URLs/hashes.
Only six checksum-bound recipe/API files are copied from lite4. Connector/C,
wolfSSL, PCRE2 and fmt retain their v0.4.7 pins.

Application order is common portability → 12.3.3 redo variant → canonical
`guest/source.patch` → the existing wire/init/auth/dependency preparation.
The descriptor records ordered patch digests and every portability preimage
(including required absence for newly added files) and postimage. Preparation
rejects unregistered/mismatched input, changed recipe bytes, changed patch bytes,
wrong preimages, failed application and wrong postimages. GNU patch uses batch,
forward and fuzz=0. Existing experimental overlays remain separate and are
rejected by release provenance. Release checks validate the current descriptor
and complete ordered series against the actual build receipt. All inputs and
patches remain in the corresponding-source publication set.

[The repeated source comparison](v050-ad-integration-evidence/patch-comparison.json)
confirms that the adopted output differs from the old 12.3.3 patch only in one
version-specific comment, with no code delta.
The historical 15 versus 17 figures count different things, not inconsistent
runtime fixes. Fifteen file diffs are byte-identical between the two original
18-file experimental patches. `configure.cmake` differs in line positions and
`my_virtual_mem.c` in comments. The tested normalized common layout applies
those two too, giving 17 common files and one redo file with version-dependent
control-flow context. This adoption ships two portability patch files, not
18 patches; it ships only the 12.3.3 variant. The canonical overlay's malformed
context/counts formerly required fuzz in one hunk; it was regenerated against
the same input and produces identical output, now without fuzz.
The approved [inventory and constraints](../decisions/guest-patch-management.md)
remain the ownership reference rather than another duplicated 18-row table.

VM decommit remains accounting-only, nonnull recommit does not promise zero-fill,
protection and file locks remain no-ops, independent DB backing remains required,
and directory fsync adapts WASIX's EISDIR behavior. These are inherited limits,
not newly established native MariaDB durability/protection guarantees. No VM,
filesystem or worker-stop redesign is included.

The official MariaDB GPL and zlib notice bytes match existing distributed notices;
[notice hashes](v050-ad-integration-evidence/source-notices.json) record the check.
Source-notice verification now uses the adopted official MariaDB archive for
those notices; the lite4 archive remains corresponding recipe/patch source.
Historical linked-symbol attribution is preserved, and new guest attribution
must be recorded independently rather than claiming unchanged generated bodies.

## Build and generation route

[generated-go-toolchain.json](../../release/generated-go-toolchain.json) remains
unchanged: wasixcc 0.4.7, LLVM 23.1.0, Binaryen version_133, WASIX sysroot
v2026-07-03.1 legacy EH and EH-PIC, Go 1.26.8. It fixes each tool archive URL
and hash. The legacy noncanonical fields in inputs.lock.json do not select the
Generated-Go compiler; the canonical toolchain manifest does.

The fresh Linux arm64 root builder runs `scripts/build_generated_guest.py`
with empty `/work` and SDK and two independent source preparations/builds.
The existing legacy-EH shell fixes build paths/options, JOBS=3 and Binaryen -O2
feature flags. Arm64 Linux is a guest build host, not an added product platform.
The expected adoption Wasm hash is the prior measured
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`;
canonical builds must confirm it before this report claims completion.

Native generation runs the existing `translate_guest.py` → memory32 fixture →
`setup_candidate.py --source-only` → `generate_runtime.py` chain. The converter
is goccy/wasm2go `730057c146463f663e8774587bc96fb2bea91af8`, with unchanged
ordered patches: imported-memory, import-function-index, relaxed-madd,
pure-memory32, controlled-thread-traps, host-logical-memory, linear-memory-owner,
helper-bridge, export-collision. No shibukawa fork, new converter fix or update.
The raw translation and adapted-input inventories are accepted explicitly;
`regenerate_release_guest.py` then independently repeats the chain and compares
every generated and handwritten integration byte. Provenance is produced by the
installer, not refreshed to excuse manual edits of generated output.

## Handshake and Snapshot contract

The existing handshake change reads `SELECT CONNECTION_ID(), VERSION()` from
the newly opened guest session, validates one row/two nonnull values, decodes
hex and rejects empty or NUL-containing versions. It sends VERSION() bytes
verbatim: no suffix removal, compatibility prefix or alternate profile. The
`-MariaDB-embedded` suffix originates in MariaDB's embedded build. Capabilities,
authentication, connection ID, cleanup and public APIs keep their existing paths.
A failed identity query aborts the connection; no old-version fallback exists.
SQLAlchemy/GORM tests assert MariaDB dialect/version recognition using the
actual SQL value and normal driver paths.

Snapshot format is unchanged. Guest identity changes, so persisted Snapshots
created with the old 13.1.0 guest must be recreated from SQL/fixtures using
12.3.3. Existing Snapshot acquisition/Fork checks remain fail-closed. An actual
old-runtime saved Snapshot is used to verify rejection; no guard is relaxed.

## Verification and follow-up

Results and exact build/generated/host identities will be completed after the
commands finish. Fast Feedback currently passes 86 focused helper/dev/release
contract cases. Local native runtime scope is macOS 27.0.1 arm64 (within macOS15+ support); Ubuntu24.04 x86_64
is SKIP because no native x86_64 product runner is available in this task.
Emulated/arm64 guest builds cannot count as native Ubuntu product PASS.

Follow-up E/F must assess Fd_allocate, 8/16-bit atomic loads, zero-length bulk
memory, shared-memory race semantics and observation limits on this final guest
and unchanged nine-patch converter. They must repeat final native qualification,
consumer/artifact/source guards and product/resource validation. A zero race
report in focused checks is not proof of full-guest race correctness.
No full release qualification, product benchmark, VFS/Snapshot optimization,
platform/Go minimum/API change or unrelated dependency update is included.
