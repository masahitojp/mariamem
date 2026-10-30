# Prepared P6 — scoped candidate verification complete

P6 scoped verification is complete at source_commit
`c7960d604f525c15d66fc003b0341989c4719267` with Go1.26.10 and the existing
Human-accepted consumer exceptions. [CI39859160329](https://github.com/masahitojp/mariamem/actions/runs/39859160329)
passed all four jobs. Main adoption, target version, Qualification, Product
Validation and publication remain separate Human decisions. See the
[Human Review](v06x-prepared-p6-human-review.md) and
[final receipts](v06x-prepared-p6-complete-evidence/receipt.json).

## Earlier preparation and failed integration run

[CI39798209370](https://github.com/masahitojp/mariamem/actions/runs/39798209370)
confirmed two independent canonical source builds and99-file independent Go
regeneration/build guards on both platforms at source_commit
`1b4e41ebfff86cbab228dfa623c3364e80ddf9eb`. It failed later because two existing
Python integration assertions still required PREPARE rejection. These assertions
now explicitly require native PREPARE metadata and RESET/CLOSE/reuse; historical
text-only callers retain their explicit rejection expectation. There is no
accept-either-result fallback. Runtime, guest inputs and generated Go are unchanged.

At that failed run the remaining gap was complete runtime/consumer/J1 replay.
Those skipped checks were not counted as PASS; final CI39859160329 now supplies
the successful current-source execution. See the [CI repair receipt](v06x-prepared-p6-ci-fix-evidence/receipt.json).

## Inputs and ownership

- Main baseline: `22a8c64305e706408ebcd54cfd7ecc45426802ad`.
- Reviewed files: `5d729eff7bd64aa5de3d2b5464e728c3a52fb7ed`, with
  [the Human-accepted bounded exceptions](../decisions/prepared-consumer-exceptions.md).
  Experimental commit history is not merged. Its reports remain historical
  evidence, not evidence of current-candidate execution.
- Canonical authoring basis: `38b1f795598e3dd56eb3ce9a3e5f3c180d0d59ab`;
  generated installation: `bbd3ce4e9c140b6d9023cabe5a889a4751aa09f9`;
  runtime identity correction / local clean host:
  `0ca1a1483c1f18db83c2b5a499f9ff82dcc1685d`.
- MariaDB12.3.3 source_commit `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`;
  lite4mariadb recipe_source_commit `24be9371a2f6c71250a2356631ad6feab2280b02`.
  Archive identities and tag-object identity remain in `guest/input.json`.
- Converter `730057c146463f663e8774587bc96fb2bea91af8` plus the same13 patches;
  The initial receipts use Go1.26.8. The Human subsequently requested the
  Go1.26.10 security update (forward compatibility1.27.3); current-source
  new-Go regeneration/runtime/audit results now pass in CI39859160329.
  LLVM23.1.0, WASIXCC0.4.7, Binaryen133 and the pinned legacy-EH sysroots remain
  unchanged. No shibukawa converter dependency is introduced.

The exact approved three-file source repair moves from `guest/experimental.patch`
into `guest/patches/12.3.3-prepared.patch` (SHA256
`ffd5e884f20da6ca993d9f515910fab69639a2f200d2f36f58ee9cf91a37dcb4`).
It is the third `guest/input.json` series entry, after common portability and
12.3.3 redo, before recipe `guest/source.patch`. Whole-file pre/post hashes,
ordered application and prepared whole-function fixtures fail closed. Recipe
`guest/source.patch` is unchanged. A future independent experimental overlay is
still isolated and release-rejected; no such overlay is present here.

The repair owns TIME metadata width, prepared parameter/result metadata and
WASIX-only embedded metadata. Authored prepared bridge/include, guest and host
wire/session/lifetime components retain their reviewed owners. Generated Go was
installed through the translator/adaptor/installer, never hand-edited.
`HANDWRITTEN_FILES` and MemFS pinned preimages remain unchanged. Historical
TIME-only source proof now lives in `tests/fixtures/prepared-time-source-history.json`.

## Artifact identities and reproduction

| Artifact | Identity |
| --- | --- |
| Optimized guest | `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40` (18,405,460 bytes) |
| Linked guest | `7450e04846de36177151b36bdd027c97fbea46e90b00b3412db20e01e3711da6` |
| Generated provenance | `c20f8a4cd4117921c525cf467a8684ea1bd9ac7f86b494bd5975b031095d3b62` |
| Initialized data | `6111bfe83de71695517e3d9f25fed842d4a43bfc6ae774815abafd81af9064dd` |

`release/generated-go-inputs.json`, `release/generated-go-translation.json` and
`internal/generatedgo/provenance.json` bind converter patches, raw translation,
adaptation, generated source and owned glue. Independent local regeneration
matched all99 files (62 transpiled inventory entries,36 owned/glue files and
provenance). Its memory32 regression ran2472 cases with1693 expected guest
traps and host exit0. The raw receipt retains the original development Wasm
source_commit; it is not relabeled as a new source-build receipt.

The canonical commands are:

```sh
# Fresh Linux arm64 root builder with pinned dependencies, empty /work and SDK:
python3 scripts/git_identity.py inspect HEAD
python3 scripts/build_generated_guest.py
# Native supported-platform checkout, downloaded same-SHA guest artifact:
python scripts/regenerate_release_guest.py --output /absolute/empty/output
python scripts/verify.py check
python scripts/verify.py integration
```

The [candidate workflow](https://github.com/masahitojp/mariamem/blob/55b09c3ae78f98d1b989cdc5d82bfa33ba96b72b/.github/workflows/prepared-canonical.yml) binds all
steps to the pushed commit and includes the full P1–P5 replay, actual native
control, routines/DEFINER/auth, installed wheel and SQLAlchemy/GORM, J1 controls,
retained-library audit and17 independently mutated build-evidence rejections.
It is candidate verification, not Qualification. `release/generated-go-build.json`
now records the completed canonical source/regeneration proof from CI39859160329;
build/license receipts retain their exact tested source_commit and Go1.26.10.

## J1 and accepted failures

All19 J1 boundary functions have exact new hashes, explicit callee/index mappings
and reviewed integer relocations. The diagnostic string is byte-identical at its
new address. TLS grows497→505 initialized bytes: the497-byte prefix is identical,
and the extra8 bytes are zero. Initialized data/segments bind to the already
reviewed prepared data identity; this is not a claim that all old/new data match.
The historical assertion template is unchanged. Heap/mmap unsafe controls fail
with the original canary assertion; protected and protected-race runs pass.
These six outcomes do not establish general shared-memory correctness or turn
mmap race-detector silence into evidence of safety.

Normal `verify.py integration` now runs selected real Go/Python prepared consumers
and includes `internal/preparedproto` in its focused race set. Exact detailed
edge comparison includes subsequent SQL and cleanup outcomes. Mutation tests
reject changed values, errors, missing edges, stale C-client profiles and a
changed disposition record. The Human acceptance is separate from the original
functional FAIL. No pure-mode forcing, alternate-driver substitution, interpolation
or SQL rewriting makes that FAIL disappear.

README/Go/Python guides distinguish this unadopted candidate from publishedv0.5.3,
state the precise Oracle exceptions, and avoid blanket prepared compatibility.
The positive MariaDB-driver observation is limited to the two tested cases.

## Evidence and remaining checks

The compact [receipt](v06x-prepared-p6-evidence/receipt.json) records source
identities, file hashes and runner-path scrubbing. Runtime and SQL values are not
normalized. The unchanged [P5 decision](../decisions/prepared-consumer-exceptions.md)
links prior both-platform native and MariaDB-driver evidence.

| Check | Status | Evidence / limit |
| --- | --- | --- |
| Ordered source preparation and exact prepared fixtures | PASS locally | preparation receipt and focused source tests |
| Full source Python tests | PASS locally |796 PASS /41 SKIP, `source-all.txt`; opt-in actual-host cases remain SKIP here |
| Canonical generation, compile,99-file independent reproduction | PASS locally | local-generation / local-independent-regeneration; development Wasm origin explicitly retained |
| J1 original failure plus protected/race controls | PASS locally | six run logs, results and exact identity/data review |
| Selected Go/Python real consumers | PASS matching locally | clean0ca1a14 host, Python3.14.8 / OpenSSL3.5.9; accepted functional FAIL remains FAIL |
| Original upstream notices / retained-library attribution | PASS locally | six pinned source archives;12 positive symbol families in clean host |
| Full source Go tests/vet and final inventories | PASS locally | `check-final.txt`:22 inventory/source tests +774 other source tests,41 explicit SKIP, Go tests/vet and public allowlist |
| Two independent canonical source guest builds | PASS atc7960d6 | CI39859160329, exact expected guest/link hashes |
| Both-OS independent regeneration/build guard | PASS atc7960d6 |99-file identity, original same-SHA receipts |
| Full semantic/consumer/J1 replay after integration repair | PASS atc7960d6 | Both OSes; accepted functional FAILs retained;17 guard mutations rejected |
| Qualification / Product Validation / release | NOT RUN | separate decisions |

No new performance improvement is claimed. The remaining production maintenance
cost is the explicit three-file MariaDB repair plus authored bridge/wire owners
and their fixed-input regeneration/replay on upstream updates. Package/event
scope, bounded DEFINER policy, existing shared-memory limitations and approved
consumer exceptions are unchanged.

Local checks caught an old handwritten runtimekind guest constant and a copied
`.log` evidence filename forbidden by the publication allowlist. The constant was
updated to the fixed guest identity; the text log was renamed. The existing tests
and allowlist were retained, and the complete source check passed afterward.
`check-intermediate.txt` preserves the latter failure; it is not final evidence.

Owned scratch/build/download/cache copies and the completed helper worktree were
removed after preservation (about5.8GiB before cleanup,164KiB compact local
evidence remains). The helper intermediate source ref is retained, with no owned
path over1GiB or cleanup debt. See `v06x-prepared-p6-evidence/cleanup.json`.

## CI integration expectation repair — 2026-10-23

Both platforms passed focused race/Go integration, default execution and generated
memory tests. Python integration had30 PASS /2 FAIL: the old text-only
`test_python_wire` and `test_text_multi_runtime` still demanded error1235 for
COM_STMT_PREPARE. Current prepared support correctly returns the success header;
the stale assertions stopped the job before J1 and P1–P5 replay.

`exercise_prepared_lifecycle` reuses the established P1 raw-wire parser, compares
both descriptor groups and warnings to the fixed native placeholder metadata,
checks RESET success, sends CLOSE followed immediately by PING to detect an
invented CLOSE ACK, and requires1243 for the closed ID. Existing following SQL
checks remain. New deterministic tests reject old1235 behavior, altered metadata,
wrong counts/missing EOF, RESET failure, an extra CLOSE ACK and a wrong closed-ID
error. Focused local checks:60 PASS /15 explicit actual-host SKIP. These are not
substitutes for fixed-source native CI. No guard, accepted failure, public scope
or engine implementation changes.
