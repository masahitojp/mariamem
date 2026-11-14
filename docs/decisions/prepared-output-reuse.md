# Prepared output reuse — accepted integration boundary

On2026-11-14 the Human approved main integration after the
[Issue criteria review](https://github.com/masahitojp/mariamem/blob/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/prepared-output-product/issue-criteria-submission.md),
including the proposed [prior-condition disposition](https://github.com/masahitojp/mariamem/blob/a45604e848ff8f58c684f05016b994b7e6e6f7eb/docs/reviews/prepared-output-product/acceptance-map.md).
Runtime source: ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e; base:
eb175ae23292c1c40cfbeb4b9b73132873c4cc6f. Later documentation/decision commits do
not change the CI-tested runtime. This is adoption approval, not release approval.

Keep embedded MariaDB. Reuse only prepared output bytes through one C adapter,
then validate them in Go. Retain existing input, host state, connection/session,
flow control and lifecycle. No new engine patch/API function or controller is
part of this decision. Private prepared protocol v2 and its coherent generated
guest replace the old representation; no automatic old-route fallback is provided.

The benefit accepted now is fewer custom output-conversion responsibilities.
The sampled LTS direct boundary was stable. Total update-hours, availability lead
time and payback remain unmeasured; source line counts and CI PASS are not those
measurements. Issue128 completed comparison and decision support; Issue164 retains
the future actual-update cost observations. Provision for roughly
two user-selectable LTS offerings with upstream-aligned maintenance remains the
direction, with only12.3 offered now. This decision does not add another engine.

## Maintenance boundary

For the next actual engine update, review the direct `MYSQL_STMT.result` /
`MYSQL_ROWS` producer, list count/termination, length convention, copy-before-free
and ownership. Review metadata/status/OUT and existing input/engine patches as
common obligations. Retain shared valueShape/validValue rules; do not grow a
second independent conversion table. Record shared versus per-series repairs,
human investigation and review versus machine and queue time, and initial migration versus
recurring update cost. The earlier #150 preparation benefit is common to both routes.

Use existing C ownership/failure controls, Go raw/chain/hidden-OUT/version tests,
canonical generation/build/binding guards and public/installed consumer gates.
The saved71-case native-reference probes and frame checks can be rerun for an
engine update. They and the bounded A/B performance comparison are not all automatic
normal-CI assertions. Preserve that detection limit; a functional PASS is not
proof of no performance regression. Do not claim universal speedup, peak RSS or
unexecuted Linux performance from the saved single-Mac measurements.

If cached-row changes require a local adapter adjustment, assess and verify it.
New engine hooks, series-specific conversion implementations or weakened public
contracts return to the Human's value decision. Returning to the prior route would
also require coherent C/private protocol/Go/generated inputs and acceptance;
immediate fallback and restoration time have not been verified.

## Accepted verification disposition

Use current product oracles for unchanged host owners and the added checks for
changed raw output. Old full-native controller/factory/Serve tripwires and exact
native observer campaigns are historical, not current PASS counts. Their selected-
route treatment is accepted with this integration; existing public contracts and
accepted consumer exceptions are retained. Issue138's unadopted patch/FAILs and
stopped follow-up remain separate; this approval does not restart or waive them.

Original CI sources remain distinct: independent canonical gate43450619130 on
d8f66d9a5605b3b738b2175268a3734ee1c89a4a has unchanged guest/C/generated inputs
through the approved host; normal43530112119/public43530115529/installed43530119031
pass the approved host SHA. Preserve named source identities and their Git ancestry;
do not relabel receipts to an integration or merge SHA. Normal PR CI verifies the
concrete integration source. Later release Qualification/publication remains separate.

## Retained observations and limits

The [compact performance samples](../../benchmarks/prepared-output-20261114/README.md)
retain the original regression and host-only repair, five alternating pairs and
all outliers. Final median candidate/main execute+fetch ratios were 0.987 (one
row), 0.827 (1,000 rows) and 0.998 (64KiB); the latter pairs span 0.950–1.140.
This single Apple M1 sample does not establish a universal speedup or Linux result.
The 71 native-reference scenarios covered P2 22+20+15 and P3 14 cases, including
metadata/reprepare, OUT and PS_MULTI_RESULTS. Finite frame probes at 65535,
65536, 65537 and 16MiB−1024 bytes succeeded on both sources; 16MiB−1 produced
the same fatal Proc_exit2/ERR2013 on both. This is neither an exact maximum nor
a recoverable-oversize guarantee. The initial tuple-versus-JSON-array comparison
failure was a comparator representation error, not a runtime repair.

The canonical [short receipt](../reviews/prepared-output-product/ci43450619130/README.md)
remains because current generation provenance references it. Superseded reviews
and raw job bundles were retired under #158; original detailed context is
available at the fixed source linked above, not asserted as current CI evidence.
