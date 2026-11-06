# mariamem project status

This document owns current state and approved direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns implementation, and [decisions](decisions/snapshot-product-contract.md) own
continuing constraints. GitHub Issues own actionable checklists and milestones.
Version themes and candidate adoption do not authorize a release.

## Current published release

**v0.6.2 is published**, 2026-11-05, from:

- `source_commit`: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`
- annotated `tag_object_sha`: `cebdb4114187171bd418b0a1b419e1c27368808d`
- [Release CI 41948677334](https://github.com/masahitojp/mariamem/actions/runs/41948677334):
  `operation=release`, SUCCESS. Both-platform qualification, all six feature
  families, aggregate READY, publication and both public smoke jobs succeeded.
- [Published release](https://github.com/masahitojp/mariamem/releases/tag/v0.6.2):
  macOS/Ubuntu wheels, corresponding source, provenance and SHA256SUMS.

This is exact-source release evidence, not a PASS for later main commits, every
upstream ORM or a new performance campaign. Manual dogfood and measurements keep
their original source/platform boundaries. Python distribution uses GitHub
Release wheels; PyPI publication remains unavailable.

### Shipped capabilities

| First release | Shipped scope | Current guidance |
| --- | --- | --- |
| 0.5.1 / 0.5.2 | Process-local immutable baselines, private child blocks, one Python host per root lineage; ownership-based capture without repeated content scans | [Snapshot contract](decisions/snapshot-product-contract.md), [migration from 0.5.0](changes-since-v050.md) |
| 0.6.0 | Procedures/functions, server-side prepared execution, pytest preparation/PrepareCommand, scoped routing, Go helper, Live/owned E2E, bounded dump reader and ordinary Django recipe; Python minimum 3.11 | [0.6.0 notes](../release/NOTES-v0.6.0.md) |
| 0.6.1 | Prepared Django classes, deferred acquisition, routing exclusion, local xdist, Django 5.2/6.0/6.1; finite per-Snapshot Fork capacity; placeholder credentials; dump statement bound and allocator/WASI write fixes | [0.6.1 notes](../release/NOTES-v0.6.1.md), [Django workers](django-prepared.md#configure-worker-count) |
| 0.6.2 | MariaDB prepared statement alias and zero-parameter flag fixes; bounded input pipelining; opt-in Go Pipe; Node ORM connection guide | [0.6.2 notes](../release/NOTES-v0.6.2.md), [protocol](mysql-protocol.md), [Go connections](go.md#same-process-connections), [Node ORM](node-orm.md) |

D1's agreed scope and issues #43/#72/#74/#77 are complete. Finite Fork #53,
placeholder credentials #78 and buffer-pool alignment #63 shipped in 0.6.1.
Prepared-driver #93/#95, pipelining #94 and Go Pipe #66 are integrated and shipped
in 0.6.2; Node guide #99 is complete through PR #113. Their earlier
integration-pending entries are historical, not remaining release work.

## v0.7.0 — Prepared UCA tables adopted, protected integration pending

On2026-11-07 the Human authorized protected main integration through PR112.
The failed Development run41969231695 identified an unclassified candidate
workflow; its explicit tooling classification is corrected without changing
runtime/guest inputs or relaxing tests. Required checks and strict-base
protection must pass before the authorized merge.

On2026-11-05 the Human approved candidate adoption of
`cbd25f027e804bbd529a85208589ba2dd2899b86` following the
[adoption review](reviews/uca-prepared-canonical-adoption-review.md).
The [decision](decisions/prepared-uca-tables.md) records the bounded change and
accepted measurement limits. This is a v0.7.0 workstream outcome, not a version
metadata change or release approval.

[CI41961766293](https://github.com/masahitojp/mariamem/actions/runs/41961766293)
and its [verified receipt](reviews/uca-prepared-ci-41961766293/README.md) bind that
original source: two independent C builds, identical106-file Go regeneration,
actual table/corruption/profiling/worker controls, native SQL, independent
children, Snapshot and cleanup on macOS15 arm64 / Ubuntu24.04 x86_64.
The guest is `6d744220…`. Incoming single-build origin275c1807 remains
UNQUALIFIED; no old receipt is relabelled to the integration head.

Five alternating Mac fixture pairs report median Fork -23.4%, host CPU -15.5%,
whole fixture -5.3% and one-held-child RSS increment -5.0%. ASCII SQL median
+2.0% and mixed +0.7% are retained as a small-cohort tradeoff; no blanket SQL,
Ubuntu performance or parallel-scaling claim is added. Prepared table bytes
replace repeated construction; each Fork still starts its own engine/runtime.

Integration preserves current main0c4e75dc's published-guide/CI selector updates.
Its runtime/guest/input bytes remain equal to the tested candidate. Only current
acceptance bookkeeping changes, with original CI source pointers retained.
The one-off candidate workflow remains manually reproducible; automatic campaign
pushes stop after acceptance so receipt-only changes do not repeat two C builds.
Normal required `check`, `integration`, `Live required gate` and strict-base
protection remain required for the final PR head. Main integration is pending;
Qualification, version selection and publication are not authorized here.

<a id="adopted-ownership-optimization--unreleased"></a>

## Product contract

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB, uses ordinary connections and commits/rollbacks, and discards
it afterward. Prepare migrations/seed once and share initial state, never prior
tests' mutations. Successful Snapshot consumes its source; rejected busy or
transaction preconditions preserve it. Each Fork reconstructs its own runtime
and writable state. Baseline Close prevents new Forks without revoking successful
children. Public save/load and cross-process baseline sharing are not supported.

Python automatically owns one host per root lineage. Normal child Close or SQL
failure does not close siblings; a host crash loses that lineage. Independent
roots and xdist workers remain independent. Go uses the caller's process.

Fork limits are finite and per Snapshot. Full capacity waits before starting a
child; reserved/starting/cleanup-pending owners retain slots until retirement.
Automatic sizing is a memory heuristic, not a global limit, OOM guarantee or
optimal worker count. Hidden cgroup limits can over-admit: set explicit caps.
Independent root starts remain outside these caps. Live needs two slots and
reserves replacement capacity before draining. Failed capture cleanup can latch
`captureDebt` permanently: close remaining owners and prepare a fresh lineage;
cleanup retry or Live Reset cannot recover that pool. See [the accepted limit](decisions/issue53-fork-limit-adoption.md).

TCP remains the default. Go `Database.DialContext` and helper `InProcess: true`
opt into Pipe for their owned pools. The same wire/guest and 16-session cap apply;
TCP excess returns MySQL1040, Pipe admission returns `ErrCapacity` without a
rejection worker. There is no Node SDK or listener-free startup promise.

<a id="prepared-p6-canonical-ownership--complete-adopted-on-main"></a>

## Supported scope and limitations

- Supported hosts: macOS 15+ arm64 and Ubuntu 24.04 x86_64. MariaDB remains
  12.3.3. Package minimums: Python 3.11 and Go 1.26.0. Release build pin is
  Go 1.26.10, forward-compatibility pin 1.27.3. Python feature profiles use
  3.11/3.14; Django profiles use 5.2/6.1 respectively. Minimums are not a full
  version cross-product. See [Go compatibility](go-compatibility.md) and
  [Django policy](django-testing.md#supported-django-versions).
- The endpoint accepts placeholder credentials without authenticating accounts
  or enforcing user privileges. It is a local test endpoint, not a security
  boundary or persistent service.
- The [wire contract](decisions/v060-wire-contract.md) and
  [0.6.2 protocol limits](mysql-protocol.md) define supported commands/flags.
  SQL and responses are serial per connection. Pending input is bounded to
  1,048,581 bytes; overflow aborts that DB instance. COM_RESET_CONNECTION,
  server cursors, packet continuation, TLS/compression, LOCAL INFILE and
  replication remain outside support. Live Reset is not a session reset.
- The [two Oracle Connector/Python exceptions](decisions/prepared-consumer-exceptions.md)
  remain accepted: prepared CALL result traversal and macOS C/default untyped
  NUL projection. Native-parity syntax-error presentation and environment/C-mode
  SKIPs retain their separate scope. ORM dogfood does not promise MySQL8 SQL parity.
- D1 supports explicit prepared classes and local xdist `load`/`loadscope` with
  explicit worker counts. It has no class-wide atomic block; class preparation's
  `on_commit()` can execute immediately. Routing/shadow_maria is mutually
  exclusive. Django `--parallel`, multiple aliases, remote/auto workers and
  other documented modes remain unsupported.
- Full generated guest execution is not Go race-detector clean; focused checks
  and mmap silence are not general shared-memory proof. The accepted
  [purge comparison](https://github.com/masahitojp/mariamem/blob/424172f017a0ec42c01407300f08411e9d480348/docs/reviews/purge-wasm-go-comparison.md)
  did not establish the real-guest protection premise or authorize a runtime fix.
  Forced reclamation of non-cooperative execution remains outside guarantees.
- Close means ownership/worker retirement, not immediate RSS reduction. Current
  ordinary baselines do not retain one FD per prepared file; old file-backed
  measurements are historical. No general throughput, peak-memory or startup
  guarantee follows from the bounded measurements.
- The 0.x API may change. Source provenance, licenses and reproducible generation
  remain release requirements.

## CI ownership

Daily PR checks select documentation/tooling checks or source/unit checks plus
representative Ubuntu smoke from the changed boundary. Heavy Live, Django,
dump, routing, preparation and SQL/fault acceptance belongs to Release CI.
Documentation-only changes do not justify rebuilding unchanged runtime code.

Release shares portable units and exact wheels/hosts, runs language-independent
Go consumers once per OS, and can reuse authenticated exact-SHA READY plus
complete feature evidence. Manual timing/RSS campaigns are separate from
functional regression. See [development](development.md#local-verification),
[regression versus measurement](decisions/release-regression-vs-measurement.md)
and [release handoff](releasing.md). Historical timing comparisons do not prove
current CI savings; no new runtime reuse policy is approved here.

## Issue #65 — native protocol 3D.1 experiment, not adopted

The Human selected bounded capture/Fork implementation after the
[3D design](design/issue65-native-protocol/snapshot-fork.md). The isolated native
endpoint passes its scoped macOS arm64 [3D.1 experiment](../benchmarks/spikes/issue65-native-capture/README.md):
stopped-root capture, fresh independent Forks, rollback, child recapture,
parent Close, input/output fences, Go Pipe and failure ownership controls.
The report pins actual guest/host/template/binary identities and distinguishes
controlled failures from native execution. The earlier
[3C evidence](../benchmarks/spikes/issue65-go-wire/README.md) keeps its own scope.
The same-source native Linux x86_64 repeat passes in
[CI42146945114](https://github.com/masahitojp/mariamem/actions/runs/42146945114)
at tooling source_commit `1a91ced92d0ff005926a92767c3a82d7415e1ca8`:
14 top-level cases, controlled worker/peer join, two negative binding controls
and21 Python binding cases. All274 Go/assembly/data files match the macOS bundle;
the guest hash is unchanged. Both owned workspaces and the temporary WASM transfer
were disposed. This qualifies only the isolated experiment, not public APIs.

Existing production-guest Go test bindings need adaptation before adoption.
The Human selected Linux -> Live -> compatibility/contracts -> productization/
performance, then authorized the bounded [3D.2 Live proof](../benchmarks/spikes/issue65-native-live/README.md).
The [Live CI42150799762](https://github.com/masahitojp/mariamem/actions/runs/42150799762)
passes all22 cases (14 original plus8 Live) at tooling source_commit
`43d96a62740c8e7309e3e6709d2d83fc929c653d`. Actual native x86_64 execution
confirms physical drain, reservation, generation commit and explicit recovery;
ordinary-disposal and permanent capture-debt controls retain their model context.
The guest and baseline host bundle are unchanged; two Live template files are
added. Both owned workspaces and the transfer WASM were disposed.

The Human moved to compatibility/contracts, prefers host-owned stateful
coordination, and on2026-11-06 approved all three recommended changes in the
[native wire decision](decisions/issue65-native-wire-contract.md): transport close
on fatal established-session failure with original cause/cleanup state retained
by the mariamem owner, the named pinned-native malformed EXECUTE exception, and
removal of the obsolete internal32MiB envelope limit from streaming while
retaining client SQL/command/output-packet bounds.

The [contract and ownership boundary](design/issue65-native-protocol/contracts.md)
retains authoritative SQL/NET/THD state in guest and lifecycle/resource policy in
host. Custom C++ controller code should shrink; removal of all custom C++ is not
proven, and MariaDB's native implementation remains. Controller relocation is
future productization work. The approved behavior still needs native-route
implementation and compatibility evidence. Public API integration, full protocol/
consumer acceptance, race and performance remain unqualified. Existing stable
behavior/tests are unchanged; this decision does not adopt the candidate on main
or select a release.

The Human requested continuing the compatibility experiment and updating Issue65.
[Issue65](https://github.com/masahitojp/mariamem/issues/65) now tracks the current
scope/decisions and remaining work while retaining initial investigation history.
The [fixed-guest compatibility observation](../benchmarks/spikes/issue65-native-compat/README.md)
adds raw credential/capability/prepared/capacity/fatal/full-window probes after the
22-case Linux/Live repeat. [CI42238921778](https://github.com/masahitojp/mariamem/actions/runs/42238921778)
at source_commit `4d45d5445fe65f66237653e3bbfb5a7d6137cebb` completes all7
groups/88 observations with6 mismatches: FOUND_ROWS, direct/Live capacity rejection,
and full-window overflow/EOF monitoring. Credentials, tested prepared state and
fatal EOF pass; the prior22-case lifecycle suite still passes. This is NOT_READY,
not full compatibility acceptance. Both workspaces/transfer were disposed;
original failures and scope are retained in the report. Keep the approved
contract and make source-bound minimal fixes; do not weaken expectations. No guest or controller
implementation changes are made in this step. Maintainability is the primary
objective; transfer conversions/copies may decrease, but performance is unmeasured
and must be compared under matched conditions after correct product integration.


On2026-11-07 the Human requested the three demonstrated compatibility fixes and
integration of current main. Main source_commit
`0c4e75dc2c21421a59d04661efd72a1f58efecaa` is merged into the experiment branch;
its additional changes from the shared0.6.2 source are documentation and
source-scope tooling. This is not adoption of the native experiment on main.
Main advanced during this work to `61973daa19b6f665d7342338c3252dd7af61fc90`
(prepared UCA tables). The Human's requested main intake is now frozen at that
commit and merged too. It changes guest source/data and canonical generated Go;
the old pre-UCA result remains historical evidence. The native guest has now
been rebuilt, all three complete worker bodies reviewed and a fresh macOS arm64
proof run at tooling source_commit `d86f40aeee18121e7c33315e10607d747c2e07e1`.
The [three-fix candidate](../benchmarks/spikes/issue65-compat-fixes/README.md)
passes22 lifecycle cases,7 compatibility groups/88 observations with zero
mismatches, both FOUND_ROWS/UCA Snapshot/Fork controls, focused Live endpoint,
worker-peer boundary, selected-binding controls and22 canonical installer tests.
Guest/host base `a1e3b8a0d7f3750e684610e273a28b802a7135d0` includes frozen
main61973daa and the native FOUND_ROWS patch; host overlays add capacity rejection
and full-window input monitoring. Guest SHA256
`0531ff4f348670dd5e2065a4a25fe9012ed278bd346a12093b97ff1cdfdd67e9`
remains UNQUALIFIED. Its exact source reference has279 Go/assembly/data files.
Linux repeat passes [CI42260991841](https://github.com/masahitojp/mariamem/actions/runs/42260991841)
at candidate source_commit `2ffa5c3428a4b40c211c9f4ace1379253d337588`:22 lifecycle,
7 groups/88 observations, zero mismatches, both supplemental controls and supporting
checks. Source279 files match macOS; both owned workspaces and the guest transfer
were deleted with no cleanup debt. Public integration, full compatibility and
performance remain unqualified. Future legacy/native performance attribution must hold engine
and UCA inputs fixed; published0.6.2 end-to-end comparison separately names UCA.


On2026-11-07 the Human requested continuation after that PASS. A bounded
[remaining-limit observation](../benchmarks/spikes/issue65-native-limits/README.md)
keeps the guest/binding/runtime fixed and adds6 groups/38 named observations for
representative OUT commands/caps, cold/warm input headers, text/binary packet
boundaries,40MiB aggregates with blocked-output control, and Pipe full-window
EOF/overflow. First rerun the unchanged baseline, then permit exactly one added
test source. One Linux CI submission is authorized within this observation task;
no new native execution is claimed before its result. Missing evidence remains
INCOMPLETE, contract differences NOT_READY. Repairs, controller relocation and
productization are separate work; no contract expectation is weakened.


The first remaining-limit [CI42266736265](https://github.com/masahitojp/mariamem/actions/runs/42266736265)
at source_commit `b08c3c938660ca74885b8e967e7a2adb71cdccaf` is INCOMPLETE:
26/38 observations,18 passing,8 mismatches and12 unexecuted. Baseline22/88 still
passes. OUT-command rejection and TLS/PROTOCOL_41 rejection differ from the
approved profile; PROCESS_INFO's following-packet mismatch is secondary to its
unexpected result set. Cold/warm input headers and Pipe full-window EOF/overflow
pass. Six output/aggregate subcases never reach login because their30000ms test
OPEN exceeds the fixed guest10000ms ceiling. The test is corrected to10000ms and
a source-contract check added; no corrected native PASS is claimed. Workspace
cleanup/transit deletion succeeded, while native join was not proven for those
invalid-OPEN cases. The [report](../benchmarks/spikes/issue65-native-limits/README.md)
separates these facts and the extra fixed-source execution cost. No semantic
expectation or guest identity is changed to obtain a green result.



## Current work tracking

Checked against GitHub Issues on 2026-11-05 after v0.6.2 publication. Issues own
live checklists; this is a direction summary, not a second acceptance ledger.

- **v0.6.2:** no open issues in its milestone. Prisma dogfood #92 is complete.
  The unofficial adapter #98 and MySQL8 parity #107 were closed as not planned;
  they are not unresolved release gates.
- **v0.6.x:** [#65](https://github.com/masahitojp/mariamem/issues/65) remains open.
  Its initial source investigation is superseded by the separately selected native
  memory-Vio/WASIX Snapshot/Fork/Live experiments recorded above. Native lifecycle
  execution is established only in that isolated route; compatibility is NOT_READY
  at CI42238921778. The Human selected the three demonstrated fixes. Public API
  integration, adoption and release remain separate. The shipped Go Pipe #66
  does not itself implement guest-native wire relay.
- **v0.7.0:** [the milestone](https://github.com/masahitojp/mariamem/milestone/4)
  owns bounded initialization/resource work: #88 buffer size, #100 common
  initialization, #101 parallel stretch, #103 template reuse and #106 UCA.
  Candidate work/PRs are not shipped support or permission to change defaults.
  Keep exact workload/toolchain/source identities and existing finite budgets;
  do not combine different measurement cohorts or grow an open-ended campaign.
- **Deferred/unassigned:** #56/#64 memory experiments; #68 post-ready SQL latency
  (investigation stopped, no automatic reopening); #84 prewarming; #82 Django
  `manage.py test --parallel`; #57 preparation routing; #58 tooling classification;
  #60 Live extensions; #61 dump extensions; #62 optional wire demand. Broader
  100MiB/heavy-preparation, FD/many-baseline, 16-connection and resource tuning
  remain v0.7.x direction, not new v0.6.2 prerequisites.
- **Accepted/reference limits:** [#20](https://github.com/masahitojp/mariamem/issues/20)
  and [#21](https://github.com/masahitojp/mariamem/issues/21) track the named
  connector exceptions; [#108](https://github.com/masahitojp/mariamem/issues/108)
  records MySQL/MariaDB differences without a compatibility implementation promise.

<a id="v060--dogfood-and-fixture-ergonomics"></a>

The approved product direction remains reducing environment setup, test authoring
and cleanup with real MariaDB. Prefer explicit opt-in, owned lifetimes and
bounded evidence from real consumers. Existing container infrastructure or exact
production MySQL requirements can favor a real external server. Broader framework
support, automatic preparation routing/cache policy and cross-worker sharing need
their own design decisions. [Kickoff notes](reviews/v06x-kickoff-notes.md) retain
exploration context; they do not override shipped contracts.

## Development discipline

Follow **Explore → Challenge → Human decision → Implement → Verify**. Keep
experiments separate from stable main, preserve compact results and reproduction
inputs, and clean disposable outputs under the [workspace policy](experiment-workspace.md).
Select verification by the changed boundary; do not add a performance gate or
broaden acceptance automatically. Candidate adoption and versioned release
approval remain separate. After a release submission, return its SHA/operation/
run URL and stop; CI owns qualification, publication and public smoke.

## Historical decisions and evidence

The former chronological status log mixed current state with versioned
checkpoints and obsolete pending headings. Its full text is preserved at
[release source 47121e1b](https://github.com/masahitojp/mariamem/blob/47121e1be0b399ba4e2270ce3e25c411ade0e2eb/docs/project-status.md).
Use that pinned history, versioned [release notes](../release/NOTES-v0.6.2.md),
individual decisions and source-bound review receipts for past results. Old
FAIL/SKIP/pending records are not rewritten as later release acceptance.
