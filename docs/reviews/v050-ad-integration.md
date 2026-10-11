# v0.5.0 A–D — MariaDB 12.3.3 integration

Status: **A–D COMPLETE**. Integration and the requested local verification pass.
This is **not v0.5.0 RELEASE READY**. No tag, publication or merge into main is authorized.

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
The adoption Wasm hash equals the prior measured
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`;
Both formal independent builds confirmed it. The raw linked Wasm hash is
`3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba`.

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

## Recorded identities and reproduction

The actual guest-build origin is
`9dd38e03495ab0b87d2e8d62328bc5d8bf84fc64`, the committed recipe before
canonical output adoption. [guest.json](v050-ad-integration-evidence/guest.json)
records both matching builds; [regeneration.json](v050-ad-integration-evidence/regeneration.json)
records the independent full Go inventory match. Receipts retain their real
origin; they are not relabeled as the final report/consumer commit. The historical
canonical-build hash in guest.json describes its value at build time. Exact
final-commit qualification remains a later release gate.
[Identities](v050-ad-integration-evidence/identities.json) bind patch bytes,
translation, adapted input, canonical build and generated provenance. All 14
handwritten generation ownership files remain byte-identical to v0.4.7.

Use Go 1.26.8 and task-owned GOCACHE/GOPATH/GOMODCACHE. Retained reproduction
commands assume an empty task temp tree:

1. Run [guest-command.sh](v050-ad-integration-evidence/guest-command.sh) from
   the committed checkout: the default formal build route prepares/builds twice.
2. [native-command.py](v050-ad-integration-evidence/native-command.py) records
   the explicit adoption chain. Its partial-adoption diagnostic flag does not
   establish completion. After both builds, repeat with
   `scripts/regenerate_release_guest.py --guest-dir ../temp/builder-build/generated-release --output ../temp/independent-regeneration`.
3. Run `scripts/verify_generated_runtime.py` and
   [source-guard-command.py](v050-ad-integration-evidence/source-guard-command.py):
   actual provenance, negative cases and independent offline source preparation.
4. Use a clean independent clone with a `.git` directory for source stamping;
   run `scripts/build_alpha.py --ci-candidate`, then
   [consumer-command.py](v050-ad-integration-evidence/consumer-command.py), passing
   the absolute task workspace as its argument. The private proxy/wheel retain
   the unchanged 0.4.7 package label; they do not replace public artifacts.

The pinned Go VCS scanner can miss `.git`-file worktrees. A nested checkout
reported parent main SHA; an external worktree omitted VCS stamping. The existing
binary identity guard rejected both wheel attempts. A separate clone at
`83a6ede966db7f1bbc3a827ca58f5581c0f5dd7c` produced the clean exact-SHA host/wheel
and fresh linked-library attribution. Earlier host-metadata attribution is
superseded. Functional tests ran the new generated source, but alone do not
prove stamping. The [attribution ledger](../../release/generated-license-evidence.json)
records the actual audited clone SHA and host build information.

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

The evidence directory retains commands, exact inventories, normalized result
copies and original/saved SHA256 values in
[evidence-hashes.json](v050-ad-integration-evidence/evidence-hashes.json).
Path normalization is explicit; a normalized record is not claimed to retain the
original file digest. No mandatory local A–D check remains failing.

| Verification | Result | Evidence / scope |
| --- | --- | --- |
| Formal source preparation and guest build | PASS | [Two-build receipt](v050-ad-integration-evidence/guest.json), [phase events](v050-ad-integration-evidence/guest-phases.jsonl); identical linked and optimized hashes |
| Patch rejection and helper Fast Feedback | PASS | [Initial 86 cases](v050-ad-integration-evidence/fast-feedback.txt), [10 patch cases](v050-ad-integration-evidence/patch-management-tests.txt), then full ordinary check |
| Independent Wasm→Go regeneration | PASS | [Receipt](v050-ad-integration-evidence/regeneration.json), [log](v050-ad-integration-evidence/independent-regeneration.txt); all 62 installed runtime files identical |
| Existing memory32 semantics fixture | PASS | Independent regeneration log: 2,472 cases, 1,693 expected guest traps; host survives |
| Canonical source, compile, vet, Python/tools | PASS | [verify.py check](v050-ad-integration-evidence/canonical-check.txt): 16 source-owner cases; Go test/vet; 585 Python cases, 18 subtests. Its 34 opt-in SKIPs are not runtime acceptance claims |
| Build/source/provenance guard cases | PASS | [Source guards](v050-ad-integration-evidence/source-guards.json); real origin accepted, wrong origin/contract/one-build/experimental overlay rejected; fresh offline source preparation identical |
| Exact host/wheel source identity | PASS | [Private wheel](v050-ad-integration-evidence/private-wheel.json): clean clone SHA `83a6ede966db7f1bbc3a827ca58f5581c0f5dd7c`; unchanged binary guard passed |
| Source notices and retained-library attribution | PASS | [Notice check](v050-ad-integration-evidence/source-notices.json), current [ledger](../../release/generated-license-evidence.json); positive generated/native definitions for all 12 groups; 5 related source/license mirror tests rerun after final attribution update |
| SQL/transaction, isolation, Snapshot/Fork/LoadSnapshot, Start/Close/cleanup | PASS | [Go integration/default/OOB suites](v050-ad-integration-evidence/native-go-integration.txt); [28 Python cases on exact-SHA host](v050-ad-integration-evidence/native-python-exact-source.txt); [49 Snapshot scenario checks](v050-ad-integration-evidence/snapshot-scenarios.json) |
| Focused handwritten/runtime race checks | PASS | [Existing six-package command](v050-ad-integration-evidence/focused-race.txt); not a full shared-memory race census or proof |
| Handshake/version semantics and failure rejection | PASS | [Exact SQL/wire equality](v050-ad-integration-evidence/handshake-identity.json), [unit test](v050-ad-integration-evidence/handshake-unit.txt); `12.3.3-MariaDB-embedded`, connection ID equals thread ID |
| Actual old saved Snapshot rejection | PASS | [Exact-SHA host rejection](v050-ad-integration-evidence/old-snapshot-rejection-exact-source.json), [old snapshot inventory](v050-ad-integration-evidence/old-snapshot.json); `Snapshot WASM build mismatch` |
| External Go and installed Python consumer | PASS | [Consumer report](v050-ad-integration-evidence/consumer-results.json), [log](v050-ad-integration-evidence/consumers.txt); private proxy resolves exact module files without replace; installed wheel bytes verified; Python smoke 2 cases |
| GORM / SQLAlchemy bounded dogfood | PASS | Consumer report/log plus `gorm-0..3.json` / `sqlalchemy-0..3.json` in evidence: 32 / 44 cases; start, fork, fork, start; normal driver options and version/dialect assertions |
| Ubuntu24.04 x86_64 native runtime | SKIP | No native x86_64 product runner available. Arm64 guest-builder Linux does not substitute for this platform |
| Minimum macOS15 environment / other supported Go-version matrix | SKIP | Local runtime is macOS27.0.1 arm64, Go1.26.8; deployment/minimum binary check passes, but other environments were not executed |
| Full Release Qualification and Product Validation | SKIP | Explicitly outside A–D; exact final commit qualification and product/resource comparison remain E/F/human work |

A first guest build emitted GNU make clock-skew warnings. Both independent
artifact hashes matched. The unchanged converter still emits SSA iteration-cap
warnings and leaves f16 rewriting disabled; no new correctness fix was bundled.
These observations do not replace broader semantic qualification. Recovered
harness/environment errors are recorded in
[recovered-events.json](v050-ad-integration-evidence/recovered-events.json),
including the historical provenance fixture and VCS stamping failures.
The historical WASM/AOT source ledger is retained as historical evidence; it does
not certify the new guest. The canonical build/ordered-input and current license
ledgers own this adoption.

There is **no remaining A–D blocker**. Persisted old guest Snapshots must be
recreated; no migration or identity bypass is provided. Main remains the
unchanged product baseline; this task creates only a pushed work branch.

Follow-up E/F must assess Fd_allocate, 8/16-bit atomic loads, zero-length bulk
memory, shared-memory race semantics and observation limits on this final guest
and unchanged nine-patch converter. They must repeat final native qualification,
consumer/artifact/source guards and product/resource validation. A zero race
report in focused checks is not proof of full-guest race correctness.
No full release qualification, product benchmark, VFS/Snapshot optimization,
platform/Go minimum/API change or unrelated dependency update is included.

E/F should focus their final comparison on `guest/input.json`, the two portability
patches and canonical overlay; `prepare_guest.py` / `guest_input.py` / canonical
build receipts; new Generated Go bodies and guest identity; mysqlwire's private
identity decoder/query; source/license evidence and actual consumer artifacts.
No converter patch bytes or public API changed. This local two-build / independent
regeneration proof does not authorize a final-commit READY status or publication.
