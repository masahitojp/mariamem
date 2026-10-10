# mariamem v0.4.5

This release stabilizes verification and documents the practical cost of preparing
test databases. The database, Snapshot/Fork ownership and integrity contract are
unchanged; no new public API or MariaDB guest upgrade is included.

- Previously unreachable MySQL-wire regression cases now run in maintained
  integration tests: data/metadata, errors, protocol and session behavior.
- Ordinary development checks no longer rely on historical Product CI artifacts
  remaining available. Runtime qualification, final artifact consumer checks and
  public distribution smoke have explicit separate responsibilities.
- Generation ownership has one canonical handwritten-file list. Existing source,
  license and packaging consistency checks run before expensive compilation,
  with actionable generated-output mismatch errors and no duplicate later run.
- Fresh/Snapshot measurements include preparation, SQL and cleanup. Fresh remains
  useful for inexpensive setup; Snapshot/Fork can amortize expensive migrations
  and fixtures. There is no universal data-size threshold or adopted optimization.

Generated-source reproducibility, corresponding source, notices and final
Go/Python consumer qualification remain required. Runtime proof retains its
actual tested source identity; final artifacts have their own exact identities.

See [measurement conditions and reproduction](../benchmarks/v045-measurement.md)
and [verification review](../docs/reviews/v045-verification-economics.md).
Supported platforms and existing limitations are unchanged.
