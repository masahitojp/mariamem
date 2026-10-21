# P2 TIME metadata — internal-source decision required

## Human Review

Decision: permit a narrowly bounded MariaDB-internal metadata patch for prepared
TIME parameters. Recommendation: permit the one-line candidate below, then verify
it against the unchanged native oracle. Both OSes now reach the actual P2
comparison and show the same single metadata discrepancy; no value difference is
observed in these22 cases. This blocks P2 acceptance, not evidence of SQL data
corruption. P1 and the repaired12 binding mutation tests passed on both OSes.

The strongest objection is a new upstream maintenance obligation and a fresh
Wasm identity/rebinding cycle for a display-width difference. That cost is real.
A blanket host TIME-length adjustment is not justified: engine column metadata
may come from a TIME field or expression rather than this parameter path. Do not
weaken the native comparison or classify the differing descriptor as equivalent.
The proposed engine-side change addresses the specific asymmetric source path.

## Evidence and exact proposal

[Run39565377640](https://github.com/masahitojp/mariamem/actions/runs/39565377640),
source_commit `ab5c39db3ca99dba9948c9c2c9b2326714bebda9`.
[Receipt and hashes](v06x-prepared-p2-time-metadata/receipt.json) bind the original
failure capture, unchanged reference and fixed MariaDB83e909fc source files.
All22 cases execute; binary rows and terminal packets match native. Only
`negative-time-over-24h` column declared length differs: embedded16, native23;
other descriptor bytes match. Both OS captures are identical. No driver failure
or truncated SQL value is established by this descriptor mismatch alone.

Pinned [sql/sql_prepare.cc:673–780](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_prepare.cc#L673)
uses MAX_TIME_FULL_WIDTH in ordinary Item_param::set_param_time (line700), but
MAX_TIME_WIDTH in the embedded implementation (line780).
[sql/item.cc:4522](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/item.cc#L4522)
passes that argument through fix_temporal with fractional precision. This is a
concrete source asymmetry consistent with the observed width difference. The
[one-line proposed diff](v06x-prepared-p2-time-metadata/proposed-source-change.txt)
changes only the embedded call to the ordinary server's constant. It is **not
applied or verified**; matching all affected results must still be demonstrated.

## Bounded implementation and cost if approved

- Add only this pinned source change to guest/experimental.patch, with complete
  pristine-file hash and zero-fuzz/exact preimage checks; keep canonical
  guest/source.patch and all converter patches unchanged. Preserve release
  rejection of experimental patches. Adapt the dedicated experimental workflow
  only as needed to produce an explicitly unqualified source artifact.
- Verify TIME parameters with/without fractional seconds, zero, negative,
  >24h/range cases; compare actual TIME columns/expressions and multiple
  parameters to native, preserving complete column/row/terminal comparison.
- Fresh source build, fixed converter translation and exact function/data/TLS
  review; repin the single candidate only after review. No generated hand edits,
  old guest fallback or relocation-tolerant matcher. Re-run both-OS development
  SQL smoke, bindings/mutations and unchanged P1/P2 comparisons.
- Estimated additional work:0.5–1 engineer-day plus source/CI execution, assuming
  this is the only newly exposed difference. This is not a delivery promise.
  Recheck the existing per-guest-update maintenance allowance; canonical patch,
  source/license/provenance adoption remains P6. Other findings trigger a new
  explicit decision rather than silently broadening this patch.

The [approved design stop condition](v06x-prepared-product-design.md#8-cost-generation-ownership-and-next-decision)
(section7 immediately above section8) requires stopping if a MariaDB-internal edit
is needed. Accordingly no runtime patch, CI resubmission, main integration,
Qualification or publication is performed at this decision point. Full P2–P6
scope remains unchanged. Existing source/unit/development successes do not close
that scope.
