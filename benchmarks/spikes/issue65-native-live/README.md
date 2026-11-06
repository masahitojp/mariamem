# Issue65 native Live 3D.2 — prepared, execution pending

The Human selected Linux -> Live -> compatibility/contracts -> productization/
performance and authorized this bounded continuation. The same-source Linux
[repeat](https://github.com/masahitojp/mariamem/actions/runs/42146945114) passed.
Recommendation: test the unchanged production `internal/live.Endpoint` with
native-protocol children, retaining its reserve/drain/retire/commit ordering.
The strongest concern is cleanup ownership: execution failure must remain visible
without treating a joined failed runtime as permanently undisposed, and permanent
capture debt must never be cleared by Reset.

This is a small isolated adapter, not public Live API wiring or a new generation
algorithm. No guest patch, MySQL parser, session migration, production integration,
release or performance change is introduced. The guest remains source_commit
`5d9915d9940ff691249361aafb6ea39551f29a87`, SHA256
`c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf`.
The host base is `ecd5d2b7ceff2085cac59f629c36d688007fc6bc`.
The workflow and templates at its exact triggering commit are additional inputs.

## Scope and evidence required

The [workflow](../../../.github/workflows/issue65-native-live.yml) repeats the
original Linux campaign unchanged, including source comparison, all14 cases,
controlled worker join and binding guards. It then adds exactly `live.go` and
`live_test.go` to the staged command, recompiles and reruns all22 top-level cases.
No existing staged source may change. `live-build.json` records the full source
inventory, template/tooling/guest identities, binary hash and Go build information.
`live-suite.txt` must finish PASS with exactly the original14 plus these8 cases:

| Case | Required result |
| --- | --- |
| DrainAndReset | Idle physical SQL pool blocks Reset and preserves rows/generation; reserve before drain; deny new attaches; hold backend retirement before generation commit; fresh baseline loses child writes; repeat reset |
| CapacityBeforeDrain | An external sibling occupies the spare slot; nonblocking reservation failure preserves ready endpoint, connection and generation |
| ReplacementFailureRecovery | Explicit startup-rejection model blocks SQL without a generation increment; retained old child is joined on explicit successful recovery |
| CancellationBeforeCommit | Deterministic barrier after actual native READY; cancellation disposes both children, blocks SQL and keeps generation; explicit Reset recovers |
| CleanupDebtRecovery | Explicit unresolved ordinary-disposal model retains the real running owner and occupied lease; ordinary admission stays blocked; confirmed retry permits explicit Reset recovery |
| CaptureDebtIsPermanent | Existing root-acquisition cleanup-debt model after real capture; repeated Reset and later disposal cannot erase debt or free its slot; a separate lineage remains usable |
| ParentAndEndpointClose | Parent Close preserves admitted native child but disallows replacement; endpoint Close joins workers and releases slots; repeated Close/Reset cannot resurrect it |
| InvalidRestoreNeverAdmits | Real missing mysql.proc baseline fails native restore before READY; no endpoint is published and confirmed disposal settles its lease |

`WaitDisconnected` waits for both native stats (no sessions and started==joined)
and host session retirement. A deterministic retirement barrier proves the endpoint
calls this boundary before committing; it does not simulate every scheduler race.
Normal data stays opaque. The native child adapter separates terminal execution
cause from successful cleanup only after `awaitJoined` confirms runtime, reader
and relay joins; capture debt remains an error and retains capacity.

The startup-rejection and unresolved-cleanup controls are deliberate models. They
do not establish real I/O-failure detection through void l4m_close, forcible worker
termination, or race freedom. Post-commit cancellation semantics retain the
existing endpoint implementation and tests; no new native post-commit barrier is
claimed. Full consumer/auth/prepared/fatal-wire contracts and public SDK integration
remain later work. This proof must pass before proceeding to those stages.

## Budget, verification and disposal

Initial active budget2h/tooling30min, at most2 heavy CI submissions; each hosted
workspace12GiB budget/free floor12GiB. Guest builder Ubuntu24.04 arm64/root uses
the exact locked build recipe; runtime acceptance is native Ubuntu24.04 x86_64.
No emulation is counted. A new full build is required; the prior run's disposable
WASM was deleted. No persistent cache is introduced.

Local checks: Go formatting/parser, Python AST, the existing8 acceptance-guard
unit tests, public-source/diff checks and `actionlint -shellcheck=` (v1.7.12).
They do not compile or execute this native Live adapter. CI compiles and executes
the exact recorded bundle. Runtime/guest/generated product code is unchanged.
All SDK/download/converter/generated/binary/Go-cache state is owned and deleted
with the existing workspace cleanup verifier, including after failure; keep
compact evidence only. Delete the one-day WASM transfer in an always-run final
job; evidence retention7days. Successful submission hands off URL, SHA and
operation=`native-live-experiment`; do not supervise CI afterward.
