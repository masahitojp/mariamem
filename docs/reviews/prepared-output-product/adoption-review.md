# Output-only candidate — integration review checkpoint

**Decision: integrate the output-only candidate with the explicit
[selected-route acceptance disposition](acceptance-map.md). Recommend yes.** The
product route removes output bind/refetch/numeric/temporal reconstruction without
adding an engine patch; final same-host normal, both-OS public and installed
acceptance pass, and the observed64KiB regression was repaired in the host.
Embedded input and host state remain on the current route.

The strongest objection is that cached-row internals add review obligations and
total future upgrade-hours remain unmeasured. The sampled LTS direct boundary
was stable, and extra conversion responsibilities are actually retired; this
supports bounded structural reuse without claiming time savings. New hooks,
series-specific conversions or weakened public contracts would return to the
value decision. The Human must acknowledge the proposed treatment of unported
full-native observers before Issue132 is fully complete. This recommendation
neither integrates main nor approves a release.

## Fixed object and evidence

- Runtime candidate: ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e.
- Comparison main: eb175ae23292c1c40cfbeb4b9b73132873c4cc6f.
- Canonical gate: d8f66d9a5605b3b738b2175268a3734ee1c89a4a,
  [43450619130](https://github.com/masahitojp/mariamem/actions/runs/43450619130).
  Its guest/C source, toolchain, generated Go and engine patches are unchanged
  through the runtime candidate, confirmed by an exact Git diff. Receipt producer
  and host source identities remain separately named.
- Final host submissions: normal43530112119, public43530115529,
  installed43530119031. All three completed successfully on the exact host SHA; final-ci.json retains job metadata.
- [Current measurements and raw observations](performance-20261114/README.md).
- [Earlier whole-proposal maintenance matrix](../issue128-output-maintenance-matrix-20261112.md)
  and [LTS history](../issue128-lts-output-history/README.md). These existing
  documents were preserved byte-for-byte from the original working checkout;
  that checkout's dirty state was not reset. `historical-cost-evidence.json`
  hashes them. `lts-source-recheck.json` independently re-fetches all30 frozen
  primary files and retains whole-header/producer diffs. Direct row definitions
  and producer remain stable in the sampled transitions; no claim covers
  transitive allocator ABI or all intervening commits.

## Conditions and detection net

| Condition | Assessment | Evidence / detection and remaining limit |
| --- | --- | --- |
| Embedded, input/session/host state retained; no new engine hook | Confirmed | Exact base→candidate diff has no guest/source.patch, guest/patches, host/control/live or public lifecycle implementation change. Current C adapter is the sole new cached-row owner. |
| Removed conversion work is real | Confirmed | guest/prepared_api.inc removes result bindings, refetch and MYSQL_TIME/value reconstruction (23 added/103 removed physical lines). Raw Go validator adds55 lines and uses existing valueShape/validValue. Line counts describe scope, not time saved. |
| Raw ownership/failure checks | Confirmed within finite scope | Canonical C normal/ASan/UBSan failure matrices; Go parser/whole-chain/hidden-OUT tests; actual71 unchanged native-reference scenarios. Mock failure injection does not prove every guest OOM branch. |
| Metadata and repeated execution/OUT/capability | Confirmed within finite scope | Real P2 22+20+15 and P3 14 on fixed source, original native references, required PS_MULTI_RESULTS, schema/reexecution counters. No old full-native count transfer. |
| Packet/JSON budgets | Confirmed finite samples | Old/new/fixed values and metadata agree at64KiB prefixes and16MiB−1024.16MiB−1 causes the same fatal Proc_exit2/ERR2013. Exact maximum and universal oversized recovery are not claimed. |
| Same-engine performance | Bounded observation complete | Five alternating pairs,101 iterations, clean stamped binaries. Fixed median ratios one0.987/thousand0.827/64KiB0.998;64KiB pair range0.950–1.140. Initial regression and repair retained. One Mac, end retained RSS, no peak or universal speed claim. CI does not impose performance thresholds. |
| Formal generation/binding/ownership | Confirmed | Two C builds, both-OS120-file exact regeneration, source/build/binding negative controls and reviewed worker/CRC/dictionary/image relocations. No generated function manually edited; old guest rejects. |
| Both-OS public/installed/ORM on final host | Confirmed | Final43530115529/43530119031 and normal43530112119 all pass ef4d5cd9. Complete reports/logs and source inventories are saved in their directories. Known accepted Connector functional FAILs remain FAILs with native matching. |
| Old A/B controller observers / native factory / D1–D3/G1/G2 | Proposed disposition, not blanket PASS | See acceptance-map.md. Native factory/controller absent; current public oracles remain. Exact old ns/Fork→5000ms and native hold/fence campaigns were not rerun. Human must acknowledge the selected-route treatment before declaring Issue132 complete. |
| Issue138 | Not adopted, still stopped | No candidate diff in its engine patch paths. Historical FAIL/NOT_READY and missing later checks remain; no restart or implicit waiver. |
| Local dependency / experiment residue | Owned performance cleanup complete | Committed source/runner refs, raw measurements/hashes/probes retained. Standalone source copies, hosts, compiler cache and venv removed. Helper verification reports no >1GiB owned paths or cleanup debt. Active product review tree and unrelated user workspaces are protected. |
| Whole MariaDB upgrade cost | Still unmeasured | Migration incurred binding/address/fixture/license/registry repairs and CI diagnosis. Independent source preparation (#150) is not a saving attributed to this route. Next actually offered LTS must record its own shared/per-series repairs and acceptance. |

## Missing-things scan

No changed public API, new user configuration, broader driver support or release
version is introduced. README/Go/Python/releasing descriptions and existing
accepted consumer limitations do not require a changed user contract. The
architecture document intentionally describes published0.6.2; adoption should
record this unreleased internal output change without pretending it was shipped.

Canonical manifests, generated inventory/handwritten owners, exact guest SHA,
source registry and distribution/license records were reconciled during
formalization. Final normal CI checks these source boundaries. No new baseline
release pin or release note is required before a release is selected. Guest
bootstrap remains historical UNQUALIFIED, not reclassified by later tests.

The remaining material item is the Human's selected-route
acceptance/integration decision. Proposed non-application of native-only tests
is explicitly visible, not silently checked off. No evidence establishes future
repair-hours, two-series runtime acceptance,13.3 behavior, Linux performance or
peak RSS. Those limits do not authorize adding engines or expanding this campaign.

Final per-platform evidence and the selected-route proposal are ready for Issue
handoff and Human integration review. Do not merge, publish, restart#138, or
create a broad architecture experiment from this report.
