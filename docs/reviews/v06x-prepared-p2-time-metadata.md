# P2 TIME metadata — internal-source decision required

## Human Review — original patch proposal, not approved

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

## Follow-up: is the difference an intentional embedded specification?

Conclusion: no official rationale or specification explicitly requiring the
embedded TIME parameter width to differ was found in the inspected sources,
commit messages, documentation and targeted MariaDB Jira searches. That search
result is not proof that no such statement exists, nor an official bug ruling.
The positive historical evidence points toward an old branch not following the
fractional-seconds metadata update; this last characterization is our inference.

Official MariaDB/server history, queried through GitHub Commit.blame and commit
REST API at the pinned source and its ancestors:

| Record | Confirmed observation |
| --- | --- |
| [d3c5c499, 2004-12-02](https://github.com/MariaDB/server/commit/d3c5c4997ca71610abf7e94b0c66f27278e3341e) | Embedded time sending repair handles day-to-hour and range clipping. Its width already uses MAX_TIME_WIDTH. This predates MariaDB fractional-seconds support. |
| [a8a757c6, 2011-03-01](https://github.com/MariaDB/server/commit/a8a757c6bb32bbf291afdf33df861127489889ab) | Commit titled wl#173 temporal types with sub-second resolution changes the ordinary set_param_time call from MAX_TIME_WIDTH to MAX_TIME_FULL_WIDTH. Its sql_prepare.cc diff contains just that ordinary-path change; embedded width is not updated there. |
| [6aedbf40, 2017-11-24](https://github.com/MariaDB/server/commit/6aedbf40e08395533d4f5fc29220b6f358988979) | MDEV-14494 refactors functions into Item_param methods and preserves both different constants. It explains refactoring and multiplication cleanup, not a new deliberate embedded-width contract. Its parent is a18f6009e3227d6c781fafd93a002767ae5b2425; blame there attributes ordinary width to the2011 commit and embedded call to the2004 repair. |
| [Pinned sql_const.h](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/sql/sql_const.h#L78) | MAX_TIME_WIDTH16 documents a representation without fractional seconds; MAX_TIME_FULL_WIDTH23 includes six fractional digits. |

Targeted public searches included embedded + TIME/metadata/fractional/microseconds,
set_param_time and both constant names, with MariaDB documentation/Jira domains.
No directly applicable intentional-difference statement or exact known-bug issue
was located. Unrelated embedded limitations do not establish this one as a
supported exception. No maintainer was contacted and no issue was filed.

Thus the earlier conversational statement "this is embedded specification" must
be read only as observed implementation behavior, not a documented supported
contract. Conversely, this investigation cannot claim MariaDB officially calls it
a bug. It supplies a concrete historical basis for a missed-update hypothesis.
The original patch proposal remains unapplied; investigation alone neither
approves an internal change nor proves users are affected. Driver impact and
whether to preserve/align this inherited metadata remain product decisions.
This follow-up changes documentation only; no runtime rebuild/test is required.
