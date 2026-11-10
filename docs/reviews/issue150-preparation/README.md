# Issue150: versioned legacy preparation candidate

Recommendation: review this source-tooling candidate for main integration.
It reuses the existing input resolver and common pipeline, preserving both the
current 12.3.3 default and a historical 13.0.2 legacy preparation. The benefit is
version selection without rewriting preparation code or replacing canonical
inputs. It does not eliminate upstream patch review, generation bindings or
runtime acceptance. Main integration and release have not been performed.

Base: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
Tested implementation: `b53ac77fc1c9e199cb926bf3cf69812392443c00`.
Extraction source: `cee676e8fcd77ee15db2b31639a1c100758c5b1b`.
The later evidence/documentation/whitespace-attribute commit changes no pipeline
or registered input bytes. Original root-worktree user changes were not included.

## Evidence

`comparison.json` records complete path/byte/mode/link inventories:

- Current 12.3.3: 32,203 members, no differences for selected preparation; the
  refactored default also equals the frozen main producer.
- Historical 13.0.2 legacy: 32,344 members, no differences from the original
  `32c799031f619164d3730b61a0bc9d7ae48dcd9b` producer.
- Inputs were downloaded from pinned URLs into fresh owned scratch and checked.
  Git commit identity was checked with `git_identity.py`; no SDK or build used.
- Focused tests: 54 passed and22 subtests; existing source tests:82 passed,
  3 optional auth-hook source controls skipped (archive is in comparison scratch,
  not canonical build/downloads). These are not MariaDB/runtime results.
- Public-source check passed. Historical patch context whitespace is preserved
  with a narrow attribute rule, rather than modifying checksum-bound inputs.

The comparison ran from a clean committed candidate. Its command durations are
preparation observations, not upgrade speed or human effort measurements.
The source trees were removed after comparison; downloaded archives and the
one-use test environment are removed after retaining these compact logs.

## Boundaries and remaining obligations

Canonical `guest/input.json`, source patches, release lock, generated guest and
bindings remain byte-identical. Native profiles, raw-row/v2 wire and controllers
are not imported. Historical13.0.2 includes its original observation patch and
frozen adapter data solely for reproducible source preparation. Its selected
receipt is release-ineligible. This is not13.2 or future13.3 runtime acceptance.

New `test_guest_input_resolver.py` and `test_guest_preparation_context.py` are
collected by the existing normal Python-tooling CI owner (`verify.py` pytest
discovery); no new broad runtime campaign is needed to verify input boundaries.
The opt-in full-source comparison above provides the independent real oracle.
Existing rejection checks cover mixed/unknown versions and profiles, hashes,
patch images, symlinks, output collision, old/mixed receipts and changed recorded
source files. Hash-bound registry data remains the reviewed trust root, not a
signature or a guarantee of upstream semantics.

The strongest concern is registry maintenance: new versions require reviewed
archive/patch/proof registrations, and new upstream constructs may require common
helper changes. This is an explicit remaining upgrade cost. Data-only registration
applies only to implemented stages/contracts; the lexer still has source-bound
constants. The next version must review those exceptions, not bypass validation.

Reproduction and registration: [guest/versions/README.md](../../../guest/versions/README.md).
No previous local workspace or untracked spike artifact is an input. Historical
Git worktrees are used only as independent comparison oracles. Issue150 remains
open until the reviewed candidate is integrated into main; no release is implied.

Validation note: invoking test_routine_schema alone without scripts on PYTHONPATH
exposed its existing import-path dependency; the recorded source-check group with
PYTHONPATH=scripts passed. No runtime module or test expectation was changed.
