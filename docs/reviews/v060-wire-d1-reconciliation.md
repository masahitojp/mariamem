# v0.6.0 wire / D1 evidence reconciliation

2026-10-31 JST. **No newly required wire command implementation was identified
in this bounded reconciliation. D1's additional prepared entry is explicitly
deferred from0.6.0 by the subsequent Human decision and will be considered in
0.6.1, tracked by [Issue43](https://github.com/masahitojp/mariamem/issues/43).
The adopted standard Django recipe remains available.**

The [D1 decision](../decisions/d1-v060-deferral.md) records the missing lifecycle
boundaries, user impact and remaining work; it is not a D1 PASS or implementation
promise. Default transactional flush correctly starts the second test empty,
so its existing PASS cannot close the later declared prepared-schema/seed
contract. Selected serialized rollback and fixture cases are narrower evidence,
not proof that D1 is impossible or necessarily expensive.

## Proposed meaning of wire-contract completion — separate decision

Proposed sentence for explicit Human interpretation approval:

> For v0.6.0, wire-contract completion means a source-pinned supported/unsupported
> inventory plus native/guest and declared-client-path anchors with the named
> accepted exceptions; complete per-entry packet capture is not required,
> uncaptured paths remain UNVERIFIED, and the exact release candidate must still
> pass Release CI.

This defines a proposed acceptance basis, not a claim that all entries or release
acceptance are complete. The previous D1-only approval does not approve this
interpretation; no approved wire-scope policy is silently added to project status.
Recommendation: accept this bounded basis because it preserves actual native
controls, driver counters, original failures and explicit limits without opening
a blanket trace campaign. Strongest objection: an uncaptured client command
sequence can remain invisible even when application scenarios pass. A concrete
required sequence or discrepancy should trigger a separately bounded probe;
source inventory alone would not settle that case. This proposed sentence makes
that residual uncertainty visible instead of upgrading it to observed PASS.

## Reviewed object and limits

This is the requested30–60min source/evidence reconciliation, not a new app
campaign, implementation, Qualification or release review. Question: which
accepted wire/D1 requirements are already met, what named gaps remain, and what
finite action follows? Exit: pinned source comparison, per-entry evidence map,
remaining-path dispositions and detection nets. No new runtime, dependency
installation, native/guest execution, packet capture or heavy CI; tooling budget0
new measurement infrastructure. On budget expiry report remaining evidence as
UNVERIFIED rather than introducing another campaign.

- Main/base source_commit: `ce66b9df2067c546c88f6748fcbce2dc175a619a`.
- Active contract wire source_commit: `437d74d9d11d8dc2a03dc94bba0d37346131ebff`.
- Older inventory cc00ccd and P1 reconciliation2ad041cd retain their source
  context; neither is rewritten as current runtime evidence.
- Original E2E snapshot77db4c2c is historical. Metadata refreshed during this
  revision: PR28 head `d38deb043bc84bda064cee06b8568bc5174b744c`, OPEN and not merged.
  Human adoption approval is already recorded by its owner; protected integration
  remains owner-managed. This dated snapshot is not a claim about a future PR
  head or current-head qualification. [Owner decision at inspected head](https://github.com/masahitojp/mariamem/blob/d38deb043bc84bda064cee06b8568bc5174b744c/docs/decisions/e2e-integration-conditions.md).
- dbt fixed1.7 receipts: local f37b2a7b and Ubuntu7a9a6f72, saved completion at
  [3787e3dc](https://github.com/masahitojp/mariamem/blob/3787e3dc85221e0a01997c3410198e41e014a1fc/docs/reviews/dbt-revalidation-completion.md).
  Both receipts and the [completion record](dbt-revalidation-completion.md) are
  now selectively included in this PR for main; executed source/receipt bytes
  are preserved. Issue19 is closed and project-status records completion.
- Main integrated for this revision: `cff1fd779fdf35a1f33775b9866cf78f3c09f74c`.
  It adds CI/release tooling, not a changed wire/runtime surface; the source
  comparison JSON records this recheck separately from the original ce66b9df scan.

The [source comparison](v060-wire-d1-source-comparison.json) independently
compares all four contract hash pins; all are byte-identical. A broader Git diff
also finds no changes in internal/mysqlwire, internal/guest, guest or
authoritative generated source between437d74d and this main. This is source
continuity, **not** fresh runtime PASS. `check_fixture_design.py` passes, with
its explicit `runtime: NOT_RUN` output retained as the verification boundary.

## Required-entry reconciliation

| Entry / condition | Existing evidence and exact scope | Missing item / disposition | Existing detector |
| --- | --- | --- | --- |
| P1 preparation, per-child schema/seed after commits/failure, owned cleanup | [Main integration](v06x-p1-head-integration.md); full41063375697 is older Ready head8912224a/actual6ccec794; final daily41076760360 is850ddcc2/actual0f59d660 | Already adopted. Do not reopen full acceptance; final-source platform qualification remains owned by Release CI | P1 native/installed acceptance, original failure/admission controls, exact-source Release workflow; daily smoke has narrower scope |
| G1 bounded preparation/children/pool cleanup | [G1 review](v06x-go-fixture-acceptance-review.md), main PR6; later integration CI40810248227 atfbc5037e8d409e22f496ccd25eae9675135884d6 succeeded | Already adopted. Contract corrected to `ADOPTED_ON_MAIN`, with original source/merge/CI/review binding | Helper real-guest/controlled-fault/installed campaigns; design lint does not validate G1 status against adoption |
| D1 ordinary manage.py / pytest-django recipe | [Guide](../django-testing.md), adopted PR3; final Django40502166621 succeeded with native2/guest4 cells. Recorded actual PR checkout730bd17 differs from head0490b43 but full trees match | Standard recipe accepted. This does not close the later prepared-entry obligation | tests/django_lifecycle/ci.py validates native inputs, cases, partial-DDL failure, original error and owner disposal |
| D1 every prepared-entry test starts from declared schema/seed | Scope draft rowD1; tests/django_lifecycle/run.py:90–94 intentionally expects SEED then empty for default flush | **DEFERRED, NOT PASS** by the Human decision; remaining design/acceptance is Issue43 for0.6.1 consideration | Existing oracle detects standard flush regression, but no D1 restoration test exists; ordinary green Django CI cannot detect this missing product boundary |
| EP1 browser / EG1 HTTP owned hooks and reset | Earlier accepted-scope E2E receipts and separate PR28; refreshed source d38deb04 under its owner | Human adoption approval is recorded; PR28 was OPEN/unmerged at d38deb04 metadata refresh. Integration remains separately owned; not closed by this report | E2E owner's exact-source acceptance/ancestry/protected gates; no new result inferred here |
| Wire capability inventory and retained consumer exceptions | [Active437 reconciliation](v06x-wire-main-437d74d.md), [P6 review](v06x-prepared-p6-human-review.md), [exceptions](../decisions/prepared-consumer-exceptions.md) | No supported dispatch/flag drift found. Usage-to-command observations remain partial; see ledger below | Design lint checks source hashes, command/capability sets and names of ledger fields, not populated per-entry observations |
| Independent dbt preparation | Fixed core1.7.20/adapter1.7.0/Connector26.10.0, two hosts, native/guest × threads1/4 with TEXT DISTINCT and cleanup | Original repair question complete; source-bound local/Ubuntu receipts and completion record selectively included here for main. No1.8 scope added | Replay result/census/row/cleanup assertions and CI ZIP/inner checksum validation; no packet trace |

One metadata read each independently confirmed Django40502166621, P6
39859160329 and G1 integration40810248227 as completed/successful. API head SHA
is check attachment, not a substitute for the saved checkout/source receipt.
No existing campaign was rerun. P1 metadata/evidence was inspected under its
main integration record; this report does not independently re-authenticate all
old ZIPs or qualify latest main.

## Wire operation evidence ledger

These rows reconcile the nine required ledger fields. `UNVERIFIED` means no
per-entry packet/capability capture was found, not an absent command or PASS.
The default assumption must not turn app success into a complete wire trace.

| Operation / client options | Observed command/flags | Native / guest result | Error / cleanup | Source/client pin and detecting oracle |
| --- | --- | --- | --- | --- |
| P1 prepare callback/command, ordinary SQL and routing; worker-local owner; PyMySQL1.2.3/SQLAlchemy2.0.54 | Per-entry command/flag sequence **UNVERIFIED**. Existing text/handshake surface is source-supported; a Python SQL parameter is not proof of binary prepare | Fixed P1 native/installed profiles PASS under their historical sources; no new run | Original failure and cleanup debt preserved in owned-entry controls; final host/temp observed | P1 integration sources/receipts above; P1 runtime/negative controls and tests/test_python_wire.py. No detector demands a complete packet ledger |
| G1 database/sql + mysql1.9.3; helper-owned bounded pools; parameterized SELECT | G1 full wire trace **UNVERIFIED**. tests/gointegration/fixture_test.go uses WHERE id=?; separate tests/prepared_consumer/main.go checks Com_stmt_prepare increases for explicit/implicit prepares | G1 both-host SQL/isolation PASS; separate P6 native/driver controls prove their own prepared path, not every G1 command | Owned cleanup and capture consumed/preserved controls; controlled engine-fault limits remain | G1 integration40810248227; P6 sourcec7960d60 and its Go consumer counter oracles. Do not relabel a P6 counter as a new G1 packet capture |
| D1 fixed Django5.2.8/mysqlclient2.2.7/pytest-django4.12.0; manage and pytest, single alias | Per-entry handshake/command trace **UNVERIFIED**. Schema, migrations, transactions, flush and metadata queries are exercised; no reset/cursor support inferred | Standard-runner native2/guest4 PASS; prepared-D1 result **NOT_RUN** | Duplicate errno1062 recovery, failed migration errno1146 and original ProgrammingError chain, no body after setup failure; owner closed/reaped/temp removed | Django40502166621 and saved PR3 identity; cases.py/run.py/ci.py/recipe probe. No D1-entry admission/debt oracle exists |
| EP1 Django/Playwright browser and EG1 Go HTTP | Current entry-specific command/flag capture **UNVERIFIED in this scan**; browser/HTTP success alone is not protocol coverage | Old Live examples/selected E2E sources remain separate; current PR28 acceptance belongs to its owner | Hook retirement/Reset/application shutdown evidence is not COM_RESET_CONNECTION evidence | PR28 inspected source d38deb04 and its owner acceptance/decision records; do not duplicate the campaign or claim current-main adoption |
| Fixed dbt1.7 seed/run/test/snapshot/docs, threads1/4; Connector26.10.0 | Full command/flag trace **UNVERIFIED**; model SQL and original TEXT DISTINCT are observed. No prepared/CALL/reset-family claim | Both observed hosts native/guest PASS; application rows match within declared snapshot normalization | Expected generic uniqueness data-test failure and subsequent SELECT; schema0, guest connections0/reaped/temp removed | f37b2a7b/7a9a6f72; saved source-bound result and CLI/census/row/cleanup oracles at3787e3dc |

This is a populated **partial-observation** ledger. It closes the missing written
mapping, not all UNVERIFIED captures. The Human may accept these bounded source,
native and client-path anchors for the declared profiles; if a protocol sequence
must itself be proven, name that sequence and cost a targeted probe. A blanket
all-command capture campaign is not automatically required by this report.

## Remaining-path dispositions

Source dispatch is QUIT1, INIT_DB2, QUERY3, PING14, Prepared22–26, SET_OPTION27.
Base bits are1|4|8|512|8192|32768|65536|131072|524288; PS_MULTI_RESULTS262144 is
conditional on validated support. Unhandled commands return1235/42000 by source.
A source branch is not per-command runtime acceptance.

| Inventoried path | Evidence / scope |0.6.0 treatment and residual uncertainty | Detecting oracle / blind spot |
| --- | --- | --- | --- |
| COM_RESET_CONNECTION31 | No handler; [approved release scope](../decisions/v060-release-scope.md#explicitly-not-in-060) explicitly excludes it | **Already OUT**. Reconnect, STMT_RESET and Live Reset remain different operations. Per-entry request census is UNVERIFIED | Generic unsupported branch; reconnect-state tests do not prove session-reset semantics |
| COM_STMT_FETCH28 / server-side cursors | No handler; same approved exclusion | **Already OUT**. Ordinary prepared SELECT is not cursor support | Prepared owner/metadata tests cover adopted family; no positive cursor oracle |
| TLS/compression/DEPRECATE_EOF/alternate auth | Not advertised; accepted endpoint is local root/empty password. tests/test_python_wire.py::test_unsupported_handshake_flags_are_rejected_without_poisoning_host (CLIENT.SSL/1235 at lines129–130) rejects SSL and then reuses the host | **Keep existing unsupported/local-endpoint boundary**; do not claim transport security or arbitrary authentication. Complete driver negotiation traces are UNVERIFIED | SSL refusal/host recovery oracle exists. It does not prove all unsupported flags or other auth profiles |
| LOCAL INFILE | LOCAL_FILES not advertised; no file-transfer exchange implementation. SQL-file import is a different path | **Proposed retain outside declared profile**; no selected-profile requirement was found. Loader demand and actual client requests remain UNVERIFIED | Source capability map only; no successful or dedicated refused LOCAL exchange test identified |
| CHANGE_USER17 / STATISTICS9 / PROCESS_INFO10 | No handlers; app metadata SQL goes through QUERY | **Proposed retain unsupported** for0.6.0; individual demand/request paths remain UNVERIFIED | Generic unsupported branch; metadata-query success does not cover these commands |
| Binlog/replication18/21/30 | No stream dispatch/adopted feature or selected CDC workload | **Proposed retain unadopted/watch**; no binlog feature added from this scan | Source/config inventory, no CDC campaign; SHOW syntax is insufficient |

The first two exclusions reuse an existing Human decision. The other rows keep
current implementation limits visible and make their proposed disposition
explicit; they are **not** newly Human-approved exclusions or hidden support
claims. No additional protocol implementation is authorized by listing them.
Packet continuation/capacity raises remain OUT under the same scope record;
detailed resource/capacity tuning remains0.7.x.

## D1 concrete obstacle, user impact and remaining work

The current parent example owns one server per runner invocation
(docs/examples/django/run_tests.py:21–34); Django owns test DB creation,
migrations, class/test transactions, flush and serialization. It does not capture
a declared prepared baseline or acquire a new mutable prepared child per test.
The lifecycle oracle deliberately accepts default flush's SEED→empty transition.
The evidence is specifically cases.py::SerializedCases (setUp checks the
migration SEED) and mixed_cases.py::SerializedCases/FixtureCases (inherited
serialization and authored JSON fixture). These bounded suites are valuable;
there is no dedicated general D1 restoration oracle, arbitrary prepared-schema
restoration proof or new-entry acceptance.

Concrete integration questions remain: where preparation ends relative to Django
test DB creation, which runner/fixture owns restoration for ordinary TestCase
versus transactional tests, and how to retire physical connections/transactions
before changing the underlying owner. The scope draft explicitly says this
mechanism needs design; there is no approved D1 implementation entry. These are
source-supported missing boundaries, **not** proof that a large adapter or guest
change is required. No confirmed common wire/runtime defect is established.

User impact of the approved deferral: users retain the documented standard Django runner and
choose framework-native TestCase/fixtures/serialized rollback policies. They do
not receive an automatic D1 prepared-Snapshot lifecycle or universal seed replay.
Default transactional flush remains empty; call that behavior by its actual name.

Remaining D1 work if later selected: choose that explicit boundary/starting-data
policy, define command/callback preparation and readable-owned admission/cleanup
behavior, then prove first/second/reverse/commit/failure restoration and cleanup
on both hosts/minors. Scope should stay on the authored orders app first.
[Oscar input selection](v06x-independent-django-input.md) is source-only proposed
external workload exploration; it is not required to decide this D1 boundary and
would not by itself implement the prepared entry. Do not make Oscar or another
framework compatibility matrix a new automatic release gate.

## Finite follow-up and what is not a gap

1. D1 deferral is now approved and tracked by Issue43 in0.6.1. No design/code/CI
   begins from that scheduling decision. Shared defects remain in scope.
2. Human wire-scope review: accept the partial ledger and proposed remaining-path
   treatments, or name a specific required protocol observation. No automatic
   blanket trace/requalification campaign. Unsupported capability remains visibly
   unsupported even if no selected app requested it.
3. Existing work: E2E owner closes PR28 adoption; #24 owns the finite panic guard
   follow-up. Neither is resolved by this document. G1 metadata and dbt completion/receipts are reconciled in this PR without changing original evidence or claiming broader support.

G1's active JSON pending status is corrected here. Separate historical prose cleanup remains:
tests/django_lifecycle/README.md ends with a never-executed candidate sentence,
and the scope draft's historical checkpoint says P1 is not yet accepted. Current
adoption/status records supersede those statements, but a concise current-status
pointer would prevent readers treating them as fresh blockers. Existing CI does
not validate that narrative/adoption consistency. Preserve their historical
source context; do not erase old failures or trigger new runtime campaigns to
resolve prose drift.

No new guest/generated/runtime patch need, version/ledger update prerequisite,
new adapter dependency or source-identity gap was found for **this document**.
No universal SQL/wire, cold setup, resource or arbitrary-framework proof is
claimed. Existing accepted Connector exceptions remain unchanged and detailed
resources stay0.7.x. Stage-only release notes still need normal final-version
handoff later; that is a release task, not another D1 investigation.

Verification for this docs change: exact Git/source comparisons; existing design
lint (DESIGN_LINT_PASS / runtime NOT_RUN); documentation/public-source/version
and diff checks. No unchanged runtime tests or CI submission required. The report
is a recommendation and evidence map, not main adoption or release approval.
