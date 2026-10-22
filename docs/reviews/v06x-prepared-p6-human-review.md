# P6 Human Review — Go1.26.10 candidate

**Decision requested: adopt the Prepared candidate and Go1.26.10 update into main.**
Recommendation: **integrate**. The fixed-source canonical path now reproduces the
reviewed guest, independently regenerates all99 Go files, and passes the scoped
protocol/lifecycle/consumer/guard gates on both supported platforms. Main adoption
is the only requested decision; target version, final Qualification, Product
Validation and release remain separate.

The strongest objection is user-visible: Oracle Connector/Python26.7.0 still
fails the two accepted workflows (prepared CALL traversal can leave its
connection unusable; Mac C/default can shorten an untyped NUL-containing character
projection). This prevents a blanket one-line-switching claim. I still recommend
adoption because the Human explicitly accepted those exact boundaries, the new
Go run reproduced the same bounded failures against native controls, and strict
edge/profile tripwires and public-guide limits remain. No new exception is requested.

## Reviewed object and evidence

- Runtime candidate / artifact source_commit:
  `c7960d604f525c15d66fc003b0341989c4719267`.
- Main base, rechecked against the remote before this review:
  `22a8c64305e706408ebcd54cfd7ecc45426802ad`.
- Artifact reviewed: `docs/reviews/v06x-prepared-p6-canonical.md` at that candidate,
  together with [CI39859160329](https://github.com/masahitojp/mariamem/actions/runs/39859160329)
  and the [original receipt bundle](v06x-prepared-p6-complete-evidence/receipt.json).
  These inputs and the main-adoption decision were reconstructed from the ongoing
  P6 task and prior Human decisions, rather than a new review form.
- Four jobs PASS: canonical guest builder, native control, macOS15 arm64,
  Ubuntu24.04 x86_64. This is candidate CI, not Qualification.
- Go1.26.8 predecessor `4aa764aefedfcb8ae3bde55077c8f29ad4081026` also passed
  [CI39804746790](https://github.com/masahitojp/mariamem/actions/runs/39804746790).
  It is historical evidence, not a substitute for the new-Go run.

## Prior conditions — cross-check

| Condition | Judgment | Evidence / detection |
| --- | --- | --- |
| Keep functional failures separate from native parity and Human disposition | Satisfied | Both `fresh-native-matching.json`: matching PASS, functional FAIL, ACCEPTED_BOUNDED_EXCEPTIONS |
| Exact edges, following SQL/cleanup and client-profile binding; reject mutations | Satisfied | Both `selected-consumers` / fresh-native matching; `tests/test_prepared_consumers_probe.py` and normal integration gate |
| Canonical ordered source owners and strict pre/post identities; no experimental overlay | Satisfied | `guest/input.json` third patch, exact source pin, actual canonical `guest.json`; build guard rejects experimental/source/overlay mutation |
| Independent Wasm and Go reproduction | Satisfied | Two identical source-build repetitions; both native `regeneration.json` inventories match99 checked-in files including provenance |
| Exact lifetime/data/J1 closure and original failure oracle | Satisfied | Both `j1-identities.json` and `j1-results.json`: unsafe heap/mmap fail, protected/race controls pass; all six expected outcomes |
| License/provenance/source inventories and build guards | Satisfied | Both Go1.26.10 clean-host audits show12 positive component families; positive guard +17 independently rejected mutations; refreshed build/license ledger mirrors |
| Durable normal-CI selected consumers | Satisfied | `scripts/verify.py:integration` runs selected real consumers and focused prepared protocol race coverage; `.github/workflows/check.yml` pins the required driver |
| Public guides state exact candidate support/limits, not universal compatibility | Satisfied | README:173–184, docs/go.md:146–157, docs/python.md:188–199 and unchanged accepted-exception decision |
| Toolchain change rechecks applicability | Satisfied for P6 | Actual new-Go host buildinfo, regeneration and same consumer edges on both platforms; version-only old PASS was not reused |

All original P1–P4 matrices, routine/DEFINER/auth, installed-wheel and existing
SQLAlchemy/GORM steps passed in both native jobs. The accepted MariaDB-driver
claim remains its two tested cases. Unsupported Linux Oracle C import is an
explicit allowed SKIP; required default/pure modes executed. No all-driver,
all-Wasm or all-shared-memory guarantee follows from these results.

## Missing-things scan

- Unsatisfied or newly re-approval-gated P6 conditions: **none found** after ledger
  closure. The immutable P5 decision still describes P6 as open at its dated
  acceptance point; this review/status owns the subsequent completion.
- Current guide/contract contradictions: **none found for this unadopted
  candidate**. Guides now use current-source-build wording that stays accurate before and
  after adoption, while preserving publishedv0.5.3 history. CI cannot decide
  editorial scope; the explicit guide/contract cross-check found no contradiction.
- Generated ownership / bookkeeping: **none left open for P6**. Canonical ordered
  patch and converter13 patches, HANDWRITTEN_FILES, MemFS preimages,99-file
  regeneration, current build/license receipts and exact mirrors are preserved.
  No generated Go is hand-edited. New version notes/tag baselines are not needed
  until a version is selected and release preparation is authorized.
- Unreached scope: final Qualification, Go1.27.3 external consumer, full product
  performance validation and publication are **NOT RUN here**. They are later
  gates; existing qualification/release checks still require the new compiler
  and same-source receipts. Existing general shared-memory and forced-stop
  limitations are unchanged; no new census or general safety proof is claimed.
- Stale in-code comments: **none found in the changed prepared/generation/wire
  boundaries**. The historical text-only helper keeps an explicit rejection
  branch; current callers require positive native-metadata/RESET/CLOSE/reuse.
- Mixed decisions: **none**. Passing CI or this recommendation does not authorize
  main integration, Qualification, Product Validation, a version or publication.

## Records and next action

Build/license ledgers and current completion/status documents are saved on
`experiment/prepared-p6-records`, based on the exact candidate above. Only
bookkeeping, mirrored legal inventory and documentation/evidence files change there;
production runtime, guest, converter, generation scripts/pins and workflows are
identical to the tested candidate. The separate branch preserves the submitted
candidate and avoids another full CI for a results-only push. The receipt records
original/stored hashes; only runner paths and traceback whitespace are scrubbed.

The bookkeeping boundary also passed81 focused source/inventory/release-guard
tests, with a diff restricted to documentation, build/audit ledgers and legal
inventory mirrors. No unchanged runtime was rebuilt or requalified.

On Human approval, integrate the tested candidate plus these bookkeeping records
and record the Human approval/integration identity. This does not start final
Qualification; that later, separately authorized gate must target the final main
source. No new experiment, engine repair or broader compatibility claim is a
prerequisite found by this review.
