# mariamem project status

This document owns current state and future direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns current HOW, [decisions](decisions/snapshot-product-contract.md) own
continuing product constraints, and reports preserve historical evidence.
Version themes are direction; they are not release approval.

This document keeps approved scope, decisions and evidence context. For work
linked to a GitHub Issue, that Issue owns actionable checklists and completion
tracking, grouped by release milestone; link it here rather than maintaining a
second checklist. An accepted-limitation Issue is not automatically release-blocking.

The current published release and later main changes are distinct sources.
Changing version metadata does not itself publish a release.

## CI cost reduction — daily reuse adopted; consolidation 1–4 authorized

[PR35](https://github.com/masahitojp/mariamem/pull/35) moved heavy product acceptance
to Release CI, and [PR36](https://github.com/masahitojp/mariamem/pull/36) merged as
source_commit `55b09c3ae78f98d1b989cdc5d82bfa33ba96b72b` after all required checks
passed. PR36 shares one checkout/Go cache across source checks and smoke. Its
[run](https://github.com/masahitojp/mariamem/actions/runs/41072335740) took 10m06s
wall time and 9m58s summed job time; smoke took about 4s. PR35 took 8m52s wall and
12m56s summed job time. Both missed compiler caches; this is not a controlled
before/after benchmark or proof of shorter overall waiting.

The Human subsequently authorized all four inventory recommendations:

1. Classify the reviewed pure CI-policy tests as tooling, so editing them does
   not itself launch Go/runtime work. Unknown inputs remain conservative.
2. Daily Go checks target product root/cmd/internal/fixture packages; benchmarks,
   documentation examples and standalone acceptance programs keep their complete
   package checks in Release. Handwritten vet stays complete; pure generated pN
   packages retain build-tag checks daily and full applicable analysis at Release.
   Generated-source/license checks and representative smoke remain daily.
3. Build one wheel per supported OS in Release and distribute that exact wheel
   and its embedded host to candidate qualification and all six feature suites.
   Consumers check source, platform, wheel/host hashes and embedded Go identity;
   reuse restores authenticated frozen inputs, never rebuilds on a miss. The
   shared build runs alongside guest reproduction, before feature acceptance;
   final qualification still requires canonical guest/source reproduction.
4. Retire eight historical experiment workflows and their automatic triggers.
   Preserve reports and source-pinned workflow links. Keep runtime qualification
   as a manual-only compatibility path because runtime reuse still references it;
   its old experiment-push trigger is removed. Retired GitHub registrations are
   disabled separately; no existing run or historical evidence is deleted.

This follow-up retains `check`, `integration`, and `Live required gate`, with no
protection bypass. Full core/race and both-OS feature acceptance remain required
at Release; platform/browser/ORM/fault-specific failures may be detected then.
One release dispatch remains sufficient; no separate candidate acceptance is
required.

The Human then prioritized Release-side unit deduplication and exact-READY feature
reuse over further Development trimming. This follow-up uses the existing
artifact authentication and guard path; it does not start qualification or
publication. Its question is whether repeated feature execution can be removed
without accepting incomplete or different-source evidence. Evidence is bounded
to workflow/helper inspection, deterministic mutation/selection tests and the
shared unit suite on Python3.11/3.14. No heavy CI submission is needed for this
implementation; unresolved hosted behavior remains explicit rather than adding
an unrequested release run.

Pure routing compatibility, preparation receipts and dump policy/binding oracles
have one shared owner at each supported Python/pytest boundary. The Human also
authorized the remaining portable feature-unit consolidation: P1 native/fixture
design mutations, Live observation oracles and Django owner/receipt mutations
join that owner; Live drops its repeated routing compatibility invocation. The
ownership check covers all six callables. Dump drops the native producer's
source-only repeat while keeping installed-wheel tests on both OS/Python minors.
Live's real process/pipe/signal/socket controls and all installed/runtime feature
cases retain their platform/interpreter owners; core full pytest retains its
independent baseline. Fresh release qualification still runs
all six feature suites. After both-platform READY and complete feature success,
CI records the exact source, final asset hashes, original run and all required
results in an authenticated artifact. Automatic READY reuse skips the shared
runtime/unit jobs and six features only after that original proof validates.
Absent, old, expired or invalid feature proof reruns features while preserving
valid core READY reuse. Reuse never renews original evidence expiry; a proof
lost after selection fails aggregation. Explicit recovery modes continue to
run features. Publication and public smoke retain their existing guards.

The implementation is locally verifiable without a new product build. Hosted
full/READY-reuse execution and time savings remain unmeasured. See
[development](development.md#local-verification) and
[release responsibility](releasing.md#ci-inputs-reuse-and-acceptance).

## CI strategy follow-up — release preparation and final publication ownership

After PR39 merged as source_commit
`adde9d63ea1dce82246b54e95c5250e23aea57f7`, the Human authorized three further
changes: focused local release preparation, one final aggregate guard inside
publication, and explicit classification for all maintained workflows. Exact-READY
feature reuse remains a retry optimization; a new candidate still needs its own
qualification. No release version or qualification/publication run is authorized
by this CI maintenance task.

Release preparation accepts only its existing version/documentation file set and
runs `release_preparation_checks.py` regardless of runtime-reuse intent. It never
runs local Go/full runtime checks as a prerequisite to submission. Explicit runtime
intent is still authenticated before push, and Release CI retains full or
validated-reuse qualification.

The publisher authenticates the aggregate READY ZIP and exact candidate/evidence
run references, restores both platform handoffs with the existing digest/path
checks, then recomputes the complete aggregate guard once before staging or any
remote mutation. It compares that result to the authenticated READY, verifies
staged asset hashes, and retains remote identity/upload/public-smoke checks.
Private transport-only helpers create no PASS/READY receipt and have no bypass
CLI. Normal restore/guard consumers keep semantic verification; guard-only restore
no longer repeats build/source/wheel validation already performed by its guard.

The nine current workflows have explicit tooling scope. Mixed runtime changes
and unreviewed paths still select the daily runtime profile. The inventory test
requires every added workflow to receive an explicit classification. This closes
the PR39 classification gap: three feature workflow edits had unnecessarily
selected Go compilation on a cache miss. Its completed Development run took
8m11s; this observation is not a prediction of the follow-up's timing.

Validation uses focused release/transport/selector tests and the canonical local
preparation check. Heavy Release submissions remain zero; both-OS hosted
publication execution and time savings are still unmeasured.

## Release guard consolidation and core compiler cache — implementation authorized

After PR40 merged as source_commit
`ce66b9df2067c546c88f6748fcbce2dc175a619a`, the Human approved proceeding with
recommendations 1 and 2 of the next CI inventory: consolidate repeated guards
within Release stages and retain candidate core/race compilation across runs.
The later proposal to parallelize guest reproduction and core qualification,
and remove the cross-platform candidate barrier, remains separate work. Remaining
feature-unit ownership cleanup is also outside this implementation.

READY selection, reused platform verification and aggregation now use a combined
authenticated restore and complete guard. Each stage runs its semantic guard
once per platform; publication retains its own final guard. The combined CLI
writes NOT READY on transport, guard or staging failure, replacing stale READY.
Candidate helpers predating the combined command retain the checked legacy
restore/guard sequence. No public unchecked-restore option is added.

Candidate core/race compilation has a separate cache namespace from wheel builds,
scoped by OS, architecture, Go toolchain, module inputs and candidate source.
New candidates may restore older compiler outputs, but clear test results before
qualification. Successful qualification saves the expanded cache, including race
compilation; cache misses/outages still run the full checks. Exact-source frozen
assets, clean external consumers, guest reproduction, both-platform acceptance,
final publication and public smoke keep their existing checks.

Validation is bounded to tooling/transport tests, workflow shell branches,
workflow lint and source-boundary checks. No heavy Release run or publication is
part of this work. Hosted cache hits, cold/warm savings and the complete updated
Release path remain unmeasured; no additional qualification run is a prerequisite
created by this optimization.

## Release qualification parallelism — implementation authorized

After PR41 merged as source_commit
`cff1fd779fdf35a1f33775b9866cf78f3c09f74c`, the Human authorized recommendation 3:
start core qualification alongside guest reproduction and remove the cross-OS
candidate barrier before external-consumer verification. Remaining feature-unit
cleanup is separate work. This changes scheduling, not the accepted test coverage,
candidate identity or publication decision.

The core jobs consume the existing exact-source shared wheel and tracked generated
Go after shared runtime preparation; they do not wait for canonical guest builds.
Each OS then freezes only after its own core job and the canonical guest job
succeed. Freezing rechecks the shared wheel, generated sources and complete
guest/corresponding-source evidence. External-consumer verification starts after
that OS's frozen handoff, in its existing separate runner and isolated consumer
environment. Core cache ownership and fresh test execution remain as in PR41.

The final `verification` join requires both OS paths. Full mode additionally
requires guest reproduction, both core jobs and both handoff jobs to succeed;
reuse/recovery modes require those full-only jobs to be skipped. Missing, failed,
cancelled or unexpectedly skipped work blocks the join and therefore READY.
The existing feature gate, immutable handoff/evidence names, qualification run
references, final publication guard and public smoke remain compatible. An
explicit runtime-reuse proof is transferred from each successful core job and
authenticated again by the existing frozen-proof verifier before packaging.

Evidence is bounded to existing source/workflow inspection, actual gate/shell
execution with synthetic results, dependency and shared-step checks, and the
canonical focused preparation checks. Heavy CI submission budget is zero for
this maintenance task. Hosted scheduling, cold/warm timings and end-to-end
Release completion remain unmeasured; no speedup or new release approval is
implied by local PASS.

## Issue #5 host repair — adopted on main, unreleased

The Human approved main adoption of candidate source_commit
`8383f09b4043eafed07fcb048f8edcbde30d0c6a` after Development
[CI40737308463 attempt2](https://github.com/masahitojp/mariamem/actions/runs/40737308463/attempts/2)
completed successfully. Both-platform worker-failure/native-equality acceptance,
normal integration and full check are successful. Attempt1's hosted-runner
communication failure remains recorded; its cause is not established.

The bounded repair binds `Fd_dup` to the existing descriptor implementation and
notifies fatal worker traps promptly. The affected DB becomes unusable; pending
calls retain the original cause; joining still precedes resource release.
Other DB instances remain independent. Non-cooperative Go workers retain their
resources until they exit. The other14 panic imports remain fail-closed.
Guest source, public API and Live/Snapshot product contracts are unchanged.

See the [adoption review and conditions](reviews/issue5-main-adoption.md),
[repair report](reviews/issue5-host-repair.md) and original
[investigation](reviews/issue5-text-dedup.md). [PR14](https://github.com/masahitojp/mariamem/pull/14) squash-merged to main
source_commit `ca67dcacaf2d96b040f0e312cdf60aab85abd99d` from checked head
`e9c77c1b7a2f66a9aef7cb6fbdfde1c4921bcf0f`; their trees are identical.
The integration retains main's intervening CI changes. Final PR Development
[40778348981](https://github.com/masahitojp/mariamem/actions/runs/40778348981),
Live [40778348966](https://github.com/masahitojp/mariamem/actions/runs/40778348966),
Django [40778348956](https://github.com/masahitojp/mariamem/actions/runs/40778348956)
and dump [40778348959](https://github.com/masahitojp/mariamem/actions/runs/40778348959)
checks succeeded; strict app-bound check/integration/Live gates were respected.
The earlier macOS runner-capacity cancellation and CI-rule integration failure
remain historical failures, not runtime acceptance. PR worker acceptance runs
on Ubuntu; main/manual retain both hosts, with original both-host candidate
acceptance separately identified above. Issue5 is closed by the merge. These
receipts do not qualify a later release/main build. No protection bypass,
release qualification, version selection or publication was performed.

## Dogfood recipes, guides and CI improvement adopted on main — unreleased

The Human approved main adoption of PR3's bounded candidate
`d389306f9ae0514824f79fccbe2800776786a7ac`: the ordinary Django standard-runner
recipe, public Python browser/Go HTTP Live examples, sequential/parallel
Snapshot/Fork documentation and Live CI deduplication/compiler-cache changes.
The starting main base is `250bceb80be4cfc9f7c844d888af864fc1d38d25`.
PR3 squash-merged on 2026-10-27 to main source_commit
`ebb97260788710b2065e81481b2c2f516d6f7e52`, from checked PR head
`0490b43a21dceeab10b33d94b5b92bf383e4055e`. The actual final PR CI source was
`730bd17c935928dd37e2cd7df14aa115c40e89a7`; all three have identical tree
`c98a74c854d59cf19f1584a7cb5fa994e0f6632b`. See the
[decision](reviews/v06x-dogfood-main-adoption.md) and
[completion receipt](reviews/v06x-dogfood-main-completion/README.md).
This closes the approved protected-PR integration; no bypass was used.

The reviewed actual PR CI source is `3ed2c8e0790499c215869e33154272b062c35a88`,
whose tree matches that candidate. Development40492425939, Django40492425975,
Live40492426087 and incidental dump regression40492426188 all succeeded.
Django has native references for both Python minors plus four guest cells;
Live has both-host public examples, failure controls and installed consumers.
The final strict-base PR checks also passed: Development40502167065,
Django40502166621, Live40502166546 and dump regression40502166708. GitHub's
20 successful checks bind the PR head; execution/receipt provenance retains the
actual CI merge SHA above. The selected code matches reviewed d389306; later
changes only record documentation/evidence. Post-merge API readback confirms
all three app-bound required contexts, strict freshness and admin enforcement.

Accepted limitations: the new manual parallel guide snippets were checked
statically, with existing parallel runtime anchors retained; their exact
execution is not claimed. Django's workflow is not a required protection context.
Live's new compiler caches missed on the first run and saved successfully;
the final PR run restored the native and both host caches. Observed host-job
times fell, but a controlled cache-only speedup remains unmeasured.
Multi-alias/parallel/async or arbitrary
Django projects and blanket compatibility are outside this recipe evidence.
The existing three required contexts, strict freshness, administrator enforcement
and guide-only skip policy are unchanged. No product/runtime/guest/generated or
release ledger change is included. Qualification, version and publication remain
separate Human decisions.

The next independent Django input investigation (2026-10-28) recommends
Oscar4.2.1's sandbox, source_commit `d0a70850abf8e4229d4971aa7e8f4643326ec9f3`.
The [source-selection and acceptance proposal](reviews/v06x-independent-django-input.md)
pins inspected source/fixture/migration inputs and records native-first gates.
This investigation installed or ran no upstream code: dependency locks,
native references and all new guest cells remain NOT_RUN. Execution and any
later adapter/runtime change remain separate decisions; existing Django/Live
adoption is not reopened.

## Live endpoints adopted on main — unreleased

The Human approved both the previously applied protection and the selected Live
candidate. [PR1](https://github.com/masahitojp/mariamem/pull/1) squash-merged on
2026-10-27 to main source_commit `212bb07ffb8e89669c32d6b5a7ba94fc7aa18b2c`,
from starting base `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4` and approved PR
head `fcc6bd856867afdf5909c8fec4abd5c586ec434e`. The actual PR CI source was
`cf3991234efa3897a7a50466b07e29a97af2aa7c`; its tree matches the PR head and
landed squash commit. CI receipts retain that source, not a relabelled main SHA.
See the [Human decision](reviews/v06x-live-main-adoption.md),
[adoption recommendation](reviews/v06x-live-correction-adoption-review.md) and
[completion receipt](reviews/v06x-live-main-integration/README.md).

Development CI40448056712 and Live CI40448056639 passed the protected PR's checks.
The latter includes fresh native MariaDB12.3.3 references, both guest host OSes,
Python3.11/3.14 public Go/Python browser and failure controls, installed consumers
and the always-reported aggregate. Both host canonical checks have 1083 PASS/
45 explicit SKIP/76 subtests. The new 12 ordinary-operation interruption tests
run on canonical Python3.14; the separate local 99-case runs on both minors remain
separately identified. The original local Python3.14.9/OpenSSL4.0.3 Connector
import FAIL is retained and documented; CI OpenSSL3 does not qualify it.

Post-merge API readback confirms `check`, `integration` and `Live required gate`,
all bound to GitHub Actions app 15368, with strict freshness and administrator
enforcement. No bypass or exploratory-history merge occurred. The selected
runtime matches reviewed candidate c1ee8d3; subsequent integration changes are
documentation/evidence only. Published v0.5.3 does not include Live. Caller work
quiescence and physical SQL connection retirement remain required before Reset.

Separate post-adoption decisions remain open: observe one actual guide-only skip
or explicitly accept the unit model; decide whether docs/reviews-only PRs belong
in the skip allowlist; decide whether to expand Go/native interruption coverage.
No option has been silently selected. Qualification, version and publication
remain separate Human decisions and were not started by adoption.

## Product contract

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB, uses normal connections and commits/rollbacks, then discards
the DB. Expensive migrations/fixtures may be prepared once and reused as a fixed
Snapshot baseline. What is shared is the initial state, not previous tests'
mutations. Fork creates an independent mutable DB; a modified child can create
a new baseline without changing its parent.

Normal user entry points are acquisition functions and test-per-database fixtures.
Successful Snapshot consumes its source; rejected busy/transaction preconditions
preserve it. Close boundaries remain explicit.

The maintainer approved D block storage plus one automatically managed Python
host per root lineage on 2026-10-16, and then removed public persistence/loading
from the implementation scope. Baselines become process-local; preparation inputs
remain migrations/seed. Child independence and consuming Snapshot are retained.
The maintainer approved main adoption on 2026-10-17 for reviewed candidate
`f55bd3a91073e9f80b8a816055acf0983b8b2e79`. Its runtime matches the bounded
macOS arm64 verification and native Ubuntu CI, which passed on source
`4282cba73f12c772942b72c2f020b3ec1228be11` in
[run 38908979283](https://github.com/masahitojp/mariamem/actions/runs/38908979283).
The shared-host crash domain and intentional public save/load API removal are
accepted for this use. That v0.5.1 performance comparison remained macOS-only;
the later [native Ubuntu campaign](reviews/ubuntu-product-performance-results.md)
confirmed the Snapshot gain on Ubuntu x86_64 (see the Snapshot stopping point
below). The earlier
slow resource-observed small-fixture trial is preserved; the later bounded
comparison did not reproduce it in 30 ordinary and 30 resource-observed candidate
repeats. Its cause remains unknown, rather than classified as noise or a defect.
Skipped probes remain explicit. The later authorized final configuration
Qualification passed for exact source `c97e55fc065f6ee7b560325077726da53e5d95d7`
in [verify run 38935990860](https://github.com/masahitojp/mariamem/actions/runs/38935990860).
Both native platforms and the aggregate guard returned READY after full builds,
regeneration and external acceptance. The [Qualification review](reviews/main-storage-qualification.md)
retains receipts/SKIPs. The subsequently authorized
[user-workflow/performance check](../benchmarks/main-product-verification.md)
completed 274 executions on those exact runtime inputs. Typical fixture reuse
and memory improved, while 100 MiB Go Fresh retains adverse results (all four
observations: median +7.2%). The [Product Verification Human Review](reviews/main-product-verification.md)
recommended accepting that tradeoff. The maintainer accepted the performance
review and authorized preparation/release as **v0.5.1** on 2026-10-17, explicitly
deferring the 100 MiB Go Fresh investigation until after release. Release CI
owned acceptance of the exact final-version source and its publication;
neither the earlier READY nor these measurements are relabelled as that source.
See the
[implementation results and Human Review](reviews/d-heap-shared-host.md) and
[approved design and scope change](reviews/d-heap-productization-design.md).

## Routine support adopted on main — unreleased

On 2026-10-20 the Human approved main adoption after the
[Human adoption review](reviews/routine-canonical-ci-review.md). Main fast-forwarded
to `429492fd35bc48948576b21cb3804726ced3c03a`, which contains the tested routine/text
candidate `03184a61a63b1977a1d05ed378404f59d57cf68e` plus evidence and build-ledger
updates. The subsequent documentation commit records this decision; runtime,
guest/converter inputs and generated provenance remain identical to the tested
candidate. No exploratory history was merged.

Procedures/functions and bounded DEFINER are included, together with the
product-managed mysql.proc structure boundary and necessary text multiple-result /
option paths. Packages/package bodies remain outside support/testing; events
remain an embedded restriction (1235). DEFINER metadata is retained, but account
existence/privileges are not enforced under skip-grant-tables. See the
[scope decision](decisions/routine-support-scope.md) and
[candidate report](reviews/routine-canonical-adoption.md).
Binary prepared was not adopted at this routine milestone. Its subsequent
P1–P6 completion and main adoption are recorded in the final P6 entry below.

[CI39406398732](https://github.com/masahitojp/mariamem/actions/runs/39406398732)
passed independent two-source-build reproduction, all99 generated files on macOS
arm64 and Ubuntu x86_64, required Connector/Python26.7.0, J1 failure/control
oracles and existing ORM consumers on exact candidate03184a6. These are candidate
receipts, not Qualification of a later main/release SHA. Target version, final
Qualification and publication remain separate Human decisions and were not
started by main adoption. Published v0.5.3 below does not include this work.

## Current published release: v0.5.3 — Reuse successful macOS platform checks

[v0.5.3](https://github.com/masahitojp/mariamem/releases/tag/v0.5.3) was published
on 2026-10-18 (JST) from source `4f7b18bfc00965974fcbb16ac49cbf00d9fb2b0e`.
[Release CI 39115376954](https://github.com/masahitojp/mariamem/actions/runs/39115376954)
completed independent guest builds/generated-Go reproduction, both-platform
acceptance, aggregate guard, publication and public Go/wheel smoke successfully.
The product runtime change since v0.5.2 is the macOS platform-check success
cache (`internal/artifacts/platform_cache.go`). Public APIs, guest and Snapshot
ownership remain unchanged. See [release notes](../release/NOTES-v0.5.3.md).
The macOS product comparison against v0.5.2 remains on
`experiment/product-main-macos` at `94f13e6`; integrating that measurement report
is a separate decision. v0.6 planning follows this published boundary.

## Previous release: v0.5.2 — Snapshot ownership without repeated content scans

[v0.5.2](https://github.com/masahitojp/mariamem/releases/tag/v0.5.2) was published
on 2026-10-17 (JST) from source `47f297cc7498625e076abb93322eb616c9560bb8`;
annotated tag object `2e98dee0ca94abe95dcef8351b71f7726320bf12`.
It seals the source's same private backing instead of reconstructing the ordinary
heap baseline and repeatedly reading all file contents, reducing Snapshot
creation work. Public Go/Python API signatures, MariaDB 12.3.3, supported
platforms and minimum Go version are unchanged from v0.5.1. Ordinary heap
acquisition no longer performs a full content scan to detect faults that directly
alter private bytes between freezing and acquisition; it validates identity,
state and structure instead, while strict digest-bearing imports, cross-host
transfer and borrowed-mapping lifetime detachment retain their content checks.
See [released notes](../release/NOTES-v0.5.2.md) and
[changes since v0.5.1](changes-since-v051.md). The adoption history below records
the main integration that preceded this release.

## Previous release: v0.5.1 — In-memory baselines and shared host

[v0.5.1](https://github.com/masahitojp/mariamem/releases/tag/v0.5.1) was published
on 2026-10-17 (JST) from source `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`;
annotated tag object `089b32e09608902f6d46e7ab9527d09922dcf065`.
The [typed baseline pin](../release/baselines/v0.5.1.json) separates these identities.
It includes the startup ordering correction, D block backing, Python shared host
and public save/load API removal. See [released notes](../release/NOTES-v0.5.1.md)
and [API migration](changes-since-v050.md). The ownership optimization recorded
below was subsequently released in v0.5.2; v0.5.1 evidence does not qualify it.

## Previous release: v0.5.0 — MariaDB 12.3.3

[v0.5.0](https://github.com/masahitojp/mariamem/releases/tag/v0.5.0) was published
on 2026-10-13 from source `44100ec676c8c9064f32f3a01bd9a990d487bb61`;
annotated tag object `bfd854da1cecbe71ad761d1578b3f2c710a1c07f`.
It adopts MariaDB 12.3.3, dynamic handshake version and the bounded correctness
repairs. Its public Go/Python APIs and file-backed Snapshot persistence were
retained. See the [released notes](../release/NOTES-v0.5.0.md).

The startup ordering correction, D block backing, Python shared host and public
save/load API removal were subsequently released in v0.5.1. The earlier v0.5.0
preparation history below does not qualify later main commits.

## Adopted ownership optimization — released in v0.5.2

On 2026-10-17 the maintainer explicitly accepted the limited Snapshot ownership
contract and authorized the minimal FileStore/Root/capture-binding implementation,
adapters, independent byte reference/substitution/lifetime/generation tests.
Normal API immutability, same backing, child isolation, strict Heap/transfer
validation and mapped lifetime detachment remain required. Ordinary heap
acquisition does not promise full-scan post hoc detection of private-byte faults.
The maintainer subsequently approved main integration in Human Review.
The separate release decision followed and published the optimization as v0.5.2
above. See the [contract](decisions/snapshot-product-contract.md) and
[productization report](reviews/snapshot-owned-root-productization.md).
The experiment history is not merged into this branch. Productization development
verification passed on exact source `890f770eee36c004036826104229f9269138775b`
for macOS15 arm64 and Ubuntu24.04 x86_64 in
[run39000948512](https://github.com/masahitojp/mariamem/actions/runs/39000948512):
canonical check and integration on both, including the mapped-child derived baseline.
After the [integration review](reviews/snapshot-owned-root-productization.md),
the Human approved the fixed candidate. Main was fast-forwarded from
`7a82f338cf111d5d52538b5a3f7bf129c12e2dbb` to
`52c078ba2fd5a38340ec5eb42a83853b258d7435`, with Git tree object ID
`02da8809cd9aa76ff3769af268134b90675a68a7`. The review-only head was not merged.
The [integration identity record](reviews/snapshot-owned-root-productization-evidence/integration-target.json)
pins that candidate's commit and tree, the CI source it builds on and the exact
difference set. Relative to CI source 890f770, that candidate changes
documentation/evidence and Go line comments only (four Go files); executable
behavior, tests and build inputs are unchanged. This follow-up records adoption,
corrects the published-release status and stale architecture/Acquire wording
without changing executable code, and adds one more comment-only Go file
(`internal/snapshot/owned.go`); the current runtime source therefore differs from
CI source in five comment-only files. The full Git tree differs from both the
integration candidate and CI source. Historical review/CI evidence remains under
its original source identity.
The v0.5.1 baseline pin is retained as a separate release ledger entry.
The narrowed detection guarantee recorded in [changes since v0.5.1](changes-since-v051.md)
is published in the v0.5.2 notes above. Prior Qualification and spike
regeneration results are not relabelled as the final v0.5.2 source. Release
Qualification and independent regeneration for the exact final source were
CI-owned and separate; the CI development PASS recorded here is not itself
release readiness.

**Snapshot optimization stopping point:** the observed Light Snapshot median
fell from 204.8ms on v0.5.1 to 2.85ms on the ownership candidate in the same
macOS comparison. No further Snapshot speed optimization is planned.
This is an investment decision for the measured workflow, not a claim of a
universal lower bound. Remaining Light serial time is mostly child startup/use:
child Fork median 59.4ms (40 child observations), 4-test total median 364.0ms.
The approximately 3.08ms diagnostic capture is from the candidate, not v0.5.1;
measured/diagnostic cohorts are not combined. These medians are quoted from the
adoption-source macOS measurements and remain macOS investment figures, not a
cross-platform lower bound. The separately authorized
[native Ubuntu campaign](reviews/ubuntu-product-performance-results.md), now
integrated on main, independently confirmed the Snapshot gain on Ubuntu x86_64
and recorded the mixed large-Python whole-workflow results.

## Previous release: v0.4.7 — Upstream converter migration

[v0.4.7](https://github.com/masahitojp/mariamem/releases/tag/v0.4.7) was published
on 2026-10-11 from source `e0be06f3a20c72cbb5a9be27971280c80a3ec357`;
annotated tag object `c201bf577440440253155e665def9c25ac5064f0`.
It adopts pinned goccy/wasm2go plus nine maintained patches on the unchanged
13.1.0 guest. Its published source is the A–D execution baseline; the former
candidate notes below preserve preparation scope. A–D changes were unqualified at that stage; later Qualification and
Product Verification are recorded below.

## Previous release: v0.4.6 — Product usability and validation

[v0.4.6](https://github.com/masahitojp/mariamem/releases/tag/v0.4.6) was published
on 2026-10-10 from source `b56be17206b6beef18f55c8ea39b254638da8590`;
annotated tag object `09d7b82e1900318dde45d08bebd9328ea35e6ef7`.
The [release run](https://github.com/masahitojp/mariamem/actions/runs/38040418075)
passed source reproduction, both native platform artifact/consumer qualification,
aggregate READY, publication and public smoke on macOS15 arm64 and Ubuntu24.04
x86_64. The released tag peels to that exact source; main matched it at this
post-release documentation review. These results qualify the released source,
not later documentation commits.

Go `LoadSnapshot(ctx, path, opts)` completes persisted-baseline acquisition.
Go/Python guides and [bounded product comparisons](../benchmarks/v046-product-validation.md)
cover Fresh, preparation reuse, optional persistence and independent children.
Go minimum 1.26.0, mysql client v1.9.3, guest, generated runtime and Snapshot format
remain unchanged. That release was validated with Go1.26.8 and Python3.14; accepted
Go1.27 consumer scope is documented in [compatibility](go-compatibility.md).
No Snapshot or filesystem optimization is included.

The earlier [integration verify run](https://github.com/masahitojp/mariamem/actions/runs/38033500776)
qualified source `8c07a9bd3278f7c8d2c633c38b7c41377d43100a` with private 0.4.5-labelled
artifacts. It is historical preparation evidence, not the final v0.4.6 artifact
identity. See [integration history](reviews/v046-release-qualification.md) and
[release notes](../release/NOTES-v0.4.6.md).

## Previous architecture baseline: v0.4.4

[v0.4.4](https://github.com/masahitojp/mariamem/releases/tag/v0.4.4) is released
from source `8ede4ad65def07436b64801076004ff80aec0799`; annotated tag object
`0a22ba1e02957b7bfd616836c65b72040698c617`. The
[release run](https://github.com/masahitojp/mariamem/actions/runs/37924209669)
passed final-artifact qualification, publication and both-platform public smoke.
Its runtime basis is `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`, qualified on
both platforms by [Product CI](https://github.com/masahitojp/mariamem/actions/runs/37898847164).
Final source and tested runtime source are intentionally distinct identities.

In that released file-backed implementation, creation/import validates the complete Snapshot, then mariamem owns the exact
backing used by Fork. Supported operations do not mutate it. Fork does not fully
rehash content; silent storage corruption arising after ownership is not promised
to be re-detected on each Fork. External source edits/deletion after import do
not affect the owned baseline. Live Snapshots retain one FD per prepared file.
Python uses `snapshot()`, `snapshot_to(path)`, `load_snapshot(path)` and `fork()`.
See the [then-current contract](https://github.com/masahitojp/mariamem/blob/v0.4.4/docs/decisions/snapshot-product-contract.md),
[implementation review](reviews/v044-implementation-review.md),
[architecture](v04-generated-go-architecture.md) and
[release notes](../release/NOTES-v0.4.4.md).

Generated-Go is the only supported production runtime since v0.4.3. Snapshot is
cold prepared state; Fork starts fresh MariaDB execution rather than cloning
running heap/threads/TLS/locks/stacks. The file-backed release used private
mappings and OS page CoW; main now uses immutable blocks and private changes.
Historical measurements and release repairs remain evidence, not instructions
for the current user lifecycle.
See [v0.4.3 characterization](../benchmarks/v043-characterization.md) and the
[v0.4.4 review reports](reviews/v044-release-runtime-reuse-design.md).

## Previous release: v0.4.5 — Infrastructure stabilization and measurement

v0.4.5 is published from `d992e26a6d110ceeb54f69d71acd1358c72abb1b`.
The [public smoke recovery report](reviews/v045-public-smoke-recovery.md) records
macOS success and the corrected Ubuntu smoke success with distinct identities.

The [infrastructure audit](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
and [bounded plan](reviews/v045-stabilization-plan.md) own the work sequence.
Restore wire coverage, detach ordinary development from expiring Product receipts,
extract live helpers before retiring historical infrastructure, and establish
clear runtime/artifact/measurement responsibilities. Release qualification remains
fail-closed. Source reproducibility and handwritten inclusion remain required.

Snapshot latency, suite crossover and bounded product measurements follow stable
verification infrastructure; no performance optimization is approved in advance.
No guest upgrade or new product feature is included. A reusable runtime-evidence
model or reduction of required checks needs a focused Human Review first.

Approved runtime-only qualification and identity-bound publication smoke have
been implemented on dedicated branches. Both-native qualification passed for
`34eaea1df86b57765a4d8b0840845a33d539065f`; exact tested and measurement harness
identities remain distinct. The [v0.4.5 Human Review packet](reviews/v045-human-review.md)
records restored wire ownership, canonical checks, CI feedback latency, source
reproduction scope and completed local Snapshot/crossover/product measurements.
Light preparation favors Fresh; expensive data preparation benefits from reuse.
Snapshot traversal reduction was deferred, not implemented. Release CI qualified
and published v0.4.5; the recovery report above records final public smoke.

The [final verification-economics review](reviews/v045-verification-economics.md)
keeps distinct source/runtime/artifact/publication guarantees and moves existing
source/license/mirror checks before expensive compilation. Generated output and
license records are unchanged; evidence trust-scope redesign is deferred to later
Fast Feedback work. The [measurement document](../benchmarks/v045-measurement.md)
owns exact conditions/reproduction. No Snapshot optimization is adopted.
The [agreed v0.4.6 handoff](reviews/v046-handoff.md) covers Go persisted-baseline
loading, comparable language documentation/examples and subsequent realistic
Product Validation; those changes are not part of v0.4.5.

## Supported scope and limitations

- macOS 15+ arm64 and Ubuntu 24.04 x86_64. Canonical acceptance uses Go 1.26.10
  and Python 3.14; minimum package versions do not imply a broad tested matrix.
- Full generated guest is not Go race-detector clean. Preserve the
  [race census](../benchmarks/direct-link-race-scope.md); focused handwritten
  checks do not prove general race correctness. The census is complete for its
  old pinned inputs. The [post-v0.5 evidence reconciliation](reviews/shared-memory-post-v05-reassessment.md)
  distinguishes the later R1–R5 investigation and repairs from a new census or
  general shared-memory model; those scopes must not be counted as one task.
  The [scalar/SIMD static follow-up](reviews/shared-memory-scalar-simd-reassessment.md)
  records 36 historical signatures and current candidate access sites. It identifies
  a concrete purge-state protection question and proposes a bounded original-Wasm/Go
  comparison for Human Review. No new execution or runtime fix is included, and
  candidate-site correspondence is not a complete semantic or exact-PC proof.
  The Human then approved that bounded purge head/view comparison and accepted its
  [macOS fixture result](https://github.com/masahitojp/mariamem/blob/424172f017a0ec42c01407300f08411e9d480348/docs/reviews/purge-wasm-go-comparison.md):
  torn Go heads occur inside the Wasm-permitted set (0 forbidden observations
  across 10,980,000 reads), and no mixing occurs under the common-lock or
  completed-handoff controls. This is not grounds for a Go-conversion fix. The
  purge-specific protection premise (reader `purge_sys.latch` vs writer
  `end_latch`) remains unverified. The Human accepted it as a stated limitation
  on 2026-10-17 and did not authorize a real-guest order observation; it is not
  established as harmless. Ubuntu x86_64 was not executed, and no runtime change
  follows. This is not a general shared-memory guarantee.
- Forced timeout/hard-failure containment is not guaranteed. Normal cooperative
  cleanup and non-cooperative reclaim are distinct boundaries.
- v0.5.0 had an observed approximately one-second startup mode. The
  [page-cleaner source correction](reviews/v050-startup-tail-source-fix-integration.md)
  is released in v0.5.1 and retained in v0.5.2, after bounded Fresh comparisons
  and related regression passed on both native platforms. The exact final source
  that contains it, `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`, passed
  [v0.5.1 Release CI](https://github.com/masahitojp/mariamem/actions/runs/38959312232),
  so the earlier pending exact-final-source validation is satisfied. This does
  not establish a universal latency bound.
- External consumer checks passed on macOS arm64 with Go 1.26.8 and
  1.27.0/1.27.1/1.27.2 historically. GO-2026-6809 affects Go <1.26.10 and
  1.27.0–1.27.2; 0.6.0 build validation uses Go 1.26.10 and the forward-compat
  check uses 1.27.3. See [compatibility](go-compatibility.md); minimum Go and
  driver versions are unchanged.
- Physical footprint, RSS and reachable heap are different resource measures.
  The v0.4.2 lifecycle releases linear memory after joined workers; filesystem
  metadata remains GC-managed.
- Published file-backed Snapshots retain roughly one FD per prepared file.
  The adopted D memory path removes this ordinary backing-FD requirement;
  both-native verification is recorded above. The historical 64-table fixture
  had 137 files and released its backing FDs after Close on both platforms.
  Many simultaneously retained baselines, especially file-heavy schemas, may
  approach process FD limits. The 2026-10-30 Human correction assigns detailed
  retained-baseline/FD-pressure characterization to v0.7.x, superseding its
  earlier v0.6.0 dogfood placement. Entry-owned cleanup remains required in
  v0.6.0; resource-model changes are not authorized by this observation.
- The 0.x API may change. Corresponding guest source, licenses, notices and
  reproducible generation remain required.

## Performance evidence and pending optimization questions

**Moved to v0.7.x resources: per-DB connection-count tuning.** The current contract
keeps a fixed 16-connection limit per DB. The Human placed connection-count
optimization in the 0.5.x scope on 2026-10-17; on 2026-10-18 the Human moved it to
v0.6.x so that actual demand and resource effect are confirmed during dogfood
before changing the limit. The 2026-10-30 scope correction moves that detailed
resource/tuning work and FD/resource-model characterization to v0.7.x. The
16-session wire contract and bounded application connection use remain unchanged.
The current active and closed items are listed in the [v0.5.x remaining-item snapshot](reviews/v05x-remaining-items.md).

**Evidence reuse scope — assessment accepted, expansion deferred (2026-10-18).**
The Human approved the [limited dependency/rejection-condition assessment](reviews/runtime-evidence-trust-scope-plan.md),
including a timing check of the previous long verify/release runs. The
[results](reviews/runtime-evidence-trust-scope-results.md) distinguish runtime
dependencies from qualification's benchmark test/vet and source inventories.
The prior approximately 91-minute verify and 94-minute release used different
source commits/versions; their intervening paths were already permitted by the
current path/version comparison, but no authenticated reusable runtime intent
connected them. Exact-SHA READY reuse also could not bridge different commits.
The recommendation is to retain current reuse rules and use the existing
one-shot release, or verify the final versioned candidate and release the same
SHA. No new exclusions or runtime/workflow changes were implemented. The Human
accepted deferring the wider redesign on 2026-10-18. This closes the bounded
assessment and removes scope expansion from active v0.5.x work; it does not
establish a new reuse contract. Revisit if benchmark-only changes repeatedly
block otherwise eligible evidence reuse. The Human separately approved main
integration of the assessment, evidence and acceptance records on 2026-10-18;
source `779ad55babaef2fab6875846e63d2d984f5a16d8` was fast-forwarded without
runtime, verifier or workflow changes. Any actual release remains a separate decision.

**Child Fork startup and child Close attribution — accepted 2026-10-18.** The
[bounded attribution](https://github.com/masahitojp/mariamem/blob/bbf5d1c27f3cea3e2135e8fae053f875ceb234b5/docs/reviews/child-lifecycle-attribution.md)
completed 40 fixed executions on each native platform (macOS local; Ubuntu source
`e4a5522ca475f73b56f23b08a725354eafb81b19` in
[run 39083277771](https://github.com/masahitojp/mariamem/actions/runs/39083277771),
artifact identity and all cells/traces/aggregates independently reconciled).
Guest server initialization dominates Fork on both platforms; the repeated OS
check adds material cost only on macOS. Actual DB Close is separate from SQL
disconnect waiting and is mainly guest shutdown and linear memory release.
Investigation #2 met its exit criteria and the Human accepted it on 2026-10-18.
Acceptance does not itself approve an optimization or main integration.

**Human-approved child-lifecycle optimization scope — 2026-10-18 (order
revised 2026-10-18):** for this workstream, v0.5.x is limited to these two
actions, in order:
1. Implement and measure reuse of successful macOS platform checks, preserving
   unsupported-platform rejection, cancellation/failure behavior and concurrent
   startup correctness. Keep DB internals unchanged. Implemented, verified and
   accepted for main integration on 2026-10-18.
2. Then investigate Ubuntu 10MiB parallel startup: distinguish startup
   contention from overlap with other children’s SQL/cleanup and identify the
   principal cause. Observed guest open-to-ready is 65.84ms serial versus
   133.95ms with four workers (60.62ms is the different Light case). Compare
   per-child latency and whole-suite elapsed time. This bounded investigation
   also supplies measurement evidence for the v0.7.x selection; it does not
   authorize guest-initialization optimization implementation.

Guest-initialization improvement candidate selection is scheduled for v0.7.x,
using the investigation evidence; it is not a v0.5.x task. Main integration and
release remain separate decisions. The Human approved the
[success-cache design](reviews/macos-platform-cache-design.md) for implementation
and bounded measurement on 2026-10-18, with review gaps to close first. The
[implemented candidate and bounded macOS results](reviews/macos-platform-cache-results.md)
record passing unit/race and lifecycle checks, 32 measured executions, faster
subsequent Forks and child-suite medians, plus initial-Python/parallel-Close
uncertainty. Native focused CI passed on exact source dc183e438a65c13aa532e16e38e31e3378d0a1dd
in [run39091145992](https://github.com/masahitojp/mariamem/actions/runs/39091145992);
both artifact digests, source receipts and focused logs were reconciled. The
Human approved main adoption/integration on 2026-10-18. Canonical
`scripts/verify.py integration` now includes `./internal/artifacts` in its race
set, so main CI retains the new concurrency oracles on native macOS. Product
runtime matches the reviewed CI source; this follow-up adds CI wiring and
adoption records. The first main Development CI passed check and all race
packages, but its integration job hit the 15-minute job limit before completing
later acceptance. Following Human approval, the job budget is 30 minutes with
individual test deadlines unchanged. The manual full-development
[run39094406383](https://github.com/masahitojp/mariamem/actions/runs/39094406383)
passed scope, full check and canonical integration on exact source
`8907a4e19da104fd9cd110a91e36543097e43ba4`; the artifacts race set, later Go
acceptance, Python18 tests and Snapshot33 checks completed. This closes the
post-integration development check, not release qualification. The linked
results retain the original timeout and the successful rerun. Release remains
a separate decision. Item 2 completed its bounded measurements on the isolated
[Ubuntu parallel-startup study](reviews/ubuntu-parallel-startup-study.md):
matched serial/pipeline/barrier conditions plus separate bounded diagnostics.
[run39099563649](https://github.com/masahitojp/mariamem/actions/runs/39099563649)
passed all 32 executions on source `4e73abe126672869ad03575e84706b5ab2cb557c`.
The [result and Human Review](reviews/ubuntu-parallel-startup-results.md) finds
that preventing early SQL/Close overlap does not remove slower per-child Forks;
startup execution-resource sharing is the main supported cause category.
Ordinary process-level medians are 43.50ms serial versus 84.03ms parallel per
child, while four-child elapsed time improves from 541.23ms to 263.47ms.
CPU scheduling versus cache/bandwidth contributions remain unseparated; a slow
post-ready SQL trial is retained separately. The Human accepted the bounded
investigation results on 2026-10-18 after clarification of the GOMAXPROCS
diagnostics. Keep automatic GOMAXPROCS selection: 4 was fastest among the
tested 1/2/4 settings and also matched the native default; no better setting
has been demonstrated. This closes item 2a, not the unseparated mechanisms.
The result acceptance did not authorize guest optimization or main integration.
The Human separately approved main integration on 2026-10-18. Integrate the
measurement harness/workflow, compact evidence and reports from
`791108e` as one commit; product runtime, guest, generated sources and public
contracts remain unchanged. The successful native campaign binds to the original
measured source above, not to a claim of rerunning it on the integration commit.
Guest-initialization candidate selection remains scheduled for v0.7.x.
Other previously recorded roadmap items are not cancelled by
this workstream decision.

The Human prioritized native Ubuntu performance measurement next. The
[fixed-scope campaign](reviews/ubuntu-product-performance.md) completed 246
executions on the released v0.5.0/v0.5.1/v0.5.2 inputs in
[run 39073990176](https://github.com/masahitojp/mariamem/actions/runs/39073990176).
The [result review](reviews/ubuntu-product-performance-results.md) reconciles
all cells and identities: Snapshot gains also appear on Ubuntu, while large
Python whole-workflow results remain mixed. The Human accepted these results
on 2026-10-18, closing this performance check. The large Python regressions and
their unresolved cause remain recorded. Acceptance does not reopen the closed
100 MiB Go Fresh investigation or authorize additional cause profiling, main
integration, runtime changes, Qualification or publication.
The Human separately authorized main integration and push on 2026-10-18.
The integrated scope is measurement tooling, preserved evidence and documentation;
no runtime change or further measurement is included.

**Closed until recurrence: 100 MiB Go Fresh.** The
[completed paired comparison](../benchmarks/main-product-verification.md#adverse-100-mib-go-case-and-bounded-repeat)
retains the original +29.0% wall-time trial, the three additional pairs (+1.9%
median), and all four observations (+7.2% wall / +6.3% CPU median). Preparation
and SQL account for the adverse intervals; storage overhead versus execution
conditions remains unresolved. The maintainer accepted this tradeoff for
v0.5.1; it was not an additional release gate. The subsequent bounded
[released-source investigation](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-large-fresh-investigation.md)
and [allocation attribution](https://github.com/masahitojp/mariamem/blob/7068dd045f10c2772535fccca73c040c387e5b0b/docs/reviews/go-heap-reuse-attribution.md)
are complete on `experiment/go-large-fresh`; their experiment history is not merged.
The additional runs did not reproduce persistent Fresh slowdown. The original
slow trial's cause and the allocation origin of heap-reuse CPU remain unresolved.
The original Human decision to close the investigation on 2026-10-17 is recorded
in `7068dd045f10c2772535fccca73c040c387e5b0b`.
Reopen only if similar slowdown recurs in normal use or
measurement, using the saved evidence. Further profiling or runtime repair is
not pending approved work; do not start additional measurements while waiting
for recurrence, call the old result noise, or claim the cause was fixed.

Current storage routing follows the adopted D/shared-host contract and
[implementation/adoption report](reviews/d-heap-shared-host.md) above. The v0.4.x
decision and research handoff below record earlier investigation context; their
retain-MAP_PRIVATE and unperformed-measurement statements are not the current
implementation or instructions to restart that work.

The [Go 1.26.8 / 1.27.2 comparison](benchmarks/go126-vs-go127.md) retains
same-source macOS arm64 suite/resource results and reproduction evidence.
No consistent practical speedup was demonstrated; these observations do not
change the supported toolchain policy or qualify the current main SHA.

The [memfs Architecture Decision](reviews/memfs-architecture-decision.md) was the
v0.4.x routing reference: retain memfs + MAP_PRIVATE pending limited measurement,
and defer broader replacement. The D adoption above supersedes that storage
choice. Its [memfs/pglite](reviews/memfs-optimization-discovery.md),
[pgmem](reviews/pgmem-vfs-design-review.md) and
[block-storage](reviews/block-storage-design-discovery.md) reports are historical
inputs with pinned source hashes. The observed ~4.62 GiB is cumulative allocation
across 20 Fresh DBs including fixture work; it is not retained memory or an
estimate of removable allocation. The [benchmark index](../benchmarks/README.md)
already owns measurement navigation; no duplicate report is introduced.

### Historical research handoff — before D/shared-host adoption

The following paragraphs preserve the scope handed off before the later storage
exploration and implementation. Their prospective language describes that stage,
not today's remaining tasks. Current remaining work is recorded in the adoption
report and the published-release/main distinction above.

**MemFS limited measurement:** use the existing Decision's §7 as the sole scope
and acceptance reference: file/phase initial allocations, reallocations/copied
bytes, unique write coverage, child-only mapped detach and corresponding
wall/CPU/Peak RSS. This work remains unperformed and needs separate authorization;
do not create a second measurement plan or backend implementation here.

**Snapshot lifecycle/shutdown:** pgmem stops its server, clones VFS state, then
restarts the original; mariamem consumes the source on successful cold Snapshot.
The [existing Snapshot characterization](../benchmarks/v045-measurement.md#snapshot-lifecycle-research-boundary)
already measures the public operation, host/export envelope, materialization,
read/hash, copying and owned acquisition. Reuse those traces first. Remaining
questions are pure shutdown versus guest snapshot-copy inside that envelope,
read versus hashing CPU in combined intervals, and any decision-relevant
unattributed manifest/cleanup residual. Fork startup/recovery is a separate
operation. The pgmem ~10 ms reference has different lifecycle/storage boundaries
and is not a comparable mariamem performance result. Restarting the source or
changing InnoDB shutdown mode is not approved.

Neither research item blocks v0.5.0. Performance PoCs, if later authorized,
require their own correctness and product-benefit decision; stable-guest behavior
must be rechecked before integrating an optimization selected on the old guest.

**Snapshot direct-copy — Human decision, 2026-10-14:** the maintainer accepted
stopping this investigation and its spikes at the present stage, retaining the
current product implementation and deferring adoption of the prototype. The
approved local spike and eight-run follow-up are complete; no further measurement,
cause investigation or prototype work continues automatically. Resuming this
specific optimization requires a new agreed scope and exit conditions.

The [completed follow-up and evidence](https://github.com/masahitojp/mariamem/blob/b6d371232f613425b066049bb3e6f873cfee4e37/docs/reviews/snapshot-direct-copy-recheck.md)
record a roughly 0.43-second Snapshot saving and approximately 264 MiB less
cumulative allocation on macOS arm64, but mixed 100 MiB / 16-Fork whole-suite
results: ordinary timing 2.2% slower, resource-observed timing 2.9% faster.
Extra child-phase GC recurred; changed allocation/GC pacing remains a hypothesis,
not an established cause of delay. This decision defers the current prototype
without rejecting direct copying in general. Runtime source remains isolated on
`experiment/snapshot-direct-copy`; its ownership/failure tests, raw measurements
and reproduction scripts are preserved in the linked reports. Disposable build
and measurement state has been cleaned. No release decision follows.

**Storage documentation after main adoption — 2026-10-17:** use the Product
contract and adoption report for current behavior, validation and remaining work.
The following older materials have distinct roles; none starts another experiment.

| Material | Continuing use |
| --- | --- |
| [Storage design map](reviews/storage-design-directions.md) | Reference for A–F alternatives, product value and reference-project differences. Historical assumptions are labelled; D/shared-host is now adopted. |
| [D productization design](reviews/d-heap-productization-design.md) | Approved design/scope-change history supporting the implementation. The older local draft lacking the save/load removal decision was redundant and removed. |
| [Direct-copy investment reassessment](reviews/storage-investment-reassessment.md) | Archived reasoning and measurements from the earlier comparison. Its pending-decision wording, four-hour proposal and estimates are not current tasks. |

The 2026-10-15 exploration preserved library convenience and independent real
DBs while reopening storage/clone methods. That direction led to the D/shared-host
adoption; it no longer represents an unselected backend or pending Human Review.

## v0.4.7 — Upstream converter migration (candidate)

The released scope replaces the pinned shibukawa converter fork with pinned
`goccy/wasm2go` plus nine maintained patches. MariaDB guest identity, public APIs,
Snapshot format and minimum Go version remain unchanged from v0.4.6. Independent
regeneration, runtime/consumer checks and same-scenario product/resource comparisons
must precede the Human release decision. Native macOS/Ubuntu artifact qualification
remains CI-owned. No guest upgrade, handshake experiment or VFS optimization is
part of v0.4.7. Historical candidate measurements qualify only their recorded inputs.

## v0.5.0 — Stable guest preparation history

This release is now published; its final source/tag identity is recorded above.
The following records the successive preparation inputs and decisions at the
time. Statements that a branch was unqualified or a decision was pending refer
to that historical stage, not a new outstanding correction or release gate.

Final Qualification passed for exact candidate source
`bb637c49e6d6b50ec6761dead172a35f0b051f7e` in
[verify run 38366609671](https://github.com/masahitojp/mariamem/actions/runs/38366609671).
Independent guest builds/Go regeneration, both native platform suites, external
consumers and aggregate source/license/artifact guards passed; CI returned READY.
The [qualification report](reviews/v050-final-qualification.md) preserves exact
receipts and distinguishes the workflow source from the tested candidate.
After that Human Review, the maintainer authorized Product Verification.
The [approved 80-cell campaign](../benchmarks/v050-product-verification.md)
is complete: SQL/isolation oracles and bounded cleanup pass; timing is mixed,
including an adverse Go parallel-Fresh median under the existing startup tail.
The [Human Review](reviews/v050-human-review.md) recommends adoption. The
maintainer accepted that recommendation and authorized v0.5.0 release submission;
Release CI must qualify the final integrated source before publication.

The maintainer authorized the limited J1 completion/reclamation repair after the
paired counterexample. The [implemented candidate](reviews/v050-join-lifetime-fix.md)
binds worker map reclamation to final agent access, covering delayed wake,
detached self-exit and unwind. Guest/raw converter inputs remain unchanged;
owned generated edits are independently reproduced. T1/T2/J1 close the identified
corrective items in the agreed current-guest investigation. Candidate adoption and Qualification were separate from the subsequent release
authorization, as recorded in the [Human Review](reviews/v050-human-review.md).

The bounded [R1–R5 investigation](reviews/v050-semantic-audit.md) supplied the
per-target access/lifetime and supporting-protocol review: 65 functions, 147
narrow writer sites, 28 target records and all 14 original families. Its original
result supported the reviewed mappings while identifying T1/T2 and leaving J1
unresolved. The [subsequent paired comparison](reviews/v050-boundary-join-fixes.md)
confirmed premature allocation reuse in original Wasm and Go under a forced
schedule. No Go-only forbidden outcome or natural SQL harm was established.
Those historical findings led to the authorized repair above. Coverage and local
repair verification do not replace final release qualification.

The [assessment review](reviews/v050-access-review.md) preserves why the earlier
investigation and progression recommendation were incomplete, and the finite
contract used to finish this investigation. No scope reduction was made; the
five-hour cap was a stopping budget, not a completion test. Hourly reporting was
cancelled by the Human. Prior exact-width fixes remain; the investigation itself
changed no product implementation. The later owner fixes are recorded separately
above. Final Qualification has subsequently passed for the exact candidate
recorded above; the subsequently approved Product Verification is complete as
recorded at the top of this section.

On the dedicated v0.5.0 experiment branch, the maintainer approved formal
exact-width narrow atomic writer integration after bounded design verification.
The [integration report](reviews/v050-exact-writers-integration.md) records the
unchanged accepted 12.3.3 guest, independently regenerated runtime, retained
failure oracles and local regression/consumer results. Native Ubuntu focused development
verification subsequently passed in the linked Development CI receipt; this
does not qualify the new macOS-only protocol fixtures. At that stage the branch work did not qualify main or establish general
shared-memory correctness. The later Qualification and Product Verification are
recorded above. The roadmap below retains its historical scope.

Fast Feedback phase timing and task-local Go cache reuse were integrated at
`70ac70ce0a4ccda403aa290dffa1d0bac0d8728b`. The approved single-pass development
guest route was integrated at `ee48a2a50fe71e79564ab1dde42c45594f220438`.
It builds into isolated external outputs, records actual source/tool/artifact
identities and runs a freshly generated host smoke. Results remain UNQUALIFIED;
independent Release builds and qualification guards are unchanged. The current
guest passed Linux arm64 build and macOS arm64 native smoke; this does not qualify
a new guest or native Ubuntu runtime. See [validation and exact measured identities](reviews/v05-dev-guest-build-validation.md)
and [development commands](development.md#single-pass-unqualified-guest-development).

The maintainer authorized A–D integration of exactly MariaDB **12.3.3** on
2026-10-12, retaining the v0.4.7 goccy converter pin and nine patches. Selection
is an exact source input, not an LTS classification or a multi-series promise.
The [A–D integration report](reviews/v050-ad-integration.md) owns adopted inputs,
reproduction, local checks and remaining work. This branch is not release-qualified.

The approved [common portability plus minimal source-specific hunk policy](decisions/guest-patch-management.md)
is implemented for the single 12.3.3 input: ordered hash-bound patches with
preimage/postimage verification. The handshake reads the running guest's VERSION()
without an old-version fallback. Saved old-guest Snapshots require recreation.

The [bounded correctness judgment](reviews/v050-correctness-judgment.md)
reproduces fd_allocate data loss, zero-length bulk trap omissions and load-only
subword CAS writes. Three bounded corrections are recommended before qualification;
no production fix was applied in that judgment. The maintainer subsequently
authorized the [three bounded corrections and feasibility study](reviews/v050-correctness-fixes.md).
Those owner changes, independent regeneration and local checks are complete;
no general shared-memory guarantee or RELEASE READY status follows.
Human review chooses whether to retain the stated limits or require a broader
design before final Qualification and Product Validation. The same conflicting
accesses report races on Go heap and none on production mmap backing under the
observed Go1.26.8 macOS arm64 detector. Shared-memory semantics and acceptance of
that documented observation limit require a separate Human decision.

These earlier A–D checks alone did not qualify a release. Their follow-up
correctness work, both-native Qualification and Product Verification are linked
above. Full shared-memory race census and startup-tail improvements remain
separate work; no general performance improvement is claimed.

## v0.6.0 — Wire contract and dogfood

**P1 adopted on main, 2026-10-31 JST:** PR26 merged via protected checks to
`4a8a68350e8c43fc107843a6efe7781cad1a4e2a` from head
`850ddcc2c70786dc310308d262b4f33d842fea3e`. Daily CI41076760360 executed
`0f59d660e5ca58a65818915602787fec5e7e57d3`; all three trees equal
`e09c9c8f3300b5ca716e1776da4676ada01f3e94`. The older Ready full receipt remains
bound to head8912224a/actual6ccec794, not relabelled onto the final CI-policy tree.
Main PR34/35/36's approved Release-only heavy validation applies: final head has
successful source/unit/Ubuntu smoke, with new-head platform/native/browser/installed
qualification deferred to Release CI. P1 product/input bytes are unchanged from
the successful full profile. See [integration completion and both evidence scopes](reviews/v06x-p1-head-integration.md).
This completes P1 adoption, not other dogfood/wire work, Qualification or release.
Earlier P1 pending/checkpoint entries below retain their historical source context.

**Human scope correction, 2026-10-30:** establishing the wire contract is the
main v0.6.0 objective. P1 has a [fixed six-condition exit](decisions/p1-fixed-exit-v060.md).
Detailed resource characterization, retained-baseline stress and resource-model
or connection-capacity tuning belong to v0.7.x, not P1 or v0.6.0 completion.
Entry-owned cleanup, bounded worker/connection behavior and readable failure
handling remain required. This supersedes the earlier resource placement below;
existing receipts retain their original source and scope. This scope decision
alone grants no runtime PASS or release approval; current P1 acceptance follows.

**P1 fixed-exit acceptance verified, adoption review ready:** source_commit
`b108abf11a623c18c45adfab2968d357bf40718b` passed
[CI40987752495](https://github.com/masahitojp/mariamem/actions/runs/40987752495):
macOS15/Ubuntu24.04 × Python3.11/3.14 each220 unit PASS and5 installed-consumer
runtime PASS, with4 resource experiments explicitly SKIP. Both native input
profiles pass with schema_count_after=0. The [checksummed receipt](reviews/v06x-python-fixture-implementation-evidence/ci-40987752495/assessment.json)
and [six-condition adoption review](reviews/v06x-p1-fixed-exit-adoption-review.md)
recommend main adoption. Human approval and protected PR integration remain;
P1 feature acceptance no longer waits on detailed resource measurement.
The first candidate40979625348's stale-resource-workflow FAIL is preserved,
not relabelled. Other dogfood/wire work and Qualification/release remain separate.

### PR macOS Live check ownership

The Human approved reducing PR macOS waiting after inspecting
[Live run 40846147295](https://github.com/masahitojp/mariamem/actions/runs/40846147295/job/123355927759).
PR macOS Live omits the generic canonical check; Development retains Ubuntu
source/unit/vet checks with its existing scope selection. Selected main/manual
macOS Live retains the full check. macOS canonical integration, G1 acceptance,
Live race and installed-consumer gates remain unchanged. This defers macOS-only
unit/vet findings to main/manual; it does not remove macOS runtime acceptance.

The observed check step took 10m56s and integration 20m24s. Removing the check
does not promise that elapsed saving: it also warms the compiler cache used by
later steps. Compare whole-job and downstream durations on the new candidate.
Integration and the later Live race step overlap on root/control packages, but
integration sets MARIAMEM_TEST_DEFAULT and has a broader target list; removing
either invocation needs a separate equivalence check. No extra macOS job or
timeout increase is introduced.

### Current work tracking

Use the [v0.6.0 milestone](https://github.com/masahitojp/mariamem/milestone/1)
for current and completed release work. The following Issues own actionable
checklists and source-bound acceptance evidence; this status document retains
the approved scope and sequencing below.

| Tracking Issue | Current disposition |
| --- | --- |
| [#18 — five-profile dogfood acceptance](https://github.com/masahitojp/mariamem/issues/18) | Active v0.6.0 acceptance tracking for P1, G1, D1, EP1 and EG1; recipes/component PASS do not close the full obligation |
| [#19 — dbt revalidation](https://github.com/masahitojp/mariamem/issues/19) | Active v0.6.0 independent CLI workload; the original #5 prerequisite is resolved, but repaired SQL alone does not establish dbt acceptance |
| [#24 — multi-statement host panic guard](https://github.com/masahitojp/mariamem/issues/24) | Active v0.6.0 follow-up to #13; detect unclassified host panics preceded by another statement |
| [#20 — Oracle prepared CALL result traversal](https://github.com/masahitojp/mariamem/issues/20) | Accepted external-consumer limitation; outside v0.6.0 work, no milestone |
| [#21 — Oracle macOS C/default NUL projection](https://github.com/masahitojp/mariamem/issues/21) | Accepted external-consumer limitation; outside v0.6.0 work, no milestone |

The Human excluded #20/#21 from v0.6.0 work because those external consumer
behaviors are outside our control. Their tracking does not promise a repair,
dependency update or delivery date, and does not add a fix prerequisite or
release blocker. The existing [accepted consumer exceptions](decisions/prepared-consumer-exceptions.md),
original functional FAILs, version-specific limits in the [Go](go.md) and
[Python](python.md) guides, and change-triggered rechecks remain in force.
Excluding repair work does not remove disclosure of the limitations from the
released support contract.

Completed work remains visible in the same milestone: [#5](https://github.com/masahitojp/mariamem/issues/5)
and [#7](https://github.com/masahitojp/mariamem/issues/7) repair the import/failure
path, [#11](https://github.com/masahitojp/mariamem/issues/11) tracks CI efficiency,
and [#13](https://github.com/masahitojp/mariamem/issues/13) tracks the adopted
stub-classification/SQL detection net ([PR16](https://github.com/masahitojp/mariamem/pull/16)).
These are closed; they are not pending prerequisites for #18/#19. In particular,
#19 may proceed from the resolved #5/#7 repair while recording its own source.
The adopted #13 guard still misses an unmarked host panic preceded by another
statement; [#24](https://github.com/masahitojp/mariamem/issues/24) owns that residual
gap. See the [WASIX stub maintenance procedure](v04-generated-go-architecture.md#unimplemented-wasix-host-imports)
for classification updates and the current detection boundary.

### Approved scope and release sequencing

**v0.6.0 release scope agreed with the Human, 2026-10-30:** Live is part of the
0.6.0 scope together with the other adopted-on-main capabilities (routines,
prepared statements with the accepted consumer exceptions, connection switching,
`import_dump`, the 16-bit status projection and the Go 1.26.10 toolchain). The
[scope record](decisions/v060-release-scope.md) owns the inclusion list, the
release prerequisites (complete dogfood or a recorded D1 deferral, then
version/notes, Qualification and publication) and the explicit exclusions. This
is a placement decision; it does not approve publication or bypass any gate.

**Dogfood scope and release sequencing agreed with the Human, 2026-10-29:**

- The five named entries (P1 Python pytest/`shadow_maria`, G1 Go helper,
  D1 Django, EP1 Python browser E2E, EG1 Go HTTP E2E) are the complete v0.6
  dogfood obligation. None may be silently dropped from a completion report.
  The 2026-10-28 Django policy still applies: D1 may be deferred when it proves
  difficult, but only with its concrete obstacle and remaining work recorded.
  A deferral is a disposition of the obligation, not a reduction of it.
- **Complete dogfood is a prerequisite for the v0.6.0 release.** Recipes,
  component PASS, unit tests or single-platform runs do not satisfy it; the
  acceptance campaign (declared profiles, both supported hosts, lifecycle and
  usability/time outcomes) does. Detailed resource outcomes moved to v0.7.x by
  the 2026-10-30 correction; they no longer block this prerequisite. The release
  order remains dogfood completion, or a recorded D1 deferral, then version/notes,
  Qualification and release.
- **dbt is adopted as an independent CLI preparation workload profile.**
  Its original issue #5 (`Fd_dup` / TEXT deduplication) prerequisite is now
  satisfied; [#19](https://github.com/masahitojp/mariamem/issues/19) tracks the
  remaining workload revalidation. It is not a sixth named entry and not a
  workload of P1: dbt is a command-line
  preparation/run tool with its own client and failure surface, so it is
  evaluated against its own declared profile (pinned lock, preparation command
  surface, TEXT-dedup matrix, failure semantics, both supported hosts).
  `dbt-mysql 1.7.0` pins `dbt-core~=1.7` (an EOL line) and depends on
  Connector/Python; both are recorded limits of that profile. Promoting dbt to a
  supported entry with product guarantees would require a separate decision.
- These entries, their acceptance contract and the diagnostic levels live in the
  scope proposal carried by PR #6
  ([scope draft](https://github.com/masahitojp/mariamem/blob/docs/v06-independent-django-input/docs/reviews/v06x-dogfood-scope-draft.md),
  [acceptance contract](https://github.com/masahitojp/mariamem/blob/docs/v06-independent-django-input/docs/reviews/v06x-fixture-acceptance.json)).
  This entry records the decision; it does not claim any entry is implemented or
  accepted.

**Scope emphasis agreed with the Human, 2026-10-28:** primarily finish the
end-to-end user workflow using existing functionality: establish a first test,
reuse preparation for independent subsequent tests, run the intended test
lifecycle, understand failures and complete cleanup. Expanding framework support
is not the primary completion measure; adapters and new APIs remain possible
responses to demonstrated gaps, not prerequisites chosen in advance.

**Preparation responsibility agreed with the Human, 2026-10-28:** the user
specifies migration/seed commands or callbacks; the supplied entry owns their
execution, success assessment, reuse of successful preparation and disposal on
failure. Users should not have to assemble those lifecycle operations themselves.
This is the intended user-facing scope, not a claim that every existing recipe
already provides it. Exact entry APIs, success signals, reuse/sharing units and
failure/cleanup acceptance remain design work. No cross-run persistence or
automatic retry policy is selected by this agreement.

**Default reuse unit agreed with the Human, 2026-10-28:** reuse successful
preparation within one test execution; parallel workers each own independent
preparation/baselines. The supplied entry manages that lifecycle, so users do
not assemble worker sharing or cleanup themselves. Each test still receives
independent mutable state. This selects the default user experience, not a
cross-worker baseline service, cross-run persistence or an implicit retry rule.
Exact APIs and the implementation/acceptance design remain separate work.

**Failure handling and human-readable explanation agreed with the Human,
2026-10-28:** failed preparation must not admit tests. The entry attempts cleanup
after test failure, exceptions and normal interruption; if cleanup also fails,
retain both the original failure and cleanup failure rather than masking either.
Do not silently retry to hide failure. Hard-kill/machine-stop recovery is a
separate boundary, not implied by normal interruption handling.

The default explanation must let a person understand the failed operation/stage,
what happened, the confirmed cause and original error/code where available,
the next useful action, and whether tests started and cleanup completed.
Distinguish confirmed facts from hypotheses and explicitly state when the cause
is unknown. Preserve detailed diagnostic context for inspection without making
users reconstruct the basic explanation from raw tracebacks. This selects the
diagnostic outcome, not a formatter API or a promise of automatic root-cause
identification; current runtime behavior still needs design/acceptance mapping.

The [consolidated scope draft](reviews/v06x-dogfood-scope-draft.md) separates
these agreed outcomes, existing entry foundations and remaining product choices.
**Prepared-entry guarantee and pragmatic exit agreed with the Human,
2026-10-28:** every admitted test through the prepared-data entry begins with
the declared prepared schema/seed, including after another test's committed
writes or ordinary failure. Framework-native isolation alone is not proof of
this guarantee; the existing Django runner remains a separately documented route.
Human-readable failure explanations are the ideal. If richer diagnostics prove
disproportionately difficult, a thin pgmem-style prepare-once/fork-per-test helper
is an authorized first milestone, with the reason and remaining diagnostic work
reported explicitly. This fallback changes diagnostic ambition, not initial-state
isolation, setup-failure admission, original failure preservation or honest
cleanup reporting. Exact helper APIs and runtime acceptance remain design work;
no independent-project execution is selected by this agreement.

**Human acceptance after the 2026-10-28 review:** name P1 Python
prepared/marker, G1 Go helper, D1 Django prepared entry, EP1 Python browser E2E
and EG1 Go HTTP E2E as the target set, with G1 delivered first. This target/API
proposal was approved against design commit39f9757, with the Django exception
below; first-milestone success cannot close the remaining required set. The [Go API/ownership proposal](reviews/v06x-go-fixture-api-design.md)
fixes capture consumed/preserved/invalid-but-not-disposed oracles, candidate
MaxForks2 and pool budgets, and a diagnostic choice committed before code.
The [E2E hook contract](reviews/v06x-e2e-entry-contract.md) fixes start/readiness,
quiescence plus physical connection retirement, optional resume and stop/reaping.
The scope draft includes all three time outcomes and memory/FD/connection
observations, with finite diagnostic limits and no resource-governor claim.
[Design lint](../scripts/check_fixture_design.py) checks the structured
[acceptance contract](reviews/v06x-fixture-acceptance.json) and rejects missing
obligations; runtime acceptance still requires actual evidence.

**Django exception agreed with the Human, 2026-10-28:** this is a general fixture
and E2E product, not a Django-specific product. D1 remains a dogfood target, but
difficult Django-specific implementation is **not a blocker for v0.6.0**.
Record the concrete obstacle, user impact and unfinished work when deferring;
do not label the deferred entry supported or PASS. Shared lifecycle, isolation,
cleanup or wire defects still require assessment against P1/G1/EP1/EG1 and cannot
be dismissed merely because Django exposed them. EP1 browser E2E stays required;
if its Django application is the obstacle, record a fixed non-Django application
substitution rather than making Django an indirect gate or dropping browser E2E.
The approved first implementation is G1 under the reviewed API, ownership,
diagnostic profile and resource defaults; no main adoption or release is
authorized by this decision.

**G1 Human adoption decision:** The Human approved adopting the bounded Go
prepared-test helper for G1. The reviewed PR head was
`de860c4fc553907d237ad3a046ca6a6780ce0bb4`; its production helper and G1
acceptance code match the earlier both-host reviewed candidate `f58eebcdcb9ddb38a08fdbbd4ace8f6717154ab8`.
The [acceptance review](reviews/v06x-go-fixture-acceptance-review.md) retains
the controlled-backend and other limits; it does not claim every real engine I/O
failure. The historical [Live run 40751031818](https://github.com/masahitojp/mariamem/actions/runs/40751031818)
remains bound to its own executed source, not to this later integration. The
updated candidate must pass its own protected checks and both-host G1 receipts
before main integration. This decision does not complete the other dogfood
entries or approve Qualification or publication.

**G1 implementation checkpoint:** the candidate adds the separate Go
mariamemtest helper under the approved ownership/defaults and readable-owned
diagnostic profile. See [usage](go-prepared-fixture.md) and
[remaining acceptance](reviews/v06x-go-fixture-implementation.md). Local macOS27.2 arm64 canonical check, helper race tests, actual-guest
oracles and the guide sample passed at code source_commit5c739b7. The subsequent both-host time/resource result is recorded below; G1 completion
is not claimed. The [G1 campaign follow-up](reviews/v06x-go-fixture-campaign.md)
adds all four cap/parallel modes, retained1/2/3 counters/guards, three-time outcomes,
checksum-bound raw receipts and an actual pre-admission guard STOP. Local
macOS27.2 passed at232fc19; required macOS15/Ubuntu receipts are now verified below. The Live required gate now checks both actual campaign artifacts,
not just the declaration lint. Original CI40715670588's integration failed at
checkout on network/DNS errors; filtered full-history retrieval mitigates payload
cost without claiming to cure DNS. No root runtime/guest change, main adoption or release
is included.

Subsequent Ubuntu CI40724194463 completed canonical integration, but G1 validation
rejected a final RSS0 sample after process exit. The collector now retains
exit-confirmed terminal observations separately; live RSS0/missing counters still
fail. See the [source-bound diagnosis and original failed artifact](reviews/v06x-go-fixture-campaign.md#ubuntu-ci-collector-exit-race--run40724194463).
Tooling tests214 and the full local campaign passed at549be26; the successful
both-host result follows below. Old FAIL/PASS receipts retain their original source identities.

**Both-host G1 time/resource campaign confirmed:** Live CI40730646806 attempt2
and required gate123000356113 succeeded. Executed merge source b594527 has the
same tree as PR head e8c0380. Mac15.7.9 arm64 executed on attempt2; Ubuntu24.04
x86_64 reused its successful attempt1. The [saved receipts and assessment](reviews/v06x-go-fixture-campaign.md#both-host-resource-time-receipt-confirmed--run40730646806-attempt2)
verify all four cap/parallel modes, retention1/2/3, three-time outcomes, resource
guards, expected pre-admission FD STOP and cleanup. This closes that evidence
gap; G1 still needs actual backing/disposal fault controls and an installed
consumer that exercises mariamemtest. Existing Live installed-consumer success
is not proof of that helper route. No main adoption/Qualification/release.

**G1 remaining acceptance implementation:** [physical ownership and external
helper consumer controls](reviews/v06x-go-fixture-completion.md) are implemented.
They observe real FD/temp cleanup with controlled backend/interface faults,
require 8 semantic mutations to be detected, and resolve the actual candidate
helper from a private Go module ZIP outside the repository without replace.
Fault injection exposed a diagnostic overclaim; capture-internal cleanup is now
reported unverified independently of helper-owner finalization. Full canonical
check passed at 845b8f1; final completion and 185 focused tests passed locally at
50f9817 (macOS 27.2 arm64). The existing Live required gate now requires both-host
completion receipts as well as resource receipts. Subsequent Live 40751031818
attempt 1 and required gate 123078686977 passed at executed source cccd12c9
(same tree as PR head f58eebc). Both saved host campaigns and completion logs
passed source/host/checksum replay. The [G1 acceptance review](reviews/v06x-go-fixture-acceptance-review.md)
recommends accepting bounded G1 evidence; Human acceptance/main adoption,
Qualification and release remain separate. P1/EP1/EG1 are still required.

**P1 prepared entry — implementation approved, acceptance pending.** The
[Python entry design](reviews/v06x-python-fixture-entry-design.md) and
[conditional decision](decisions/p1-prepared-entry-implementation.md) authorize
PrepareCommand plus readable owned diagnostics and worker-local stop after
cleanup debt. The contract/checker explicitly authorizes G1 and P1. Existing
None/callable semantics, including ignored callback returns, stay intact.
The pre-code characterization below is historical; current implementation and
source-bound local results are recorded in the later checkpoint.
The [local pytest reporting characterization](reviews/v06x-python-fixture-reporting.md)
now closes the annotation-feasibility question at source 1780db3: seven controls
on Python 3.11/pytest 7 and Python 3.14/pytest 9 preserve original setup/cleanup
failures and render a narrowly targeted note. It also observes that current
child cleanup failure does not stop the next body. P1 therefore needs an owned
admission-debt guard and honest final summary, not a replacement error-reporting
framework. This fake-owner probe is not physical cleanup or P1 runtime acceptance.

Wire sufficiency remains an explicit verification obligation. Cross-check the
current protocol/capability inventory with actual driver/framework behavior,
including preparation, metadata, prepared/results, pools/reconnect/session
lifecycle and failure paths. Reuse completed Prepared/routine/multiple-result
evidence under its recorded scope instead of reopening it wholesale. Selected
examples prioritize gaps but do not define or silently shrink the capability
space: classify uncovered paths and record explicit reach/defer decisions.
Native-success/guest-failure differences must retain original evidence and be
classified as wire, SQL semantics, configuration or client/environment issues
before choosing a fix. This direction authorizes investigation and verification
planning, not blanket protocol implementation, guest changes or wider support
claims. The [P1 wire reconciliation](reviews/v06x-p1-wire-reconciliation.md) now pins
main 2ad041c and explicitly records its terminal-worker guard; dispatch and
capabilities match the earlier cc00ccd inventory. The v0.5.3 inventory remains
historical; Prepared, text multiple results and SET_OPTION are already adopted.
Exact workload/driver coverage and finite exit criteria still need to
be fixed before declaring the whole v0.6 dogfood scope complete.

**North-star discussion recorded with the Human, 2026-10-18:** reduce the work
of establishing and growing database tests in both new applications and existing
systems without tests, so developers can focus on features and their behavior.
Aim for use without learning special conventions (for example, one added line
redirecting existing connections), understandable import of existing preparation
data, independent reusable test workflows across frameworks, accessible official
MariaDB compatibility references, and failures that explain the known context
and next action to humans and coding assistants. Evaluate first-test setup,
next-test authoring and execution time separately. The intended niche is a
Docker-free library that reduces environment setup, test-authoring and cleanup
work compared with assembling a container-based workflow. This is not a claim
of universal superiority over Testcontainers: existing container infrastructure
or a need for exact production MySQL behavior may favor that approach. See
[the north star, principles and objections](reviews/v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven).
This records product intent, not current support or implementation approval.
Enumerate the capability space before choosing representative tests; tests
prioritize gaps rather than define the whole scope. Version-specific acceptance
and any public-contract changes still require their own decision.

The [v0.6 capability map](reviews/v06x-capability-map.md) expands that intent into
existing foundations, gaps, unverified coverage and dependencies. It proposes
connected designs for entry/routing/lifecycle, preparation/import and
compatibility/actionable failures. The Human agreed to this planning direction
on 2026-10-18; implementation scope and API choices are not yet approved.
All capability axes remain visible before selecting tests.
The [connected workflow design options](reviews/v06x-workflow-design-options.md)
compare connection injection/adapters/interception, preparation paths and
actionable diagnostics under one lifecycle. The Human approved this comparative
design direction on 2026-10-18; source investigation proceeds with the existing
Snapshot contract in the cross-check basis. Mechanisms remain alternatives,
not approved implementations.
The [first routing/preparation source findings](reviews/v06x-routing-source-findings.md)
pin the pgmem reference and distinguish new, idle-pooled and active connections,
including the different scope of its Python and Go helpers. The
[MySQL workflow continuation](reviews/v06x-mysql-workflow-source-review.md) records
pinned driver/framework seams, concrete upstream dump/migration input inventory,
and diagnostic/official-reference requirements. Source investigation now supports
a bounded prototype proposal; runtime validation, mechanism selection and broader
driver coverage remain unfinished. No routing compatibility support is established by that source investigation.

**Connection switching — adopted on main; unreleased.**
On2026-10-24 the Human approved integrating candidate
`204f106264def67d32da8ac7733be052c928a26c` after
[CI40061580952](https://github.com/masahitojp/mariamem/actions/runs/40061580952).
Both native OSes passed17 control cases, six exact injected defects, and4 real
marker/preparation tests with2 workers;3.11/3.14 compatibility and canonical
source checks passed. Ubuntu explicit Connector C retains its allowed SKIP;
default/pure ran. The [implementation/adoption record](reviews/v06x-shadow-maria-implementation.md)
contains saved native receipts, exact identities and the five follow-ups.
Main fast-forwarded from9f29194 to
`bbde3f559a57ebf57f3d8d7ca2df8b530c7cde1f`; its non-documentation tree is
identical to the tested204f106 candidate. A subsequent documentation-only
commit records that landing and does not replace its CI source identity.
Qualification, version placement and release remain separate. The following
paragraphs preserve the earlier investigation and approval sequence; their
implementation/adoption-pending statements describe those stages.
The [post-Prepared routing design](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-design.md)
reuses the existing source findings and compares explicit injection, framework
adapters and scoped Python driver routing. It proposes a bounded real-guest
spike with pool-generation, concurrent-scope, expired-target and original-endpoint
sentinel oracles; Go keeps child-owned configuration/pools. The Human approved
spike execution after design commit `dfa6b21`. The
[native result review](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-human-review.md) records
[CI40026373681](https://github.com/masahitojp/mariamem/actions/runs/40026373681)
at prototype `dd3b44d`:13 executed cases PASS and4 deliberate defects detected
on each OS. Connector/Python's default/prepared path passed on both; explicit C
is SKIP on Ubuntu because its extension requires a newer OpenSSL symbol. The
[local checkpoint](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-spike.md) retains its earlier
Homebrew import SKIP. That review found missing explicit old-session-state (R2)
and unknown-physical-ownership (R3) oracles, so the13-case CI did not close the
full approved spike. On2026-10-24 the Human authorized proceeding
with [productization design and those two checks](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-product-design.md)
for scoped Python routing plus a SQLAlchemy adapter and explicit
injection/child-owned Go pools. The
[completion and implementation review](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-implementation-review.md)
confirms [CI40032530547](https://github.com/masahitojp/mariamem/actions/runs/40032530547)
at `2851246`:15 cases PASS and all six deliberate defects detected on each OS.
Same-child session-state reuse and unknown physical ownership are now explicitly
checked, with zero control original-endpoint attempts and completed host cleanup.
That bounded campaign passed; Ubuntu explicit C retains its allowed environment
SKIP, while required default/pure actually ran. Its subsequent review identified
additional gate/schema/TLS conditions, recorded below rather than silently
counted as covered by those15 cases.
The design proposes early registered-profile protection before application
imports and explicit engine enrollment, with the saved advanced Connector
factory boundary visible for Human Review. On2026-10-24 the Human conditionally
approved production implementation and requested
[four review corrections](https://github.com/masahitojp/mariamem/blob/fbcb38e3cf00d620a5d39c8ac6df3ff4803ada21/docs/reviews/v06x-connection-routing-review-fixes.md):
strict fallback failure classification, schema-aware profile matching,
pre-install deferred required-TLS coverage, and explicit `ownership="test"`
disposal authority. The authored campaign now requires17 cases and six strict
mutations; [CI40035962925](https://github.com/masahitojp/mariamem/actions/runs/40035962925)
passed both OSes at `006f68d`, verifying those corrections with source-bound evidence.
Production implementation continues under that approval. Early pytest enforcement
and production cleanup remain implementation acceptance work. Main adoption
and release remain separate decisions; approval does not imply they have begun.
Preparation/import and broader framework coverage remain companion decisions,
not silently excluded from v0.6.

The [production candidate](reviews/v06x-connection-routing-productization.md)
is implemented on `feat/connection-routing` from current main `9f29194`, with
the [continuing routing contract](decisions/connection-routing-contract.md).
Optional public routing, explicit SQLAlchemy ownership and early pytest entry
are present; local32 routing tests pass on both Python3.9/pytest7 and Python3.14/pytest9.
The old fixture entry passed both-OS production acceptance at source
`0698698eb77bbb4df91aea0d83f62e901b711d77` in
[CI40045368302](https://github.com/masahitojp/mariamem/actions/runs/40045368302):
17 control cases, six exact defect injections and4 pytest tests with2 workers
on each OS. Ubuntu explicit Connector C is the known SKIP; default/pure ran.
This does not verify the subsequently approved marker/preparation entry.
On 2026-10-24 the Human removed EOL Python3.9/3.10 from future
verification. The routing compatibility job now uses Python3.11/pytest7
and Python3.14/pytest9; earlier3.9 receipts remain historical evidence.
The subsequent Human implementation authorization also raised current source
`python_requires` and advertised support to3.11+, dropping3.9/3.10. Published
release metadata remains historical. The earlier experiment is referenced at fixed commits rather than
merged wholesale. Main adoption is now approved; release remains separate.

The Human subsequently approved the marker-based user entry
`shadow_maria` and the recommended naming direction. The
[accepted entry design](reviews/v06x-shadow-maria-entry-design.md)
compares pgmem fork/live options with the current consuming-Snapshot contract.
After clarifying the difference from pgmem, the Human decided that0.6.0 excludes
preparation-time automatic connection switching, superseding the provisional
approval. Migration/seed receives preparation DB settings explicitly; registered
application connections are switched during the tests. The approved callback
entry is `mariamem_prepare`; direct test DB access is `mariamem_app_db`.
Controller/adapter names and extras are listed in the accepted entry design.
The [entry implementation](reviews/v06x-shadow-maria-implementation.md) now
uses the approved names and preparation callback. Local and CI compatibility
checks pass on3.11/3.14; updated native acceptance passed at204f106 and the
Human approved main integration. This is not final Qualification or release.
Automatic preparation routing is
[retained for0.6.x reconsideration](reviews/v06x-shadow-maria-entry-design.md#reconsider-preparation-routing-in06x),
not approved implementation. Shared modes are not approved by the naming
direction. The Human decided on
2026-10-24 that live behavior will be examined as a separate task; inclusion in
0.6.0 remains a scope decision based on the required internal changes. No
`live=True` behavior is currently implemented or implied by marker adoption.
The [live task and baseline examples](reviews/v06x-shadow-maria-entry-design.md#live-baseline-and-pending-task)
define the desired starting contents separately from which application,
endpoint and connection resources survive between tests.

**Preparation/import — recipe/stable tests adopted on main.**
The [preparation/import design](reviews/v06x-preparation-import-design.md) reuses
existing migration/dump source evidence and the adopted callback/marker. It
recommends a bounded actual migration-chain/seed-to-two-tests check first, while
keeping native-client and library dump import alternatives explicit. This is a
Human-approved bounded spike, recorded in the
[migration execution record](reviews/v06x-preparation-migration-spike.md); it is
not importer/productization approval by itself. Local macOS results and
[CI40072694488](https://github.com/masahitojp/mariamem/actions/runs/40072694488)
passed the authored Alembic/seed, two independent application tests and two exact
failed-preparation oracles on macOS/Ubuntu at84c8ee1. The
[Human Review](reviews/v06x-preparation-migration-human-review.md) recommends
recipe/acceptance productization. Its acceptance conditions retain native
Python3.11/pytest7 and Python3.14/pytest9 coverage plus migration-specific xdist
worker preparation/isolation checks on both OSes. These conditions passed in
[CI40079827071](https://github.com/masahitojp/mariamem/actions/runs/40079827071)
at exact source_commit `94d51e6ea6a663aaabfee92d2103bae1c7fefbf4`. The Human has now approved proceeding with the
[recipe and stable-test productization candidate](reviews/v06x-preparation-migration-productization.md).
The [explicit Alembic recipe](preparing-test-data.md) is implemented; the expanded
native acceptance matrix and receipt reassessment are complete. The
[main-adoption Human Review](reviews/v06x-preparation-migration-adoption-review.md)
recommended the recipe/stable tests; the Human approved main adoption after
reviewing the completed acceptance. The
[selected main landing](reviews/v06x-preparation-migration-main-adoption.md)
retains production tests and supporting records, excluding the spike executable/workflow. This does
not approve an importer, Qualification or release.
Automatic preparation
routing remains excluded from0.6.0; live and broader diagnostics/framework
coverage remain separate decisions.

**Prepared Statements — complete and adopted on main.** See the final P6
completion/adoption entry below. The following sequence preserves the dated
investigation and implementation milestones; its pending statements are not
current remaining work. Python
`cursor(prepared=True)` and Go explicit DB/Tx/Conn Prepare remain required for the
one-line-switching goal; interpolation or application SQL changes are not a
substitute. The original [prepared alternatives/spike decision](reviews/v06x-prepared-design.md)
led to the [positive feasibility result](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-prepared-multi-spike.md)
with the public embedded mysql_stmt APIs, default multi-statement capabilities
and Connector/Python26.7.0. That experimental prepared implementation is not
adopted; its fixed capacities, incomplete type/result codec and named consumer
error/import differences remain explicit.

Main now supplies routine bootstrap, text multiple results and COM_SET_OPTION;
those prerequisites are complete, not work to repeat. The
[prepared production design](reviews/v06x-prepared-product-design.md) proposes a
separate versioned guest path, typed dynamic buffers, prepared CALL multiple
results, no-response lifecycle and finite P1–P6 acceptance. It distinguishes the
native-parity C-extension syntax-error exception proposal from the unchanged
original1064 FAIL. The Human approved production implementation after that design review.
[Staged implementation](reviews/v06x-prepared-implementation.md) has P1 owners,
protocol, lifecycle dispatch and unit coverage. Its source compilation and
both-OS unit CI passed; expanded native12.3.3 PREPARE controls passed. The subsequent
development gate passed the new-guest smoke and exact installed binding checks
on both OSes. Its actual wire/native metadata comparison exposed a C API numeric
flag leaking onto the wire; the host-serializer repair passed the corrected
[both-OS gate39540250744](https://github.com/masahitojp/mariamem/actions/runs/39540250744)
at3496095, including actual P1 lifecycle and native metadata equivalence.
P2 typed-value/client decoder and binary-row components passed both-OS units in
[CI39548803322](https://github.com/masahitojp/mariamem/actions/runs/39548803322)
at0ceca7c. EXECUTE source compilation and both-OS units passed in
[CI39554451701](https://github.com/masahitojp/mariamem/actions/runs/39554451701)
at00962f8; that run intentionally skipped development runtime execution.
The new guest has now been translated with the fixed converter/13 patches and
its three allocation/lifetime functions and TLS data reviewed for a single exact
binding. [Binding evidence](reviews/v06x-prepared-p2-binding-evidence/reproduce.md)
records50 local input/guard checks PASS. The first full P2 development gate
[39561037019](https://github.com/masahitojp/mariamem/actions/runs/39561037019)
passed generation/compile/SQL smoke and exact installed bindings on both OSes,
but a new mutation test changed an earlier unrelated literal instead of its
target function. The [test-only repair](reviews/v06x-prepared-p2-mutation-fix/receipt.json)
scopes the mutation to that function and passes12 focused checks, including an
earlier-same-literal regression. The corrected
[gate39565377640](https://github.com/masahitojp/mariamem/actions/runs/39565377640)
passed those12 mutations and actual P1 comparison on both OSes. Actual P2
comparison now exposes one TIME column-length difference (16 vs native23), with
all22 cases' binary rows/terminals matching. The [bounded internal-source proposal](reviews/v06x-prepared-p2-time-metadata.md)
was approved by the Human on 2026-10-21 after the upstream-history investigation.
The2011 change redefined MAX_TIME_WIDTH23→16 while the embedded call retained
that name; the ordinary call switched to the newly introduced full-width23
constant. The one-line repair is now staged only in guest/experimental.patch
with complete source pre/postimage and patch hashes. [Repair evidence](reviews/v06x-prepared-p2-time-repair/receipt.json)
records61 local checks and13 additional native TIME cases PASS, plus an unchanged
22-case native replay. [Source preflight39572844101](https://github.com/masahitojp/mariamem/actions/runs/39572844101)
passed source and both-OS units at4f41be8. The patched guest's exact allocation/
lifetime bodies, full data and TLS match the previous reviewed output; only
one raw generated part changes. [TIME binding evidence](reviews/v06x-prepared-p2-time-binding/receipt.json)
records the new single identity and62 local checks PASS. The full
[gate39577305621](https://github.com/masahitojp/mariamem/actions/runs/39577305621)
atf498396 passed all5 jobs. [Result evidence](reviews/v06x-prepared-p2-time-result/receipt.json)
confirms actual P1, original22-case P2 and extra13-case TIME/native comparison
PASS on macOS arm64 and Ubuntu x86_64, plus smoke and13 binding tests per OS.
The bounded TIME repair is verified for that matrix. The
[additional P2 matrix](reviews/v06x-prepared-p2-matrix.md) now defines20 independent
DML/warnings/schema-reprepare/type/SQL-mode controls, all PASS against fixed
native12.3.3. Actual [gate39582653522](https://github.com/masahitojp/mariamem/actions/runs/39582653522)
passed original probes on both OSes but exposed a BIT16 timeout/DB termination;
only the first2 scenarios matched, while the next17 were not independently
assessed after that shared DB died. The [test-isolation repair](reviews/v06x-prepared-p2-isolation-evidence/receipt.json)
uses a fresh root DB/host for each of the same20 scenarios and captures logs/
teardown errors;6 local controls PASS. The isolated
[gate39585983268](https://github.com/masahitojp/mariamem/actions/runs/39585983268)
atd11f4ff independently matches12 scenarios on both OSes and fails8: seven raw
parameter type inputs time out; schema-add returns2057 and leaves following SQL
out of sync. Previous P1/original22/TIME13 and smoke/binding gates still PASS.
[Failure assessment and bounded repair proposal](reviews/v06x-prepared-p2-blockers.md)
preserve exact captures and separate observed harm from source inference.
The Human approved the bounded two-part repair continuation. The
[source candidate](reviews/v06x-prepared-p2-repair.md) preserves raw parameter
types and rebuilds changed result metadata without SQL retry. Its91 focused
macOS component checks and15 added fixed-native controls PASS. The
[source preflight39596726209](https://github.com/masahitojp/mariamem/actions/runs/39596726209)
passes source/both-OS units at68fb5c2. The
[new guest binding review](reviews/v06x-prepared-p2-repair-binding/reproduce.md)
verifies guest41ab4076 through the fixed converter/13 patches: all3 lifetime
function bodies, full data and TLS match the previous guest; memory initialization
is checked/pinned too. Local94 checks PASS.
[CI39601636017](https://github.com/masahitojp/mariamem/actions/runs/39601636017)
passes installed bindings/smoke/P1/22/TIME13/additional20 on both OSes; those former
eight failures no longer reproduce. The final15-case gate fails seven unsigned
NULL metadata cases, with values/termination/following SQL matching. The
[parameter-order continuation](reviews/v06x-prepared-param-order.md) fixes the
descriptor assignment before conversion/NULL handling in both embedded paths,
within the approved binding scope. Local102 checks and extra2 native controls
PASS. [Source CI39607505031](https://github.com/masahitojp/mariamem/actions/runs/39607505031)
passes guest-source and both-OS units at a342f30. The
[parameter-order binding review](reviews/v06x-prepared-param-order-binding/reproduce.md)
verifies new guest4dad84d0 with unchanged converter/13 patches, full lifetime
bodies, data/TLS and memory initialization; local103 checks PASS. Both-OS actual
runtime/native confirmation now [PASSes at5146d8a](reviews/v06x-prepared-p2-pass.md)
in [CI39616628715](https://github.com/masahitojp/mariamem/actions/runs/39616628715):
all72 typed scenarios per OS, P1, smoke and17 installed binding mutation tests.
The specified P2 development acceptance row is satisfied; P3–P6 and full
production acceptance remain unfinished. The [minimal P3 source candidate](reviews/v06x-prepared-call-minimal.md) now adds
owned binary result chains and an OUT+two-results native reference. Local106
Python/C checks, three Go race packages and native replay PASS.
[Source preflight39624071363](https://github.com/masahitojp/mariamem/actions/runs/39624071363)
passes guest-source and both-OS units at46f5c2c. The
[P3 binding review](reviews/v06x-prepared-call-binding/reproduce.md) records new
gueste6d6021a, its64-byte data/BSS layout shift, exact complete functions/init,
unchanged TLS content and107 local ownership checks PASS. Only that new guest
is accepted. [CI39631360824](https://github.com/masahitojp/mariamem/actions/runs/39631360824)
now [passes the minimal CALL](reviews/v06x-prepared-call-pass.md) on both OSes at42be2b5,
including exact native metadata/rows/status, OUT, terminal OK, following SQL and
Close/PING. P1/all72 P2 controls and18 installed mutations also PASS per OS.
The minimal P3 feasibility gate is closed. The [full P3 candidate](reviews/v06x-prepared-p3-matrix.md)
then matches11/13 baseline cases and exposes two unnegotiated-OUT differences.
A bounded Go bridge negotiation fix now passes all14 native/guest cases on macOS,
including paired flag states and advertisement; P1/all72 P2 and smoke remain PASS.
Local112 Python/C and3 non-race Go package checks PASS. Fresh exact-candidate
[CI39686154515](https://github.com/masahitojp/mariamem/actions/runs/39686154515)
now [passes the full P3 row on both OSes](reviews/v06x-prepared-p3-pass.md)
at6fc594a: all14 cases match native, negotiated capability states and following
QUERY/CLOSE/PING PASS, and previous P1/all72 P2 controls, smoke,112 Python/C
checks, three Go race packages and18 installed mutations PASS per OS.
P3 development acceptance is complete; P4–P6 and production acceptance remain unfinished.
The [first P4 lifetime slice](reviews/v06x-prepared-p4-lifetime.md) adds native-controlled
Go DB/Tx/Conn/pool, RESET/transaction/type reuse, malformed lifecycle adjacency,
engine quota recovery and idle QUIT/EOF cleanup. Native capture/replay7/7 and
local114 Python/C plus3 Go race packages PASS. A bounded handwritten-host
CLOSE/RESET length repair leaves guest/converter/generated identities unchanged.
[CI39699613828](https://github.com/masahitojp/mariamem/actions/runs/39699613828)
now confirms all7 cases on both OSes at ecfea4a with no native differences:
active connections return0, temporary directories are removed, and the Go
consumer restores native statement counts/open connections to0. P1/all72 P2/
all14 P3/minimal CALL, smoke,114 Python/C checks,3 Go race packages and18 binding
mutations also PASS per OS. The first lifetime slice is complete. LONG_DATA,
executing-query cancellation/disconnect and the remaining resource/failure
matrix are still P4 work; this first slice does not close or narrow P4.
The [LONG_DATA source candidate](reviews/v06x-prepared-long-data.md) now forwards
chunks to the public embedded API, retains only parameter-presence/deferred-error
state in the bridge, and adds omission/NULL/type reuse plus reset/close handling.
Native25-case capture/replay PASS, including1MiB aggregate crossing, index64 and
native1105 capacity/error recovery. Local118 Python/C checks and3 Go race
packages PASS. Source CI39714836816 passes guest build and both-OS units at425c821.
The [exact new guest binding](reviews/v06x-prepared-long-data-binding/reproduce.md)
passes local source-only checks: three lifetime functions, full initializer and
TLS remain identical; data identities and the single guest pin are updated, and
prior P3 input is explicitly rejected. Actual both-OS runtime acceptance remains
pending; source/unit success is not LONG_DATA/P4 completion.
[Runtime CI39718930329 failure analysis](reviews/v06x-prepared-param-metadata.md)
now confirms both-OS generation/previous regressions PASS and LONG_DATA strict
comparison FAIL: aliased parameter names were incorrectly fixed to `?`.
The engine-owned metadata extension now passes source CI39724676227 at ab8c350.
Its [new exact binding](reviews/v06x-prepared-param-metadata-binding/reproduce.md)
records the BSS+64 layout, unchanged TLS and complete function/init/data pins;
local122 checks and the formal source-only adapter PASS.
[CI39729456821](https://github.com/masahitojp/mariamem/actions/runs/39729456821)
now [closes LONG_DATA and parameter-metadata development acceptance](reviews/v06x-prepared-long-data-pass.md)
at fba09f6 on both OSes: all25 native comparisons match including parameter names,
connections return0 and temporary areas are removed. Previous P1/all72 P2/all14
P3/first7 P4 gates, smoke,122 Python/C checks,3 Go race packages and20 installed
mutations also PASS per OS. Native fixtures/comparator remain unchanged.
Full P4 still requires executing-query cancellation/timeout/disconnect and the
remaining resource/failure matrix; P5/P6 and production acceptance remain pending.
The next [P4 active-exit candidate](reviews/v06x-prepared-p4-active.md) adds
execution-witnessed cancellation/deadline/TCP exits and Close with independent
Fork/baseline cleanup controls. Native5-case controls PASS; actual both-OS7-case
guest acceptance now PASSes on macOS15 arm64 and Ubuntu24.04 x86_64 at
[CI39747013913](https://github.com/masahitojp/mariamem/actions/runs/39747013913),
source_commit fbe419613cc0cc99657d39543c37df7b4dfe5d4a. Execution witnesses,
target invalidation, healthy sibling/baseline reuse and final cleanup all PASS;
134 Python/C checks,4 Go race packages and prior runtime gates also PASS.
Full P4 still needs the remaining failure/resource matrix; P5/P6 are open.
A bounded shared-control status classification
repair preserves unusable for fatal deadlines while keeping request timeout
classification. No guest/converter/Generated Go input is changed.
The [P4 failure/resource closure candidate](reviews/v06x-prepared-p4-failures.md)
now maps every finite P4 obligation to existing actual runtime evidence and
focused component controls. Local macOS134 Python/C checks and4 Go race packages
PASS, including16,884 injected owner-allocation/serializer failures and two
negative oracle mutations. Both-OS component CI now PASSes at86b89d8 in
[CI39752222349](https://github.com/masahitojp/mariamem/actions/runs/39752222349):
134 Python/C checks,4 Go race packages, canonical inventory and public sources
PASS on each OS. With the existing actual-guest/native evidence, the finite P4
row is complete. Guest-source/runtime jobs were explicitly SKIP for this
tests-only candidate; no new actual guest campaign or real-engine OOM injection
is claimed. P5 real consumers/regressions and P6 canonical/J1/independent
generation remain open.
The [P5 real consumer candidate](reviews/v06x-prepared-p5-consumers.md) adds
fixed Go explicit/implicit Prepare and Connector26.7.0 pure/default/C observations,
private source-bound wheel staging, current integration/routine/auth and existing
SQLAlchemy/GORM anchors. Local native Go modes and Python CRUD/typed binary/text
controls PASS, but native Python prepared CALL result traversal and C untyped
NUL projection expose new functional failures. Their original FAIL oracles are
retained; separate native-matching diagnostics cannot grant functional acceptance.
[CI39760963205](https://github.com/masahitojp/mariamem/actions/runs/39760963205)
passed the fresh Linux Python3.14 native control, both-OS units/source build,
and Ubuntu actual guest consumer matching plus installed/ORM regressions.
Mac guest observations were captured, but matching failed because Linux lacked
a native C-extension control; subsequent Mac regressions were skipped.
The [comparison-gate diagnosis](reviews/v06x-prepared-p5-ci-diagnosis.md) supplies
a separate Mac Python3.14 native control with client binary/source/ABI binding;
[corrected CI39769591459](https://github.com/masahitojp/mariamem/actions/runs/39769591459)
now passes all six jobs on exact source_commit
`c5dddf36aac2d62cfe8d4edd22b41fb8da7fdd9b`: both-OS native matching,
installed regressions and existing SQLAlchemy/GORM anchors. Mac C client
binary/source/ABI binding passes; Ubuntu's additional C mode remains an explicit
OpenSSL import SKIP, with required pure/default executed.
After the [P5 Human Review](reviews/v06x-prepared-p5-human-review.md) and
additional MariaDB-driver replay below, the Human explicitly accepted the two
precise Oracle Connector/Python26.7.0 limitations on 2026-10-22.
The [decision](decisions/prepared-consumer-exceptions.md) records **P5 evidence
complete with accepted consumer exceptions**, permitting continuation to P6.
Prospective functional FAILs remain FAIL; no unconditional functional PASS,
main adoption, release version or publication is approved.
P6 canonical independent generation/J1/provenance and permanent edge/consumer
CI placement remain unfinished. The Human requested an additional
[MariaDB Connector/Python replay](reviews/v06x-prepared-mariadb-replay.md)
before continuing the exception decision. Fixed stable1.1.14 passes both exact
case purposes against native12.3.3 using Linux/arm64 Python3.14/ConnectorC3.4.9;
[CI39776208952](https://github.com/masahitojp/mariamem/actions/runs/39776208952)
now passes all six jobs at exact source_commit
`4ce9422e8b5a49727f9a1e3ee81706545e4a8f0d`. Both real-guest Mac/Ubuntu
replays preserve all NUL bytes, drain both prepared CALL results, execute
subsequent SQL and close cleanly; server counters confirm binary execution.
The [results](reviews/v06x-prepared-mariadb-results.md) retain native comparison,
actual Python/ConnectorC versions and driver hashes. The original Oracle
Connector/Python26.7.0 functional FAILs remain; their later Human acceptance is
recorded separately in the decision above, not rewritten into the CI receipts.
The replay establishes the two tested MariaDB-driver paths, not general driver
support. Runtime/guest/converter/canonical generation inputs remain
unchanged, and no default connection is forced to pure mode.


Apart from the explicitly accepted consumer exceptions above, no further
scope reduction is accepted. Main adoption, target version, Qualification and
release remain separate decisions. The MariaDB/lite4mariadb/converter/toolchain pins remain fixed.

**Approved documentation backlog — v0.6.x, 2026-10-17:** explain serial and
parallel Snapshot/Fork usage in the Go/Python guides. Lead Python test usage
with pytest fixtures: prepare migrations/seed once per worker, acquire an
independent DB per test, and let fixture teardown close it. Show ordinary
pytest versus pytest-xdist (`pytest -n 4`) and explicitly state that each xdist
worker owns its own session baseline. Separately show manual parallel Fork
calls sharing one live baseline in one process (Python ThreadPoolExecutor /
Go goroutines), with per-child SQL connections, errors propagated, and all
children joined before baseline Close. Label serial versus parallel benchmark
examples and compare elapsed time rather than overlapping operation sums.
This is documentation of existing behavior, not new cross-worker sharing,
automatic scheduling or a new public API. Implementation is deferred to v0.6.x.

Use real consumer/workload evidence, including Django, Alembic/migrations,
metadata-heavy and dbt-like workloads. Retain SQLAlchemy/GORM regression anchors.
Evaluate actual preparation, per-test isolation, resource and failure costs.
This scope also observes whether many simultaneously retained file-heavy
baselines produce process FD/resource pressure; a dedicated resource-model
change is reopened only if that evidence shows pressure.
This scope also decides per-DB connection-count tuning (currently fixed at 16)
from observed demand and resource effect.

New run-wide baseline fixture ergonomics are deferred here. Existing session
fixtures remain worker-local under xdist. Do not promise new framework/platform
compatibility or introduce automatic cache policy before use-case evidence.

**Wire practical coverage (v0.6.x scope):** main now serves text COM_QUERY,
COM_INIT_DB, COM_PING, COM_QUIT and COM_SET_OPTION, including text multiple
statements/results and the required handshake flags. Published v0.5.3 remains
the earlier text-only baseline. Server-side prepared commands are now adopted
on main through P6; see its final completion/adoption entry below.
COM_RESET_CONNECTION/pool session reset and other optional commands/flags remain
separate capability-map items; COM_STMT_RESET is not a session reset. Host framing
and guest semantics both need acceptance. No broader protocol implementation is
approved by this status entry.

The [v0.6.x kickoff notes](reviews/v06x-kickoff-notes.md) consolidate the wire gap
inventory, fixture/test UX findings, dump/binlog assessment, the stable-endpoint
verification theme, additional scope candidates and the suggested priority order.
Discovery notes only; not approval.

The [wire-relay feasibility memo](reviews/v06x-wire-relay-feasibility.md) records
an unverified question: whether the embedded guest can expose a real MySQL
endpoint that the host relays, as pgmem relays PostgreSQL's wire. It is not part
of the approved prepared spike, and no test has run.

## v0.7.x — Guest initialization optimization candidate selection

The Human scheduled selection of guest-initialization improvements for v0.7.x
on 2026-10-18. Reuse the child-lifecycle attribution and the v0.5.x bounded
Ubuntu parallel-startup investigation. Potential directions include guest
allocation/growth and collation initialization; no method, expected saving or
implementation is approved yet. The Human also scheduled large-scale tuning here,
specifically the 100MiB case and other preparation-heavy workflows where guest
initialization dominates. Config/host levers come before guest patches. This work
is outside the two v0.5.x actions above.

The [v0.6.x kickoff notes](reviews/v06x-kickoff-notes.md) record the strategy of
using pgmem only as a matched floor reference (after a matched measurement) and
the v0.6/v0.7 split.

## Development discipline

Keep **Explore → Challenge → Human decision → Implement → Verify**.
Verification scope follows the changed boundary; explain a concrete dependency
before broadening. See [development](development.md#local-verification).

**Bounded investigation policy approved, 2026-10-30:** record one decision,
finite exit and work/tooling/CI budgets before investigating. Initial defaults
are 2 hours active work, including 30 minutes measurement tooling, and at most
2 heavy CI submissions. Measurement-tool limitations do not automatically add
prerequisites; budget exhaustion produces a conclusion or explicit inconclusive
report with options/cost. Ordinary in-budget fixes remain autonomous. See
[the working rule](development.md#bounded-investigations). This authorizes the
development policy, not a resource campaign, product scope or release.

Experiments are disposable by default. Preserve compact measurements, reports,
hashes and reproduction inputs rather than recreatable caches, completed
worktrees/builds or source copies. Completion includes cleanup and a retained-path
audit. See the [workspace policy](experiment-workspace.md).

CI owns exact-source build, acceptance and release qualification after handoff;
a submitted verification run does not publish or approve a release.
See [release workflow](releasing.md).


## Prepared P6 canonical ownership — complete, adopted on main

The scoped P6 candidate is source_commit
`c7960d604f525c15d66fc003b0341989c4719267` against main baseline
`22a8c64305e706408ebcd54cfd7ecc45426802ad`.
[CI39859160329](https://github.com/masahitojp/mariamem/actions/runs/39859160329)
passes all four jobs with Go1.26.10: two independent canonical guest source builds,
both-platform99-file Go regeneration, J1 failure/protected/race controls, complete
prepared matrices, installed/ORM regressions, exact accepted consumer exceptions,
clean-host library audits and positive/17-negative build guards. Earlier dated
P6-pending statements describe prior milestones and are superseded here.

Canonical build/license ledgers now bind the original new-Go CI receipts;
no earlier compiler result is relabeled. Normal-CI selected consumers, exact
edge/profile mutation tripwires, ordered source patch ownership and public-guide
limits are in place. MariaDB guest identity remains
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
The [P6 Human Review](reviews/v06x-prepared-p6-human-review.md) recommended main
adoption. The Human approved main adoption on 2026-10-23. Main was fast-forwarded
to integration source_commit `eb4abca3bde4b29ece3af6f0e8a8f4d0b48a5b00`
from `experiment/prepared-p6-records`, including completion/evidence bookkeeping
without moving the CI-tested candidate ref. Its runtime/generation inputs are
unchanged from CI-tested source_commit `c7960d604f525c15d66fc003b0341989c4719267`;
the additional records and this approval entry are not new Qualification evidence.

The Human-requested `chore/go-1.26.10` update is included (source_commit
`0cf9970533f719c765ef2b19802e5c6a509d5b48`, cherry-pick9272889). The new compiler
was actually used for current CI host builds, generation and runtime checks.
Go1.27.3 is the forward-compatibility check pin, not a PASS claimed by P6;
its actual external-consumer run remains in later Qualification. Go minimum1.26.0,
MariaDB/WASIX/Binaryen inputs and converter13 patches are unchanged.
[GO-2026-6809](https://pkg.go.dev/vuln/GO-2026-6809) is the toolchain remediation
basis; no specific mariamem exploitability claim is made.

Main adoption is complete. Target version, final Qualification, Product Validation
and publication remain separate decisions and have not been initiated here.
No broader shared-memory proof or new
performance improvement is claimed. Guides use current-source-build wording and retain publishedv0.5.3 history.

## Bounded dump reader and host status prerequisite — adopted on main, unreleased

On2026-10-26 the Human explicitly approved two separately identified parts of
the [reviewed candidate](reviews/v06x-dump-reader-final-review.md):

1. **Host status prerequisite:** `internal/guest/guest.go` plus guest/mysqlwire
   tests, landed independently in commit `02b58b3`. Internal unsigned32 status is
   validated and projected to its low16 protocol flags.
2. **Bounded Python dump reader:** explicit `mariamem.import_dump`, the optional
   `dump` extra, maintained tests, [guide](importing-dump.md) and main/PR workflow,
   selected as a separate product commit on top of the prerequisite.

The landing is constructed directly from stable main
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a`; experimental/design history is not merged.
Runtime, SDK, tests and workflow match tested candidate
`e3c55ca14acd2e6813e8815bb96e4307b6b1d625`. Guide wording and this Human decision
record are adoption bookkeeping. Original
[CI40211613827](https://github.com/masahitojp/mariamem/actions/runs/40211613827)
and [saved receipt](reviews/v06x-dump-reader-evidence/ci-40211613827/assessment.json)
remain bound to that candidate; they are not Qualification or a PASS relabeled
to the new main SHA. The new main source is submitted to its normal workflows.

The supported format remains the finite MariaDB12.3.3 producer profile, with
explicit errors, source discard and independent prepared children. Go has no new
dump API. Parser maintenance remains bounded by the documented profile and native
differential gate. Views/triggers, other producers/MySQL/legacy/Django inputs,
large-input performance and cold/setup-cost claims remain outside this adoption.
Guest/generated code, canonical generation inputs, release ledgers and version
metadata are unchanged. Target version, Qualification and release remain separate
Human decisions.


**P1 conditional implementation approval:** the Human approved the concrete
Python entry design at de860c4, with the [pre-code definitions](decisions/p1-prepared-entry-implementation.md)
for inherited env overlay, bounded/truncated output, rejection of unknown inputs,
and public API/admission-change notices. PrepareCommand is explicitly a new
public class; cleanup debt stopping later dependent tests in the same worker is
explicitly an approved behavior change. None/callable semantics remain intact.
Required-host/minor runtime/resource acceptance, main adoption and release are
not granted by this implementation decision.

**P1 implementation checkpoint:** [conditional definitions and implementation](reviews/v06x-python-fixture-implementation.md)
now add the public PrepareCommand third input, bounded command execution and
worker-local cleanup-debt admission. None/callable meanings remain intact.
Public API/admission notices are in the Python guide and unreleased notes, and
the contract/checker explicitly authorizes G1 plus P1 against the pre-code
decision. Both-host/minor CI, P1 resource/time and installed-wheel evidence remain
required; no complete P1/main adoption/Qualification/release is claimed.

**P1 local implementation verification:** source bcc2938 (including main2ad041c)
passed the full canonical gate and both installed-wheel Python profiles on
observed macOS27.2 arm64. Each profile passed four real-guest configurations,
including two workers, committed mutation isolation and ordinary-failure recovery;
actual bundled-host/source binding and final process/temp cleanup were checked.
The [saved checkpoint](reviews/v06x-python-fixture-implementation.md#local-verification-at-bcc2938)
keeps raw logs/checksums and two rejected preflight controls. Required macOS15/
Ubuntu CI, fresh native command/pool control and full P1 time/resource/guard
campaign remain pending; this does not close P1 or authorize adoption/release.

**Final P1 local candidate e4b4700:** [saved verification and remaining acceptance](reviews/v06x-python-fixture-implementation.md#final-local-candidate--e4b4700)
record full canonical PASS (Python 1413/source 31, Go unit/vet), pytest 7.0.0
focused 95 PASS and four installed-wheel configurations per Python minor.
Strict JUnit totals prevent expected failures masking extra cleanup errors;
read-only diagnostic metadata and finalizer interrupts preserve original errors.
Newer source does not relabel bcc2938 or earlier receipts. Required-host CI and
full native/time/resource acceptance remain pending; main/release are separate.

**P1 required-host implementation CI confirmed:** Live40811260983 attempt1 and
its required gate succeeded at executed source3f8395b (tree equal to PR26 head
bbfb6346). The [source-bound receipt](reviews/v06x-python-fixture-implementation-evidence/ci-40811260983/assessment.json)
retains digest-verified artifact provenance and raw P1 results: four host/minor
cells, focused95 PASS each, four installed-wheel configurations each, strict
JUnit counts and final physical host/temp cleanup. Development, Django and dump
also passed. The [next native-control increment](reviews/v06x-python-fixture-implementation.md#next-acceptance-increment--p1-native-control-execution-pending)
is implemented for the existing disposable MariaDB12.3.3 service but awaits its
own CI; the previous run does not prove it. P1 time/resource/retention/guard
campaign, full P1 completion and main/release decisions remain open.

**P1 native plus required-host correctness confirmed:** Live40829538394 attempt1
and required gate123316058837 passed at executed source5a9f317 (tree equal to
PR26 headde28c547). The [checksum-bound receipt](reviews/v06x-python-fixture-implementation-evidence/ci-40829538394/assessment.json)
preserves native command/callback results on both Python minors with final schema
count0, and four installed-wheel host/minor cells (focused113 PASS and four
runtime configurations each). Development/Django/dump also succeeded. Earlier
receipts retain their sources. The [next counter-feasibility increment](reviews/v06x-python-fixture-implementation.md#resource-counter-feasibility-increment--required-host-results-pending)
checks child FD/unlinked-file observation before the full time/resource campaign;
its required-host CI is pending. Counter feasibility is not P1 workload/resource
acceptance. Full P1 completion, main adoption, Qualification and release remain
separate unfinished work.

**Ubuntu Live40843725436 failed in the G1 collector before P1:** the cap1/
parallel1 Go mode completed with cleanup, but a zero-RSS observation had no exit
confirmation at poll time. The [source-bound diagnosis and original FAIL](reviews/v06x-go-fixture-campaign.md#ubuntu-zero-rss-before-waitpid-confirmation--run40843725436)
preserve source5738eae and artifact hashes; no P1 probe PASS follows. A bounded
50ms exit confirmation now retains terminal and failed zero samples separately;
live-zero timeout/nonzero exit still fail, and resource limits are unchanged.
Both focused Python suites pass135 locally; the corrected source needs fresh CI.

**Corrected collector and FD probe CI confirmed:** Live40846147295 attempt1 and
required gate123375744109 passed at sourcebd3ab3f (tree equal to head e5350bc3).
The [checksum-bound receipt](reviews/v06x-python-fixture-implementation-evidence/ci-40846147295/assessment.json)
replays both-host G1 campaign/guards; Ubuntu preserves two actual bounded-wait
zero-RSS terminal observations. Four P1 host/minor cells each pass125 focused
tests, four installed-wheel cases and the FD/logical-byte probe. Native controls
and Development/Django/dump also pass. Original failed receipts keep their source.

**Next allocation-counter increment:** the [test-only allocated-block observer](reviews/v06x-python-fixture-implementation.md#allocation-observer-increment--required-host-execution-pending)
uses Linux procfs or a Darwin SDK helper; no mariamem host/API/guest change is
made. Clean local source1fc771e8 passes258 focused tests per Python minor with
actual child fstat equality, descriptor deduplication and final cleanup. A one-byte
control separates allocated4096 bytes from logical1 byte on observed macOS27.2;
the initial nondistinguishing sparse control remains a recorded failed probe.
Required-host allocation CI and the full P1 time/resource/retention/guard campaign
are pending. Workflow/Go cache key are unchanged. Main adoption and release remain
separate decisions.

**Allocated-counter matrix confirmed:** Live40856524755 attempt1 and required
gate123395867624 passed at source81cf7a4, tree equal to head30c9e2a0. The
[checksum-bound receipt](reviews/v06x-python-fixture-implementation-evidence/ci-40856524755/assessment.json)
confirms allocated-block/fstat equality, FD deduplication and restored baseline
in all four host/minor cells, plus focused135 and four installed-wheel
configurations each. Native, Development, Django and dump also passed. This closes
counter feasibility, not full P1 resource acceptance.

**Three-time campaign checkpoint implemented:** the [fixed orchestration and evidence](reviews/v06x-python-fixture-implementation.md#three-time-checkpoint--local-source2fa14975-required-host-execution-pending)
measure first setup, adding only the second test, and four-case warmup/three-repeat
batches through the supplied entry with workers1/2. Shared input hashes enforce
no repeated lifecycle edits; real status observations prove held SQL peaks2/4.
Local source2fa14975 passes281 focused tests and all five actual-guest outer tests
per Python minor, sequentially, using a stamped source-SDK host on macOS27.2.
Acquisition/cold/human time is unmeasured. Required-host installed-wheel timing,
retained baselines1/2/3, aligned resource counters and resource STOP/mutations
remain pending. Workflow/cache key and product/guest/API are unchanged by this
increment; full P1 acceptance/main/release remain separate.
