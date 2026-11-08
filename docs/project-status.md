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

## v0.7.0 — Prepared UCA tables integrated on main, unreleased

On2026-11-07 PR112 squash-merged to main source_commit
`61973daa19b6f665d7342338c3252dd7af61fc90` after Development
[42249730837](https://github.com/masahitojp/mariamem/actions/runs/42249730837)
passed all required checks at source `d4409411231981daff54ae08f3fb7b1bc7119708`.
The squash commit and tested PR head have identical Git trees. Main integration
is complete; this is not a versioned release or new performance measurement.

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
protection were satisfied for the final PR head. Main integration is complete;
Qualification, version selection and publication are not authorized here.

<a id="adopted-ownership-optimization--unreleased"></a>

## v0.7.0 — Prepared lexer-map candidate, evidence acquisition in progress

On2026-11-08 the Human authorized continuing Issue126's prepared lexer-map
prototype into a bounded C-source candidate and measuring the remaining Fork
stages. This authorizes candidate work, not adoption, main integration or release.
The [current attribution and candidate gate](../benchmarks/lexercandidate/results/README.md)
keeps the measured Go-overlay source950b4b40 separate from the C input build.
The exact product baseline remains3d8b2201; canonical guest/generated inputs and
public APIs are unchanged. `guest/experimental.patch` is experiment-only.

In the corrected single-Mac attribution, ordinary Fork p50 is19.27ms/P1 and
25.40ms/P4. Diagnostic-on common initialization remains largest at5.90/6.42ms,
followed by InnoDB4.67/5.91ms. Observer overhead is9.5–20.5%; those stage times
are not assigned to ordinary Fork totals. All tails and preflight failures remain
recorded. An initial diagnostic warmup exposed the Go prototype's guest-address
allowlist as relocation-sensitive; the final surrogate and C candidate use
unique compiled IDs only at the pre-XML compiled registration callsite.

Standalone original-C algorithm replay passes all638 full512-byte maps and
bounded fallback/OOM/corruption controls. Actual C guest acceptance is pending.
The next experiment CI acquires one UNQUALIFIED C build, a native SQL reference
and macOS/Ubuntu raw translations. Existing exact guest/function CRC/thread
ownership bindings must be re-established from those outputs before installation;
they are not disabled or silently generalized. That CI's successful input/
translation receipt is not actual guest, native SQL differential, performance,
independent two-C-build reproducibility or Qualification acceptance.

The first C-input acquisition [CI42428352206](https://github.com/masahitojp/mariamem/actions/runs/42428352206)
failed on source86edd6cd during WASIX CMake configuration: the SDK is installed
under `/root/.wasixcc`, while the container's default HOME points to
`/github/home`. The [original source-bound receipt](../benchmarks/lexercandidate/ci-42428352206/README.md)
retains standalone C-map replay/native-reference PASS and translation SKIP.
The narrow repair matches the existing accepted builder's `HOME=/root` setting
and adds missing/wrong-HOME negative controls. Guest/runtime/release inputs are
unchanged; a corrected CI result is still required.

The second acquisition [CI42431032597](https://github.com/masahitojp/mariamem/actions/runs/42431032597)
passed the HOME/configuration boundary, then failed to compile the experimental
initializer: upstream `CHARSET_INFO` is const-qualified. The
[const-correction receipt](../benchmarks/lexercandidate/ci-42431032597/README.md)
records why the old mutable native shim missed it. The initializer now takes
`struct charset_info_st *`, matching the original producer. The replay imports
the pinned upstream const typedef and must reject the old wrong signature before
building the guest. Full638-map/component controls pass locally; actual WASIX
build/translation acceptance remains pending. Prepared table payload and prior
Go measurement bytes are unchanged.

C-input acquisition is now complete at sourceb1a265cc in
[successful CI42433100335](https://github.com/masahitojp/mariamem/actions/runs/42433100335):
one UNQUALIFIED C build, native SQL reference and both-OS raw translations PASS.
The new guest is `14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`;
both hosts produced identical51-file inventories. This supersedes the pending
input-build status after the two original failures, without relabelling them.
The [source-bound receipt and host-binding inspection](../benchmarks/lexerbinding/README.md)
record exact CRC/worker target references and unchanged non-address instructions,
TLS and BSS layout. Seven offline proposal tests pass; canonical guards remain
unchanged and reject the new guest. Next is scoped host-stage binding and actual
both-host table/corruption/native SQL/independent-child/worker/cleanup acceptance.
Input acquisition does not establish actual guest acceptance, new performance,
independent C reproducibility, adoption, main integration, Qualification or release.

The Human then authorized explicit host binding and actual-guest acceptance.
The [fixed host-stage recipe](../benchmarks/lexerhost/README.md) adds an opt-in,
UNQUALIFIED single-guest profile without changing canonical CRC/thread adapters,
product generated code or release inputs. It reuses the exact successful C guest
and native reference, freezes the complete raw inventory and keeps original C
source separate from the current host source. The next bounded both-host CI
checks full638-table equality/corruption, native SQL/two-child isolation,
worker/J1 ownership and cleanup. Actual C guest acceptance is not yet observed;
new performance, independent C reproducibility, adoption/integration and release
remain separate gates.

Actual C guest acceptance now passes on both macOS15 arm64 and Ubuntu24.04
x86_64 at host source6134274a in
[CI42437059943](https://github.com/masahitojp/mariamem/actions/runs/42437059943).
The [source-bound receipt](../benchmarks/lexerbinding/ci-42437059943/README.md)
records full638-table comparison/corruption, CRC, actual worker trap, forced J1
unsafe/protected/race controls, native SQL/two-child isolation and cleanup.
All108 installed runtime files excluding host-specific provenance match across
hosts. This closes the pending bounded actual-guest gate above, without changing
its immutable C origin b1a265cc or relabelling historical failures. Next is a
paired actual-C performance measurement; prior Go-surrogate timing is not reused
as a C-candidate speed claim. Adoption/integration and release remain separate.

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

## Disconnect notification adopted on main — unreleased

On2026-11-07 PR118 merged to main source_commit
`2434a536c50e5bd23129dd9940d6371e80a23366`, after Development42254980323 and
both-platform candidate42255365786 succeeded at
`a5fce7485cb4cb74cbc982c8c342a104f06c8ca6`. Both commits have the same Git tree.
The [saved acceptance receipt](reviews/issue117-notification-ci-42255365786/README.md)
keeps original source/platform identities and checksums.

WaitDisconnected now uses host session/failure notifications while preserving
context, Close and completed-disposal contracts. UCA is included in this tested
combination. Both-host checks cover focused handwritten races and real TCP/Pipe,
Snapshot/cap1 reuse; generated engine race instrumentation remains excluded.
Connection-retirement measurements are narrow, without a timing gate, and do
not establish a combined full-suite speedup over0.6.2. The prior single-Mac
performance/CPU tradeoffs remain in the
[candidate record](reviews/issue117-notification-candidate.md). Versioned release
qualification and publication remain separate.

## Current work tracking

Checked against GitHub Issues on 2026-11-05 after v0.6.2 publication. Issues own
live checklists; this is a direction summary, not a second acceptance ledger.

- **v0.6.2:** no open issues in its milestone. Prisma dogfood #92 is complete.
  The unofficial adapter #98 and MySQL8 parity #107 were closed as not planned;
  they are not unresolved release gates.
- **v0.6.x:** [#65](https://github.com/masahitojp/mariamem/issues/65) remains open.
  Its [source feasibility investigation](https://github.com/masahitojp/mariamem/blob/9c86d469de09a2426503b2578c3d743c2b29e574/docs/reviews/issue65-guest-wire-feasibility.md)
  is complete; an embedded-guest wire entry needs a separately selected experiment.
  No guest endpoint handshake/SQL execution or implementation is established.
  The shipped Go Pipe #66 does not implement guest-native wire relay.
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

## CRC32C optimization — main adoption approved, unreleased

On 2026-11-07 the Human accepted the adoption review and approved protected main
integration of the bounded CRC32C candidate through PR125. The accepted observed
tradeoff is Fresh P4 batch wall +51.944ms (approximately5%, all three pairs slower)
and Fresh P1 batch CPU +234.809ms, alongside Fork startup p50 improvements in all
six P1/P4 pairs (median paired -9.305/-10.731ms). The Fresh cause remains unknown;
this is neither a universal speedup nor an approximately1% regression bound.
No additional sampling or root-cause investigation is required for this adoption.
Main merge follows required checks/strict-base protection. Release/version
selection, experimental static-image sharing and broader format support remain
separate decisions.

The [candidate record](reviews/crc32c-candidate.md) preserves the initial
implementation approval, fixed exit and single-Mac comparison. Four technical
conditions are satisfied: canonical regeneration/input-drift checks; CRC and
validator equivalence/negative tests; supported-platform real SQL/isolation/
cleanup; and the finite product comparison. Generated-code ownership, guest and
converter pins, public API and completed-disposal guarantees remain unchanged.

[Runtime CI42349570517](https://github.com/masahitojp/mariamem/actions/runs/42349570517)
passed on macOS15 arm64 and Ubuntu24.04 x86_64 at
`bb894d6658cd575f8262736698d3e9ede7f67360`. The
[compact receipt](reviews/crc32c-ci-42349570517/README.md) records both job names,
IDs, artifact ZIP digests, original command/result/cleanup JSON and checksums.
The earlier dependency-failure run42345783454 remains bound to a2b960ab;
its receipt is not relabeled as success.

Changes after measured source `1057adf8fb430f5540f9d4f420f6b3f6f2012aa9`
are the qualification workflow dependency addition and its contract test, plus
records. `internal/`, `guest/`, `release/` and `scripts/` are identical (empty
Git diff); runtime bytes are unchanged. CI evidence remains bound to
`bb894d6658cd575f8262736698d3e9ede7f67360`; later record-only commits reuse it
on that explicit basis, not as a new exact-head execution.

Related work: #121's finite attribution is complete; #122 retains the candidate
list and CRC/PR125 disposition. Static-image sharing in #123 is a distinct
prototype and receives no product adoption from this decision. The measurement
branch remains separate from the minimal product PR.
