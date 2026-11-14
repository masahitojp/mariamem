# Maintained fixture-entry inputs

Moved out of `docs/reviews` under #158 so current tests do not require a review
archive. Origin: source_commit `a45604e848ff8f58c684f05016b994b7e6e6f7eb`.

- `acceptance.json`: formerly `docs/reviews/v06x-fixture-acceptance.json`.
  Only the current wire inventory and fixed-exit receipt paths changed; all
  contract values, source hashes and historical identities are unchanged.
- `time-campaign-plan.json`: byte-identical to the former
  `docs/reviews/v06x-p1-time-campaign-plan.json`; SHA256
  `d28acf176592cc2317ca6b433bc231b0a1813329b2861155db5176f9d7ea48a8`.
- `p1-fixed-exit-assessment.json`: byte-identical to the former
  `docs/reviews/v06x-python-fixture-implementation-evidence/ci-40987752495/assessment.json`;
  SHA256 `61b5ffa763da3f6e6f5b67dc7b541b7aa4e33d2a25729b7e574ff52970acc853`.
  This compact receipt remains for the explicit historical design audit. Other
  historical paths within the records identify their original source context.

Normal contract tests call `validate_current_contract`; they do not replay
adoption or claim runtime acceptance. The manual historical CLI's obsolete
unreleased-notice requirement already fails on the origin source; relocation
does not repair or waive that separate historical audit requirement.
