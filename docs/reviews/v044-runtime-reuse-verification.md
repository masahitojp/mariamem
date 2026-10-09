# v0.4.4 runtime-evidence reuse — focused verification

Runtime basis: `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`.
Original both-platform evidence: [Product CI 37898847164](https://github.com/masahitojp/mariamem/actions/runs/37898847164).
Artifact IDs/digests are pinned in `release/runtime-validation.json`.

No runtime/API/guest source was changed by this tooling integration. New checks
cover the release proof boundary; no local runtime acceptance or benchmark was
repeated.

- `python scripts/release_preparation_checks.py`: PASS, 177 pytest cases and
  6 Product runner/identity tool cases; version, public-source boundary,
  generated-source inventory and clean diff checks passed.
- Strict YAML duplicate-key validation and `bash -n` for all changed workflow
  run blocks: PASS. New Python modules parse successfully.
- Rejection coverage: wrong run/workflow/repository/commit/platform/build settings,
  failed/missing jobs, expired/different/duplicate artifacts, altered ZIP/internal
  hashes, incomplete coverage/inventory, unsafe ZIP paths, tag-object identity,
  runtime/dependency/recipe changes, modes/renames and hidden version logic edits.
- Explicit reuse failure stops before READY discovery/build/push/publication;
  frozen proof mismatch cannot become READY. Both platform records must agree.
- Main-push and local metadata checks reuse only the authenticated runtime;
  genuine later runtime changes keep ordinary development verification.

The final release still builds exact-version artifacts and requires fresh
external consumer/GORM/SQLAlchemy, corresponding source/licenses/provenance,
publication and public smoke. This report does not claim those later gates passed
or that the final integration SHA ran the original runtime campaign.

Reproduce focused checks with Python 3.14, pytest 8.4.2 and PyMySQL 1.2.3.
The tested tree contains two tracked historical outputs excluded from the
original public-source receipt: `build/go.mod` and
`benchmarks/results/direct-link-consumer-experience.json`. Only those exact names
are omitted from receipt completeness; the full Git tree comparison still
requires their bytes/modes to be unchanged. Unknown omissions remain failures.

Live proof: `python scripts/runtime_validation.py --candidate-sha <clean HEAD>`.
CI freezes that proof into each handoff, recording both source identities.
