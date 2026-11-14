# mariamem project status

This document owns current state and approved direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns implementation, and [decisions](decisions/snapshot-product-contract.md) own
continuing constraints. GitHub Issues own actionable checklists and milestones.
Version themes and candidate adoption do not authorize a release.


## MemoryEA direct panic with noinline — product verification authorized (2026-11-15)

The Human authorized product verification under [Issue182](https://github.com/masahitojp/mariamem/issues/182).
The minimal canonical candidate is generated and its provenance/license bindings
updated. MemoryEA uses direct panic with explicit noinline; bounds arithmetic,
guest Wasm and SQL are unchanged. Local current-main P1/P4/P8 paired suite
medians improved by 2.65/11.49/10.11%, but only 3/5 pairs at each P were faster.
The actual host is 96 bytes smaller and wheel 70 bytes larger: effectively no
distribution growth. These are bounded, shared-Mac observations, not guarantees.

[Product verification and all process observations](../benchmarks/memoryea-product/README.md)
record correctness, source identities and limits. The known Connector/Python /
OpenSSL 4 failure is explicitly excluded by the Human from this task's blockers;
no investigation is authorized. Existing exact-SHA CI owns remaining platform /
consumer qualification. Main integration and publication remain separate Human
decisions; local results do not establish READY.

## Evidence retention approved (#158, 2026-11-14)

The Human approved retaining continuing decisions in existing ADRs and deleting
obsolete reviews/raw evidence. No new archive branch, evidence repository or
mandatory release-asset migration is required. Active fixtures and indispensable
unique observations remain with their maintained owners; provenance/license and
release contracts remain unchanged. See [the retention decision](decisions/evidence-retention.md).
#158 owns the cleanup and before/after measurements; this direction does not
claim the entire historical backlog is already removed.


## Buffer-pool descriptor zeroing — CI complete, adoption pending (2026-11-14)

The minimal product candidate is source_commit
`2e1ecd315e4f85d5a7112112ad0858e8dc6765de`, against measured main baseline
`eeef899a296be8aa38cc9e3de0a550c428d4dca9`.
[CI43569024494](https://github.com/masahitojp/mariamem/actions/runs/43569024494)
passed two independent C builds, both-OS full120-file regeneration, normal
check/integration and focused buffer controls. The
[saved evidence](reviews/buffer-zero-ci-43569024494/README.md) binds those original
receipts; later integration bookkeeping is not a new CI result.

The change is confined to WASIX/Emscripten `buf_pool_t::create()` allocation
and descriptor initialization. Common allocator zeros, 2MiB extent alignment,
original-pointer free, default16MiB, grow and non-WASM behavior are retained.
No experiment mode/env/poison/abort enters product behavior.

The [two fixed comparisons](../benchmarks/forkcost/buffer-zero-candidate/README.md)
show P1 Fork5.3/8.7% faster. P8 Fork improvement is not stable; P8 suite improves
4.6/7.1%, while P1 suite changes from2.5% faster to12.6% slower. Preserve both
series and all outliers; do not promise a universal speedup. The
[integration review](reviews/buffer-zero-main-review.md) recommends adoption for
bounded Fork initialization savings, with this whole-suite limitation explicit.
Main integration and release remain separate Human decisions. Existing
Connector/Python/OpenSSL4 acceptance is retained; no new engine/driver inquiry
or pgmem measurement is requested here.

## PyPI distribution direction (2026-11-14)

The Human approved #159 implementation: begin with the existing 0.6.2 macOS
arm64 wheel, then reuse the same publication/recovery path for normal stable
releases. The PyPI Trusted Publisher is registered for `masahitojp/mariamem`,
`release-candidate-ready.yml`, environment `pypi` (Human confirmation).
The Human subsequently approved the initial 0.6.2 macOS upload.
[Run 43567522416](https://github.com/masahitojp/mariamem/actions/runs/43567522416)
authenticated and uploaded successfully (HTTP 200), but the immediate public JSON
lookup reported the wheel absent and stopped before smoke. A later JSON read
confirmed the original wheel hash. [Attempt 2](https://github.com/masahitojp/mariamem/actions/runs/43567522416/attempts/2)
completed publication and PyPI-installed smoke successfully: exact wheel/hash,
SELECT 1 and Close/host exit. The 0.6.2 macOS PyPI transaction is complete.
That recovery used the original implementation; the bounded visibility-wait fix
is covered separately by regression tests. Stable versions only; no alpha/beta/rc on PyPI.
Transport failure reuses the same version/source/bytes instead of forcing a
version bump. Hash conflicts stop, and successful smoke reuse binds exact
artifacts and check conditions.

0.7.0's later work is split: #170 Linux x86_64/arm64 manylinux and musllinux;
#171 Windows x86_64/arm64 and limited initial acceptance; #172 ordinary CI
selection and duplicate-build cleanup; #169 all-target public smoke and guide
consistency. macOS-first sequencing does not reduce that scope. #158 remains
the independent required distribution/evidence-size cleanup. New platforms need
initial boundary acceptance; public smoke stays install/hash/start/SELECT 1/Close,
not a repeated ORM/Snapshot campaign. Windows ordinary releases use short smoke,
with focused additional checks when relevant OS boundaries change.

## Linux distribution initial acceptance passed (#170)

The Human approved proceeding after the sequencing review. Candidate
`0f3cb82ad46be613a164c49b38f9a2dfa61f09d4`, based on main
`291467b4fbac143093b35ea15d16cda798590f97`, passed
[CI43574710937](https://github.com/masahitojp/mariamem/actions/runs/43574710937).
CI source `74ce30e5ec89221c27822980f41f7d643495c3d9` has the same tree as that
candidate; this equivalence does not relabel a receipt to a different commit.
Both native Linux CPUs passed memory/image/atomic checks, then the same wheel
per CPU passed installed SQL, Snapshot/Fork independence and Close/host exit on
glibc2.28 and musllinux1.2 containers. These share the modern runner kernel;
no old-kernel execution, full per-OS ORM campaign or release qualification is claimed.

The change extends the existing host mmap/static-image and ARM64 atomic paths
without a guest patch. #158's minimum module boundaries and Python description
accompany it; full evidence cleanup remains required. #172 owns later CI selection/
duplicate-build consolidation; #169 connects the accepted portable inventory to
publication. Final guide/diagnostic wording reflects this CI checkpoint.

The Human approved main integration on2026-11-14. Main's subsequent #176
buffer-pool improvement (`bb1e937ae75b5788c8548a52987d9d42f78292d5`) is incorporated
into the candidate, preserving its new guest/generated code and fresh symbol audit.
The derived layout retains the same constructor values and binds the combined
handwritten sources. Required CI must accept this combined candidate before the
authorized automatic merge; the earlier CI is not reused as its PASS. A versioned
public release remains a separate Human decision.

## Prepared output — integrated on main (2026-11-14)

PR163 merged as `c129ab0e2d0d286da57b3be87d7d5e9cc2d3239c`. Normal PR CI
[43535618715](https://github.com/masahitojp/mariamem/actions/runs/43535618715)
passes all three gates on head `5793989ccdbe712eb54f5bc057643e7f65ba63d2`.
The main merge tree equals that head exactly, and its runtime remains the
accepted ef4d5cd9 source. These are identity/equivalence facts, not a CI receipt
relabeled to a different SHA. Engine/C/generated inputs and old evidence source
commits remain unchanged and reachable through main history.

Issue132's selected-route acceptance and Issue128's comparison/decision support
are complete and closed after the Human's integration approval. The unmeasured
update-hours, availability lead time, payback and recovery cost move to
[Issue164](https://github.com/masahitojp/mariamem/issues/164), to be recorded during
the next actually authorized LTS update. Closing128 does not establish measured
cost savings or authorize a new experiment. Earlier approval/pending sections
below describe their dated historical checkpoints.

The source change is adopted and unreleased. Release version, Qualification and
publication remain separate and unapproved. Issue138 remains stopped.

## Prepared output — main integration approved (2026-11-14)

The Human approved main integration after the
[Issue-criteria submission](decisions/prepared-output-reuse.md).
This includes its explicit selected-route test disposition: retain current host
oracles for unchanged owners, add raw-output boundary checks, and keep the absent
full-native controller/factory campaigns historical rather than claiming their
old PASS counts. Issue138 remains stopped and its unadopted failures are not waived.

Approved runtime source is `ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e`, on main basis
`eb175ae23292c1c40cfbeb4b9b73132873c4cc6f`. The integration branch preserves those
runtime bytes; later review and decision records are documentation only. The
[decision](decisions/prepared-output-reuse.md) owns the accepted boundary and
upgrade checks. Preserve evidence/fixture source ancestry during integration;
normal CI must check the concrete PR before merging. Earlier dated recommendation
and pending-approval entries below retain their original historical context.

The accepted benefit is reduced custom output conversion responsibility. Total
upgrade-hours, time to a new LTS, payback, peak RSS and two-series runtime acceptance
remain unmeasured. Track actual future update costs in Issue164 (comparison Issue128 is complete); no additional
comparison experiment or engine offering is authorized. Qualification, release
version and publication remain separate and unapproved.

## Prepared output — product acceptance checkpoint (2026-11-14)

Independent source/regeneration43450619130, normal43460340200, public integration
43460417407 and installed distributions43465753261 passed on their exact recorded
candidates. The [checkpoint](decisions/prepared-output-reuse.md) retains
identities and scope. The single bootstrap remains UNQUALIFIED historical evidence;
later independent reproduction is separate evidence, not a relabeling.

A same-condition prepared comparison found a64KiB regression. Host-only JSON
presence decoding removed a redundant whole-message parse without changing the
guest or weakening row validation. Fixed candidate
`ef4d5cd97f718ebaaa5b2fa0d7999e3e6b169b9e` has repeat measurements,71 unchanged
native-reference scenarios and five frame cases. Median query ratios versus fixed
main: one row0.987,1,000 rows0.827,64KiB0.998. Variance and single-Mac limits remain;
no universal speedup, peak-RSS benefit or measured upgrade-hour reduction is claimed.
The [measurements](../benchmarks/prepared-output-20261114/README.md)
retain the original regression, follow-up and failed measurement setup.

Same-source normal43530112119, public43530115529 and installed43530119031 are
all PASS on that exact host SHA. The [integration review](decisions/prepared-output-reuse.md)
recommends bounded output adoption with its explicit prior-condition disposition.
This remains Codex's recommendation: main integration, Issue132's final selected-route
disposition and release are Human decisions. Owned measurement scratch/cache/source
copies were removed; committed reports and reproducible source refs remain.
Issue134 is closed as formalization/handoff complete. Issue65 and Issue132 remain
open for the integration and selected-route disposition; closure of134 is not
a contract waiver or adoption approval.

## Output-only productization authorized (2026-11-13)

The Human approved proceeding with the output-only candidate after the LTS
maintenance comparison. This authorizes formalization and acceptance; main
integration and release remain separate decisions. Retain embedded, existing
input/session and host state. Additional engine hooks, per-series conversion
implementations or weakened contracts return to the value decision.

The product branch starts from main eb175ae23292c1c40cfbeb4b9b73132873c4cc6f,
preserving recent performance changes, and ports the bounded source/test delta
from73d1dca153348feab07a7638172782056af7897d. First build a fresh UNQUALIFIED
guest using the existing producer. Review its translation and worker/CRC binding
before updating canonical pins. Then independently regenerate and execute the
same-candidate #132 acceptance. The intermediate host v2 with canonical guest v1
is deliberately not a usable release. Old trial artifacts/bindings are not current
inputs. The earlier recommendation-wait text is historical after this approval.


## MariaDB support direction — provision for two recent LTS series (2026-11-12)

The Human clarified the direction: only12.3 LTS is required now; eventually
provide roughly the two most recent LTS series so a new LTS does not force users
to migrate immediately. This supersedes the earlier latest-LTS-only premise.
It does not request adding11.4/11.8 now or product support for rolling/Preview
releases. Users will select a series-specific distribution whose version makes
its MariaDB series visible (Human examples: `0.7.1-12` and `0.7.1-13`). These are
illustrative names, not approved release versions or final tag/package syntax;
Go/Python version rules and resolution ordering must be checked in distribution
design. Exact engine versions remain identified in inputs/provenance.

Maintain each offered series for its upstream MariaDB LTS maintenance period.
A new offering alone does not end maintenance of an older one. Roughly two
series is a planning expectation, not a hard cap overriding overlapping LTS
periods. This does not request retroactive offerings of every old LTS. Record the
official maintenance category and dates when setting concrete end dates; no
Community/commercial-extension category or exact date is chosen here.
Simultaneous engines in one process are not a requirement.

Evaluate both the cost of adding a new LTS and the incremental cost of maintaining
old/new offerings: version-specific adapter/patch differences, applying shared
fixes, per-series generation/binding, CI and distribution. Distinguish shared
work from version-specific work rather than doubling every cost. Historical
parallel preparation can support this direction, but is not product acceptance.

The prepared-output candidate remains unadopted. Its LTS source comparison and
limits are recorded in [Issue128 evidence](reviews/issue128-lts-output-history/README.md).
The observed stable raw-row boundary is relevant to limiting version branches,
but does not prove two-series runtime acceptance. No runtime or release inputs
change with this clarification.

## Issue156 — dictionary-wait main integration approved

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
correction with the measured P4 regression retained. The Human approved main
integration and then related-Issue cleanup on 2026-11-13. The [approval record](reviews/dictionary-installation/integration-approval.json)
binds the reviewed source and accepted limits. Protected PR checks own the merge
transaction. Close #156 on merge for the completed finite work; #140 retains the
unproven natural PREPARE sequence. No new experiment or release is authorized.
The bootstrap remains UNQUALIFIED; no historical result is relabeled.

## WASI timer correction and startup reduction — adopted on main

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
On 2026-11-11 the Human approved main integration, accepting the measured
Fresh/Fork startup benefit and the absence of an established whole-suite benefit.
[PR152](https://github.com/masahitojp/mariamem/pull/152) merged approved head
`ba9bf77bcaf6e49a6b3a6ed4df54ed8837856b18` as main source_commit
`500020e7dc6d702ef059f0e73a4bab738103b774`. All three protected checks passed
at that head in [CI43008225827](https://github.com/masahitojp/mariamem/actions/runs/43008225827).
The [candidate measurement](../benchmarks/timer-product/README.md) remains bound
to its original measured source: Fresh/Fork median -8.63%/-8.96%, complete-suite
P4 +2.23% and P8 -20.47% on one Mac. This authorizes bounded startup/timing
correctness adoption, not a uniform end-to-end speedup claim. Main integration
is complete; Qualification and release remain separate. The Human also authorized
starting the separate UCA investigation, without adopting a new UCA change.

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

## Issue123 — process-lifetime static cache adopted; post-merge Close failure observed

On 2026-11-10 the Human authorized main integration and an immediate speed
comparison. [PR147](https://github.com/masahitojp/mariamem/pull/147) squash-merged
to `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`, with the same tree as approved
head `08a2246a50bf5ce63de97ddf2b118b8df09dca1f`; required Development checks
[42727872452](https://github.com/masahitojp/mariamem/actions/runs/42727872452)
passed there. This supersedes the integration-pending checkpoint below for this
bounded implementation, not release approval.

The [post-merge comparison](reviews/issue123-postmerge-measurement.md) against
immediately preceding main `c375edbc` completed the fixed56 processes on Mac:
39/40 primary runs succeeded and one after/Fork/P4 run timed out in Close with
one child mapping uncollected before process exit. All child SQL oracles in that
failed run passed. No consistent whole-suite speedup was established; serial
peak RSS decreased in all five pairs for Fresh and Fork. Successful Fork/P4
speed statistics use four complete pairs, explicitly separate from the failure.
The failure is not discarded or retried; its cause and relationship to this
change remain unknown. Recommendation: investigate Close before further speed
or release claims. No follow-up runtime change, rollback, extra sampling or
release is authorized by this measurement record.

The Human subsequently authorized a bounded Close diagnosis. The
[diagnosis](reviews/issue123-close-wait-diagnosis.md) at harness `9edc93e5`
completed10 alternating pairs on the same Mac:480 children per source, all SQL
and cleanup checks passed, no Close exceeded2 seconds (max14.976/16.453ms).
Result: **INCONCLUSIVE_NO_REPRODUCTION**, not a fix or withdrawal of the earlier
failure. A delayed stack/log observer passed separate forced controls. The
original error chain narrows the direct timeout to worker drain or subsequent
guest shutdown, but no slow stack identifies the blocking operation. Stop at the
fixed budget; retain the observer for the next authorized workload instead of
adding unbounded repetitions. Product/runtime/API bytes are unchanged.

The remaining Close question is tracked in [Issue162](https://github.com/masahitojp/mariamem/issues/162).
The following paragraphs preserve the pre-integration checkpoint; they are not
new implementation instructions.

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


## UCA default private-copy — adopted on main, unreleased

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
bytes are unchanged. Development CI43201340611 passed all three required checks
at a8dd2f1c. [PR157](https://github.com/masahitojp/mariamem/pull/157) was squash
merged as `8df45792a927e440972266ee799d6f7223713e14` with strict-base and
admin protection retained. [Completion record](reviews/uca-copy-main-adoption.md).
#156 completed its bounded pending-clear correction in the later output
integration; [#140](https://github.com/masahitojp/mariamem/issues/140) retains the
unproven natural PREPARE sequence. NOT_REPRODUCED is not a fix. No release is
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

## Historical benchmark reports retained (2026-11-14)

The PR backlog reconciliation retains the [v0.5.3/v0.6.0 latency comparison](../benchmarks/v060-latency.md),
[parallel model case](../benchmarks/parallel-modelcase.md) and
[shared-read follow-up](../benchmarks/shared-read-modelcase.md) as historical
observations with their exact source identities, compact samples and pinned raw
archives. They do not measure current main or establish a current regression fix.

The [former v0.6.1 disposition proposal](reviews/v061-latency-disposition.md)
remains historical: v0.6.1 and v0.6.2 have already shipped. Its proposed attribution
campaign is not an active task or a retroactive release condition. Retaining this
record neither accepts the measured regressions nor proves that later changes
fixed them. Reopening the question requires a current workload and decision.

PR54's broader benchmark-retention policy is not adopted by this reconciliation.
Its [original proposal](https://github.com/masahitojp/mariamem/blob/bb6d0efa9759629646f4d8d834221aa823bb6002/docs/development.md#benchmark-evidence-retained-on-main)
remains available for a separate future decision; current
[compact-receipt rules](development.md#compact-ci-receipts) continue to apply.
No new experiment, performance acceptance or release follows from this cleanup.
