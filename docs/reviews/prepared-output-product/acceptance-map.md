# Issue132 — selected output route and prior acceptance conditions

Reviewed runtime candidate: ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e.
Fixed main baseline: eb175ae23292c1c40cfbeb4b9b73132873c4cc6f.
This is a disposition proposal for the final Human integration decision, not a
waiver, blanket PASS, or a replay of the old full-native campaign. The Human has
selected output-only productization, retaining embedded input, Go wire and host
state. Full-native22/88/38/G1/G2 counts remain attached to their historical cohort.

| Prior condition | Selected route / evidence and detector | Remaining decision or limitation |
| --- | --- | --- |
| A: exact QueryTimeout, Start/Fork TCP/Pipe, shared/control entry | No diff in mariamem.go, snapshot.go, connection.go, internal/host or internal/control. Public source integration executes Go/Python paths; installed acceptance executes external module/wheel. Existing defaults, Python fractional timeout/wire cases remain. | The old native-specific ns observer and Fork→5000ms mutation were not ported or rerun. Do not label this exact old observer condition satisfied. Retaining current host behavior versus requiring native-controller substitution tests is part of the selected-route disposition. |
| A: drain, reservation, cancellation, parent/child independence | Existing internal/live endpoint/capacity tests, control/fork tests, public owned-prepared tests and Live acceptance smoke remain. Same runtime route and no implementation diff in those owners. | These preserve current product oracles, not equivalence of a controller that is absent from the selected candidate. |
| B: failure notification versus disposal, ownership/debt | Existing TestWorkerTrapFailsPendingCallsBeforeCompletion, TestConsumedFailureKeepsTransferUntilGuestAndWorkersJoin, control cleanup/debt/parent-close tests, actual worker failure and public lifecycle regressions remain. Installed gate uses go_snapshot_failure_lifecycle. | Old native-controller worker/reader/writer holds, early-Done/fence mutations and all composed owner-fault counts were not replayed. None are claimed real-guest PASS through mocks. Public product behavior remains the baseline contract. |
| B: independent native Close/peer-output-error fix | No C++ controller, native backend factory or old full-native Serve is present in this output route. | This native-controller patch is not transplanted. It remains historical/unadopted rather than becoming a silent correctness waiver for changed production code. |
| C: values/metadata/chain/OUT/capabilities | Go raw validator versus retained encoder, exact native packet fixtures, hidden-OUT and malformed-suffix no-prefix tests, C-to-Go harness and C ASan/UBSan. Real guest P2 22+20+15 and P3 14 pass unchanged native references; PS_MULTI_RESULTS required. | Finite tested types/scenarios; not unrestricted protocol or driver support. C failure injection is engine mock, separately labeled. |
| C: row representation/ownership/version/limits | Missing/null/mixed rows, raw header/bitmap/type/width/minimal-length/temporal/trailing bytes, old private version rejection; C row/list/count/copy/free/OOM harness. Real64KiB prefix boundary and16MiB/32MiB-frame-near samples compare main/candidate. | Oversize16MiB−1 already produces fatal Proc_exit2/ERR2013 on main and candidate; no recovery claim or limit extension. Not an exact maximum search. |
| C: D1–D3, four-type NULL, handshake1043 | Current Go input, framing and handshake remain. Existing raw request/capability/error fixtures are retained; P2 matrix includes BIT/INT24/YEAR-related actual native comparisons. | Do not import a different full-native decoder/error policy or claim its whole G1/G2 campaign. Existing contracts and accepted client exceptions remain; adopting a new wire policy needs a separate decision. |
| C: native-factory-disabled failure and old-Serve tripwire | The condition is explicitly conditional on selecting native. This candidate intentionally serves through current Go wire and has no native factory. | Proposed implementation-specific non-application, to be acknowledged with final selected-route disposition. Making old Serve fail would contradict the chosen route. |
| C: both OS, independent generation, one coherent candidate | Canonical43450619130 has two identical C builds and both-OS120-file regeneration, exact bindings/build guards/worker controls. Its guest/C inputs, toolchain and generated runtime are byte-identical through ef4d5cd9. Final normal43530112119/public43530115529/installed43530119031 pass ef4d5cd9. | Earlier receipt source SHAs remain distinct from host SHA. Final statuses/source identities are retained in final-ci.json; no candidate mixing or old artifact-only dependency. |
| D: declared consumers and exceptions | Existing Go driver, pure/default Python profiles, native-matching accepted exceptions, installed wheel/external module, GORM32 and SQLAlchemy44 use existing scripts. Functional FAILs stay FAILs under the Human's exact accepted disposition. | No unsupported default/C-extension behavior is converted to functional success; untested drivers remain untested. |
| D: same-condition performance/resources/cost | Same engine/default settings/UCA/toolchain/client/workload, clean stamped binaries, five alternating pairs. Original64KiB regression and host-only repair retained. End retained RSS measured, peak not measured. | One Mac, bounded queries; no universal regression bound or upgrade-time saving. Runtime source no new engine patches; ordinary binding/license/fixture work still incurred. |
| E: Issue138 page-cleaner/spare archive | No diff from fixed main in guest/source.patch, guest/experimental.patch or guest/patches; no native/spare-archive candidate patch adopted. | Historical FAIL/NOT_READY and unexecuted follow-up remain. #138 stays stopped; checkpoint progress is not claimed branch reachability. No new branch experiment or waiver. |

## Detection limits and proposed disposition

Existing CI catches malformed rows/mixed versions, binding mismatch, retained
public contract regressions and exact accepted consumer exception drift. The
new row-presence tests also exercise nested/duplicate fields and atomic failure.
It does not measure future MariaDB repair-hours, all internal-layout dependencies,
peak RSS, or execute absent full-native controllers. The initial64KiB regression
was found only by this explicit A/B comparison, not by a functional CI assertion.

Recommend using current product oracles for unchanged host owners and the added
raw-row boundary checks for changed output. Keep old native-controller observations
historical; do not manufacture PASS counts. The Human's final integration decision
must explicitly settle this proposed applicability (especially A/B's unported
native fault observers). Until then, Issue132 is not declared fully complete or
closed. This is the remaining decision boundary, not authorization to restart#138
or design another controller. Release approval is later and separate.
