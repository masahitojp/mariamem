# mariamem project status

This document owns current state and approved direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns implementation, and [decisions](decisions/snapshot-product-contract.md) own
continuing constraints. GitHub Issues own actionable checklists and milestones.
Version themes and candidate adoption do not authorize a release.

## Issue156 — dictionary-wait product candidate authorized

On2026-11-12 the Human approved proceeding to a product candidate, prioritizing
an early comparison with the existing main baseline. The
[decision and fixed exit](decisions/dictionary-wait-notification.md) limits the
change to notification around contended dictionary-eviction lock acquisition.
The controlled mechanism and single-Mac fixed comparison support this direction;
uniform acceleration and complete natural-tail causal attribution are not claimed.
Build the minimal candidate from8df45792, retaining unchanged host/API/settings.
Canonical source bootstrap43246097319 passed at e3d020e5, including the
repaired dictionary preparation receipt. The [installed checkpoint](reviews/dictionary-installation/README.md)
records normal generated installation, unchanged worker/CRC/data bindings and
the actual-guest regression. Local runtime, daily/smoke, worker controls and
clean-source attribution pass. The installed-candidate fixed30 comparison is
complete with all observations retained. CI43318436823 passed two-build and
both-OS full regeneration, then failed daily Python checks before integration.
The [CI setup/selection repair](reviews/dictionary-installation/ci-43318436823/README.md)
passed fresh-environment Python checks. CI43330322013 now passes at a8389b6d:
two identical guest builds, full120-file regeneration on both OSes, daily/integration,
actual dictionary/worker regressions, SQL/children and cleanup. The [integration
review](reviews/dictionary-installation/integration-review.md) recommends the narrow
correction with the measured P4 regression retained; the Human integration decision
is still pending. No main merge or release has been performed.
The bootstrap remains
UNQUALIFIED; no old runtime or performance result is relabeled. Product adoption,
main integration and release remain separate.

## WASI timer correction and startup reduction — product candidate approved

On 2026-11-11 the Human approved the [timer adoption decision](decisions/wasi-timer-startup.md)
after reviewing evidence `d24087ee`, Mac paired measurements and Ubuntu/native
CI42940198738. Implement the SQL clock-selection correction and bounded
millisecond-resolution probe omission as separable changes from main.
Whole-suite acceleration remains unestablished and this limitation is accepted;
no uniform speedup or regression-free claim is authorized.
The canonical patch, normal regression tests and generated provenance must be
assembled before integration review. Canonical-source bootstrap CI42955063307
passed on498e186e and its checksum-verified receipt is retained in the
[product checkpoint](reviews/timer-product.md). Generated Go is installed and local daily/smoke checks pass;
independent two-build canonical reproduction and both-platform verification now
pass at37023152 in [CI42959675387](reviews/timer-product-ci-42959675387/README.md).
All118 generated files agree; timer TCP/Pipe Fresh/two children, CRC/UCA/lexer,
worker/J1, native SQL and disposal controls pass. Evidence/acceptance metadata
updates preserve the tested runtime bytes and original receipt source.
PR152 is ready for Human main-integration review. No new performance claim is made. Main integration,
Qualification and release remain separate. UCA work is not part of this candidate.

## Issue150 — versioned legacy preparation candidate (2026-11-10)

The Human authorized independent v0.7.0 preparation tooling for later13.x
adoption. [Candidate evidence](reviews/issue150-preparation/README.md) records
current12.3.3 selected/default and historical13.0.2 legacy full-source equality.
The existing resolver/pipeline is reused, with current UCA/lexer/startup steps
preserved. Canonical engine/runtime inputs remain unchanged; native wire and
prepared raw-row candidates are separate. Registration instructions identify
data-only changes and remaining patch/helper/binding review obligations.
Implementation and bounded verification are complete; main integration remains
subject to candidate review, and#150 is not yet complete. No13.x runtime adoption,
new guest build or release follows from source preparation PASS.

## Issue123 — process-lifetime static cache approved for candidate implementation

On 2026-11-10 the Human accepted retaining the immutable initial image for the
host process lifetime to prioritize total test execution time. Build it lazily
once; reuse it across DBs/Snapshots in that process. DB Close continues to dispose
all per-child workers, connections and mappings. Only the bounded immutable
image remains. Python sharing follows its existing per-lineage Go host boundary.
The [decision](decisions/process-static-image-cache.md) records retained resources,
failure ownership, generation checks and limits. Assemble the minimum product
candidate from main; experimental history is not merge-ready. Both-OS prototype
CI 42657516361 passed at 378f8490; product integration/adoption/release and new
performance claims remain separate gates.
The [product candidate checkpoint](reviews/process-static-image-candidate.md)
records local correctness, retained resources and the fixed-client profile gap.
Product candidate [CI42673922578](https://github.com/masahitojp/mariamem/actions/runs/42673922578)
passed on macOS15 arm64 / Ubuntu24.04 x86_64 at source_commit
`be08dac36194442d3cbbd95f0add7c002753ffa4`; its checksum-verified
[compact receipt](reviews/process-static-image-candidate/ci-42673922578.json)
keeps exact job/artifact identities. This is core runtime correctness, not the
fixed-client comparison, installed distribution, performance or Qualification.
The Human authorized the review's two bounded follow-ups: include embedded layout
metadata in module fixtures/identity and separate private diagnostics from copied
external-consumer tests. That follow-up at `845aeedb` kept runtime bytes unchanged;
Development [CI42723709945](https://github.com/masahitojp/mariamem/actions/runs/42723709945)
passed all three checks at that exact source. Old receipts retain their original
source. The PR subsequently incorporates main `c375edbc`, including the adopted
Issue145 shutdown behavior below. The combined runtime differs from the earlier
Issue123-only CI source; its normal Development checks include the existing
shutdown/Snapshot/reSnapshot smoke. Do not relabel earlier receipts as combined
head PASS. Main integration and release remain separate.

## Issue145 — shutdown mode by disposal purpose, adopted on main

On 2026-11-10 the Human approved proceeding after the bounded macOS experiment
recorded in [Issue145](https://github.com/masahitojp/mariamem/issues/145#issuecomment-6745782014).
Select `innodb_fast_shutdown=1` when taking a Snapshot, and `2` when discarding
a fresh/Fork DB. A Fork may itself become a clean Snapshot; generation origin
must not determine shutdown mode. The candidate uses a private host-controlled
session after client cleanup, preserving the canonical guest and public API.
The main-based candidate passes local full check, race, Go integration, Python
normal/Live and Snapshot checks. Exact-source macOS CI42670536897 at401def4e
closes fixed-profile prepared/native matching and reSnapshot/parallel-disposal
checks. Ubuntu daily/smoke CI42664665273 remains bound to e671f66a with identical
runtime/test bodies. The accepted PR head satisfies normal protected checks. Release remains
separate. See the
[implementation evidence](reviews/issue145-shutdown.md) and
[CI follow-up](reviews/issue145-shutdown-ci-followup.md).
The Human approved main adoption and a post-merge measurement on2026-11-10.
[PR146](https://github.com/masahitojp/mariamem/pull/146) squash-merged to source_commit
`8eded3625ebc22a3a52280bf7647a1056e3183af`; its tree equals the approved head
`b4e9bc4c6988ae2d1a2ea6ffc6151b395c59553e`. Normal protected checks passed in
CI42673914153 attempt2 (attempt1 was GitHub Internal server error); macOS receipt
42670536897 remains bound to401def4e with identical runtime/oracle bodies.
The [post-merge comparison](reviews/issue145-postmerge-measurement.md) on
Go1.26.10/macOS confirms1MiB-write Close reductions in all six pairs for fresh
and Fork. No-write/10MiB Close benefit and uniform complete-lifecycle speedup
are not established. Main adoption is complete; release remains separate.

The earlier historical statement that shutdown-mode changes were unapproved is
superseded only for this bounded implementation. No broad startup tuning is added.


## UCA default private-copy — accepted, canonical integration pending

On2026-11-12 the Human accepted the bounded default contraction/flags/hash
private-copy optimization, including the measured unfavorable P8 tradeoff,
and asked to complete main integration before further wait diagnosis.
[Decision](decisions/uca-default-private-copy.md) and
[canonical candidate stages](reviews/uca-copy-canonical.md).
The candidate starts from main500020e7 and migrates only the accepted source
patch. Experimental guest acceptance does not constitute canonical main adoption.
Stage1 CI43185761193 passes exact guest/linked identity at c4c60eda. The normal
generated runtime and strict worker/CRC bindings are installed. Two identical C
builds and both-platform canonical acceptance passed at 6da771df in
[CI43190662084](reviews/uca-copy-ci-43190662084/README.md). PR157 Development
checks found an outdated test-only init-flag address after data relocation. The
fixture is corrected with explicit flag/page preconditions; production runtime
bytes are unchanged. Protected merge remains pending new required checks.
#140/#156 retain the residual
PREPARE investigation independently; NOT_REPRODUCED is not a fix. No release is
authorized and no uniform complete-suite performance improvement is claimed.

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

## v0.7.0 — Prepared lexer maps integrated on main, unreleased

On2026-11-08 the Human accepted the recommendation to adopt the bounded
prepared lexer-map candidate reviewed at source_commit
`8d5f8284cedde31751d4e53e52ddfd61f69432ab`, against main
`3d8b2201c1f36fa5b7264e0450104055f3822272`. The
[decision](decisions/prepared-lexer-maps.md) accepts serial Fork/CPU improvements
with the stated P4/RSS limits. No new performance campaign was added.

The minimal canonical product candidate now passes at source_commit
`b04b49dbc3dee5e2773b8d775d2202ca1eccff92` in
[CI42463414255](https://github.com/masahitojp/mariamem/actions/runs/42463414255).
Two independent C builds reproduce the reviewed guest/linked bytes; macOS15 arm64
and Ubuntu24.04 x86_64 independently regenerate identical110-file inventories.
Both hosts pass full638-table equality/corruption/profiling separation, UCA,
CRC, actual worker failure, forced J1 controls,18 build-evidence mutations,
normal/binary-prepared SQL/native comparison, two pristine children and cleanup.
[The checksum-bound receipt](reviews/lexer-canonical-ci-42463414255/README.md)
retains exact source/job/artifact identities. Development42463420122 also passes
at b04b49db. This is bounded candidate acceptance, not release Qualification.

Stage1 CI42448601842 remains pinned to fd615a53, and the original experimental
CI42437059943 remains pinned to host6134274a / C origin b1a265cc. Neither is
relabeled as the canonical source. Acceptance follow-ups changed documentation,
the build ledger, fixture status metadata and GitHub display attributes; tested
runtime, guest, adapter, workflow and test-body bytes stay equal to b04b49db.

On2026-11-08 the Human approved the
[main-integration review](reviews/prepared-lexer-main-integration-review.md).
[PR136](https://github.com/masahitojp/mariamem/pull/136) squash-merged to main
source_commit `9003f0febea952a4117de9964991b9f032ad76bf` after required
check/integration/Live required gate all passed in
[Development42468613070](https://github.com/masahitojp/mariamem/actions/runs/42468613070)
at PR head `65e70eea0670fa48a10235c519af66c0b48ca7f1`.
The merged main and approved PR head have identical Git tree
`956cc89c9152b16a4f1128536eeb21f2d64daad5`; strict freshness and admin protection
were retained, with no bypass. The final tree retains compact receipts and
GitHub generated-diff attributes. Main integration is complete; no new runtime
measurement, Qualification, version selection or publication is authorized.
P4 whole-batch/RSS/Ubuntu speedup and actual dynamic XML-loader runtime coverage
remain outside the accepted claim.

## v0.7.0 — Normal startup concurrency: adopted on main

On2026-11-09 the Human chose to advance the #140 startup-concurrency mitigation
to a production adoption candidate. Keep normal global thread-pool concurrency
through buffer-pool startup loading and redo application, while retaining read
group1 and buffer pool16MiB. The [decision and fixed exit](decisions/startup-global-concurrency.md)
record the two-call canonical patch, original source-bound evidence and limits.
The8MiB candidate (#88) is separate and is not adopted by this direction.

The generated-Go spike supports this intervention but does not prove stable
variance reduction or eliminate long PREPARE waits. Its observation-disabled
CPU median increased1.7%; resource results and residual waits remain explicit.
[Bootstrap CI42509593737](reviews/startup-cap-ci-42509593737/README.md) passed
at8d3da071 as one UNQUALIFIED C build. The
[canonical installation](reviews/startup-cap-installation/README.md) selects guest
8e3761ea; clean installed source1b446e53 passes bounded local CRC, actual
UCA/lexer/worker, Snapshot/Fork/Close and attribution checks. Complete static data
and protected worker/CRC bodies are unchanged.
[Canonical CI42531554501](reviews/startup-cap-ci-42531554501/README.md) passed on
source `d3cc48076dc9f74253e7a16ebe09d323d706e72a`: two equal independent C builds,
110-file regeneration on macOS15 arm64/Ubuntu24.04 x86_64, actual CRC/UCA/lexer/
worker controls, J1, native SQL, two children and cleanup. These close the
canonical correctness conditions, not performance or release acceptance.
The Human approved main adoption after review. PR141 was squash-merged as
`32e3329c8f12ade2062f7acb5c8c8794457b5709`; its Git tree equals the reviewed
head `e88f4e35977cd711f3ef13deba69b0d6d9d4f947`.
[Development42623097766](https://github.com/masahitojp/mariamem/actions/runs/42623097766)
passed check/integration/Live required gate on that head. Strict base and admin
protection remained enabled; no bypass was used. The earlier automatic-trigger
failure42531563986 was repaired without weakening its policy oracle. Canonical
receipt42531554501 remains at d3cc4807: runtime/generated bytes and acceptance
execution steps are unchanged through the adopted head. Main adoption is complete;
Qualification, version choice and publication remain separate.

The Human next authorized a bounded read1/read4 comparison against this merged
main, with normal startup concurrency and16MiB fixed. The
[experiment plan](https://github.com/masahitojp/mariamem/blob/473b857bbc12713a0c2e612d1cf32858b3ddf503/benchmarks/read4afterstartup/plan.json) fixes one Mac/Go Pipe/P8,
cap9, the existing70-case shop fixture, five alternating pairs, caller phase timing,
CPU/RSS and cleanup checks. The completed [comparison](https://github.com/masahitojp/mariamem/blob/473b857bbc12713a0c2e612d1cf32858b3ddf503/benchmarks/read4afterstartup/results/README.md) found
read4 whole median569.054ms versus read1 538.775ms, with2/5 paired wins;
all correctness/cleanup checks pass. This misses the predefined benefit screen.
Keep read1; three long read4 PREPAREs have unknown waiting ownership.
No read4 adoption or stable tail/resource claim is made.
#140 remains open for residual waits; #88/8MiB remains a separate decision.

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
