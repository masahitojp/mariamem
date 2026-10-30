# Routine canonical adoption candidate

The approved procedures/functions + bounded DEFINER scope is implemented in a
minimal canonical candidate. **Continue to both-OS candidate CI; do not merge or
release yet.** Local macOS arm64 checks, independent Go regeneration and existing
ORM consumers pass. The strongest remaining objection is that this is a new
canonical guest: the earlier experimental both-OS PASS does not qualify these
new bytes. This candidate must independently rebuild the exact guest twice and
pass both native targets before a new Human adoption review.

Target version, main integration, final Qualification and publication remain
separate decisions. Binary prepared production adoption is a separate open task;
none of its prototype limits is implicitly approved here.

## Scope and lineage

- Baseline: `de0e08a9c4248969a7522abebfdee8aea6ef9657` (root main left unchanged).
  Remote main `61c5d12c13c3cc7fc97c4a88d2f893054c06f589` differed only in the local
  planning documents; runtime/guest/release owners matched before this work.
- Selected experimental source: `experiment/routine-bootstrap@9250ff5`, whose
  [preceding both-OS receipt](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-routine-adoption-bounds-ci.md)
  covers `387a5f2a685748877d17e706491738ae242c0c4b`, not this candidate.
  Experimental history and raw binary/compressed evidence were not merged.
- Authored canonical source: `587f7d162cf4361f7ede78de3d0438ff7a7aecaa`.
  Canonical generated checkpoint: `e4c483257b9388909a53ea8797299eb5fda25c85`.
  CI/attribution/guide checkpoint: `9cf8cdc` (later report/evidence changes only).
- Scope: [Human decision](../decisions/routine-support-scope.md), including the
  [product-managed proc structure](../decisions/snapshot-product-contract.md).
  Fresh initializes before ready; incompatible restored structure fails closed
  without repair. Routine rows remain independently mutable child data.

The candidate takes only bootstrap/schema extraction, explicit per-instance boot
context, text result-chain serialization, COM_SET_OPTION and their tests. Text
multiple results are necessary for CALL/default consumer connections. The
experimental 128-result cap is removed; 129 row result sets plus terminal OK are
tested, including wire sequence wrap. Existing transport limits still apply.
Binary COM_STMT commands remain unsupported; a real-wire regression preserves
that boundary. Packages/package bodies are outside support/testing/guarantees;
retaining upstream enum members is not package execution support. Events remain
an embedded restriction (1235). DEFINER clauses/security metadata persist, but
skip-grant-tables does not enforce accounts/privileges or native security context.

## Inputs, generation and ownership

| Input / output | Exact identity |
| --- | --- |
| MariaDB 12.3.3 | source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e` |
| lite4mariadb | source_commit `24be9371a2f6c71250a2356631ad6feab2280b02` |
| Converter | `730057c146463f663e8774587bc96fb2bea91af8`, same ordered 13 patches |
| Guest Wasm | `976bbc588a7e70b8c7eff064a492021fb7e44d464dc84fbfd44054c9d044ea87`, 18,376,493 bytes |
| Linked Wasm | `f58eb48ffdea1b5a7978d1dc2af9e2d702518991007b611d46ab8a30da6ed6bb` |
| Generated provenance | `995e7a5138c209e3c8d5109fc7677dcbd897ac7ce8da519c65af51099a0d6cef` |

Toolchain remains LLVM23.1.0, WASIXCC0.4.7, sysroot2026-07-03.1 legacy EH,
Binaryen133 and Go1.26.8; archive hashes/options live in the existing
[toolchain pins](../../release/generated-go-toolchain.json). No canonical
source.patch/converter patch was changed and no experimental.patch is present.
New authored routine overlay/schema inputs are bound by prepare_guest's record.
Wasm grows by 8,480 bytes versus the previous canonical guest. This is a size
observation, not a startup/performance claim; no new benchmark was authorized.

Generated Go was never hand-edited. The raw translator, source adapter and normal
canonical installer produced the checked-in tree. A second invocation from the
same fixed Wasm independently repeated translation, the memory32 failure matrix,
adaptation and installation: **all 99 files, including provenance, match**.
See [regeneration proof](routine-canonical-adoption-evidence/regeneration.json).
The local source build used the single-build development output route; its
[record](routine-canonical-adoption-evidence/guest.json) remains UNQUALIFIED.
`release/generated-go-build.json` honestly keeps completion false pending actual
independent-two-source-build CI receipts. Go identity proof is not substituted
for source rebuild evidence.

### J1 and attribution

The fresh guest moved function indexes/BSS addresses. The binding was reviewed
on actual fresh output, then pinned with exact whole-body hashes. No general
normalization or fallback was added to the production guard. Nineteen relevant
bodies matched the explicit callee mapping and reviewed constant relocations;
[ABI review](routine-canonical-adoption-evidence/abi-review.json) records the
mapping. The 497-byte TLS segment is byte-identical; the 642,620-byte metadata
segment is **not** (relocated pointers). Actual new data bytes are hash-bound.

[Fixture packaging](../../tests/routine_thread_fixture.py) binds the actual
canonical functions/base/data and keeps the historical failure assertions. Only
explicit addresses/indexes/data initialization change. Unprotected heap/mmap
reproduce canary165→1 with both controls passing; protected heap/mmap pass with
and without race. See [six-case results](routine-canonical-adoption-evidence/j1/results.json)
and exact [identities](routine-canonical-adoption-evidence/j1/identities.json).
This does not establish general shared-memory correctness or turn mmap race
silence into evidence of safety.

License attribution was rerun against a diagnostic Binaryen symbol map whose
Wasm equals the actual adopted hash, actual generated definitions and a clean
native host built at e4c4832. All 12 component families retain positive symbols.
[License evidence](../../release/generated-license-evidence.json), its digest in
both inventory mirrors and provenance are refreshed; historical attribution is
preserved. Nested local worktrees required explicit GIT_DIR/GIT_WORK_TREE when
building the audit host: otherwise Go stamped the outer checkout. The accepted
host reports actual e4c4832 and vcs.modified=false; no stamp was fabricated.

## Verification to date

| Check | Result / evidence |
| --- | --- |
| Fresh canonical-owner guest build | PASS, one local source build; two-build CI pending |
| Raw conversion / generated compilation / inventory | PASS; fixed converter/13 patches, normal installer |
| Independent generated-Go reproduction | PASS, 99-file exact identity; memory32 matrix 2,472 cases / 1,693 expected traps |
| J1 exact failure + protected controls | PASS, six heap/mmap/protection/race combinations |
| Go package tests + vet | PASS in canonical check; see initial transcript caveat below |
| Python source suite | PASS, 652 passed / 41 opt-in or environment SKIPs |
| Standard integration Go race subset / SQL/transaction/default / memory traps | PASS |
| Python integration including routine/text paths | PASS, 31 passed / 1 Connector SKIP |
| Snapshot smoke | PASS, 33 checks |
| Go routine and rejected-restore cleanup | PASS; mapping counters return to zero, healthy peer survives |
| Bounded DEFINER | PASS, 16 Fresh cases + same definitions/results in two children |
| GORM existing consumers | PASS, 4 runs / 32 cases (Fresh/Fork/Fork/Fresh) |
| Installed local-wheel SQLAlchemy | PASS, 4 runs / 44 cases, outside checkout |
| Connector/Python26.7.0 local | SKIP: Homebrew Python3.14/OpenSSL4 lacks ssl.PROTOCOL_TLSv1; CI requires PASS, no skip permitted |
| License identity / notices / public source | PASS locally; current files inspected again before push |
| Ubuntu x86_64 / CI macOS | PENDING candidate CI, not relabelled from old experiment |
| Qualification / publication | NOT RUN, outside authorization |

[Evidence index](routine-canonical-adoption-evidence/files.json) binds raw/stored
hashes and saved byte lengths; home-path prefixes in text are scrubbed, accounting
for any differing hashes. Per-run consumer JSON and failure/control transcripts
are included. Runtime receipts use the tested guest/host identities; later docs
and test-runner edits do not change the generated runtime.

Initial broad wrappers failed on two honest follow-ups: sorted JSON lost the
ordered patch-map representation (actual applied patches were unchanged), and
an old regression expected MULTI_STATEMENTS to be rejected. The ordered map is
restored from the actual translator manifest; unsupported-capability rejection
now checks TLS, while real multiple-statement acceptance/toggling/error/reuse is
separately covered. The failed transcripts are retained. Python integration was
rerun successfully and the remaining Snapshot smoke completed. Sandbox network/
localhost denials were rerun with appropriate access rather than counted as
runtime failures or PASS. The final canonical check PASS is recorded in
[check.txt](routine-canonical-adoption-evidence/check.txt): Go tests/vet, 22 early
source gates, then 630 tests / 41 SKIPs and public-source verification. CI reruns
the full wrappers on its exact SHA.

## Reproduce and next gate

Use the exact candidate ref with the [candidate workflow](https://github.com/masahitojp/mariamem/blob/55b09c3ae78f98d1b989cdc5d82bfa33ba96b72b/.github/workflows/routine-canonical.yml):

1. Fresh Linux arm64 root builder: `python3 scripts/build_generated_guest.py`
   (default two independent builds; rejects changed guest hash/experimental patch).
2. Each native target: `python scripts/regenerate_release_guest.py --output <empty-dir>`;
   `generated_release.verify_build(ROOT, exact_sha)` binds actual build/regeneration
   receipts, overlays, toolchain and inventories without relaxing release guards.
3. `python scripts/verify.py check` and `python scripts/verify.py integration`.
4. `python tests/routine_thread_fixture.py --output <empty-dir> --run`;
   `PYTHONPATH=python python tests/v06_routine_definer_probe.py --host <host> --output <json>`;
   `go run -p 1 -trimpath ./tests/routine_probe -output <json>`.
5. Build a local-only candidate wheel (`scripts/build_alpha.py --ci-candidate`),
   install it, run existing SQLAlchemy/GORM consumer runners. No upload/publication.

The workflow is candidate evidence collection, not Qualification. After the Human
reports CI completion, bind actual receipts to its SHA, update source-build
completion only from real matching repetitions, and return to Human adoption
review. Do not infer main/version/release approval from implementation approval.
