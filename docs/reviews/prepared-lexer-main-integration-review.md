# Prepared lexer maps: main integration review

**Decision needed:** approve protected PR136 main integration. Recommend approve:
the small startup optimization now has independent canonical C/Go regeneration
and actual guest acceptance on both supported hosts, including the previously
missing native/binary-prepared path. No technical blocker remains against the
fixed approved gates. The strongest objection is limited performance evidence:
P4 whole-batch gain and RSS reduction remain unproven, with unassigned candidate
SELECT tails. The Human already accepted those limits for this adoption;
integration is recommended for the repeatable serial/CPU benefit, without a new
parallel-speed or memory claim. Release approval is separate.

## Reviewed object and acceptance conditions

Code/artifact source_commit `b04b49dbc3dee5e2773b8d775d2202ca1eccff92`;
base_commit `3d8b2201c1f36fa5b7264e0450104055f3822272`;
branch `experiment/lexer-canonical`, PR136. These inputs were reconstructed from
the approved [decision](../decisions/prepared-lexer-maps.md) and PR identity.
The [checksum-bound receipt](lexer-canonical-ci-42463414255/README.md) verifies
run/job/artifact metadata and original ZIP checksums. Development42463420122 also
passes at the code source. Follow-up receipt/ledger/status and GitHub display updates retain that
original identity and document code equality; their own required checks remain
mandatory before merge.

| Prior approved condition | Assessment and detector |
|---|---|
| Canonical source/config binding, unknown/dynamic fallback, no exploratory-history merge | SATISFIED. guest/source.patch + scripts/lexer_prepared.py, input mutation controls, exact compiled-only wrapper; branch based on main3d8b2201 |
| Independent source build | SATISFIED. guest128677392694 has2 agreeing fresh-source repetitions; build guards reject missing/different repetitions |
| Canonical Go installation and exact CRC/thread binding | SATISFIED. both platform inventories:110 identical files; full-body/data checks retained; new table oracle in HANDWRITTEN_FILES |
| Both-host actual638-table/corruption/profiling/CRC/worker/J1 controls | SATISFIED. native128680408235/128680408276; original forced-failure assertions retained |
| Prepared/native SQL, two independent children and cleanup | SATISFIED. both structured SQL results in receipt.json match the same pinned native reference including binary prepared output; refs0/exit0/reaped/root removal |
| Retained-library/ownership bookkeeping | SATISFIED. canonical installer ownership checks and clean host287b3a00 retained-function audit; exact guest reproduced with Binaryen133; Development source/inventory/license checks pass |
| Evidence identity and old receipt preservation | SATISFIED. canonical42463414255/b04b49db, input42448601842/fd615a53 and experimental42437059943/6134274a remain distinct |

## Remaining conditions and detection limits

1. **Protected merge is not yet authorized/performed.** Human approval and current
   strict-base required checks are the final integration conditions. GitHub
   protection detects missing checks/base freshness; it cannot decide adoption.
   If main changes runtime/build inputs, re-evaluate that combined diff before
   claiming this receipt covers it. Do not bypass protection. Readback at the reviewed head
   confirms main3d8b2201, MERGEABLE, strict freshness, admin enforcement and
   required check/integration/Live required gate; see the receipt policy readback.
2. **Performance limits remain accepted.** Mac actual-C P1 Fork p50−8.5%, P4−2.7%,
   CPU lower in all three pairs at each parallelism. P4 whole-batch/RSS/Ubuntu
   speedup is not established. Normal CI does not detect those performance claims;
   the original finite report and decision constrain wording. No additional
   measurement or diagnosis is required by the fixed integration exit.
3. **Runtime dynamic XML loading remains unverified as a whole.** Original source
   callsites/fallback and component tests are preserved; the compiled startup
   path alone changes and all admitted maps match the original guest algorithm.
   Existing CI does not exercise an actual external XML-loading application;
   do not advertise that coverage. This is a recorded bounded scope, not an
   unmet newly introduced integration requirement.

## Missing-things scan

- No additional unsatisfied technical adoption condition found. The previous
  prepared/native gap is closed on both hosts. Qualification/version/publication
  remain separate and unperformed.
- No changed public API/default routing, usage-document contradiction or removed
  SQL/failure oracle found. README, Go/Python usage guides and releasing guide
  are unchanged relative to base. Removed known-map allocations also remove only
  their own OOM branch, as explicitly accepted in the decision.
- Canonical generated ownership/input/build/translation records, host guest
  identity, exact fixtures, license evidence and Python inventory mirror align.
  No guest/experimental.patch is included. Release baselines/notes/version stay
  at their prior identities.
- No stale production comment or claim that Go-overlay measurements were actual
  C measurements found. Historical reports retain their own context.
- No independent regeneration, opposite-platform correctness or declared negative
  control remains outstanding. No new experiment/benchmark was started here.

## Next action and review limits

Approve PR136 protected integration, then merge only after current required checks
and strict-base freshness pass; record the resulting main source/tree identity.
This review did not run a new benchmark, execute cold/setup-cost trials, broaden
SQL/charset/app coverage, or repeat real-guest tests after CI. It reads the
canonical source/installer/fixtures and verifies the exact existing CI artifacts.

## Review order for the source diff

1. `guest/source.patch`, `scripts/lexer_prepared.py`, and
   `benchmarks/lexerpreparedinput/wrapper.c.inc`: compiled-only selection, source
   pins, numeric table production and original fallback.
2. `scripts/runtime_crc32c.py`, `scripts/runtime_thread_lifetime.py`,
   `scripts/generate_runtime.py`, `internal/runtimekind/kind.go`,
   `scripts/generated_release.py`: exact binding, installer ownership, host
   identity and input attestation.
3. `internal/generatedgo/lexer_prepared_integration_test.go`,
   `tests/lexer_prepared_acceptance.py`, fixture updates and the manual candidate
   workflow: actual table/negative/native/prepared/ownership/cleanup assertions.
4. `release/generated-go-*.json` and the two compact CI receipt directories:
   source/hash continuity and observed outcomes.

`.gitattributes` collapses canonical generated output on GitHub while explicitly
leaving every current HANDWRITTEN_FILES owner visible. The large Go output stays
committed for reproducible source distribution; inspect its generator/binding
changes first and use independent regeneration/whole-body checks for the output.
This display attribute changes no build or runtime behavior. CI receipt console
transcripts/API payloads/repeated inventories have been reduced to structured
results and source/hash references under the compact-evidence rule.
