# G1 resource/time campaign and CI checkout correction

The campaign is implemented and locally observed, but the required macOS15 arm64
and Ubuntu24.04 x86_64 receipts are pending the new CI submission. This is not
G1-complete, main adoption, Qualification or release approval. The helper/runtime
API and guest/generated sources are unchanged by this follow-up.

## Failed CI diagnosis

[Development40715670588 / integration122913088794](https://github.com/masahitojp/mariamem/actions/runs/40715670588/job/122913088794)
failed during checkout, before tests. The log fetched PR merge5c6959e4ba66e6e9a23f00c7f72db0ce6012d7bb
for original PR head a0da082595f95f479e83356ec1124ab846a7a6d7. It records RPC receive
timeout/early EOF, then TCP443 connection failure and github.com DNS failure.
The bounded follow-up status read found every other check on that submission
successful. Those successes are not new G1 resource receipts.

Full history checkout fetched all branch/tag payloads. The Development and Live
full-history checkouts now use the supported partial-clone filter blob:none,
retaining commit ancestry and required current/pinned bytes while avoiding
unneeded historical blob downloads. See the [checkout input](https://github.com/actions/checkout#usage).
This mitigates transfer cost; it neither proves transfer size caused the DNS
failure nor guarantees recovery from a runner/network outage. The new CI must
confirm checkout and subsequent tests. No error suppression or source override
was added.

## Executed campaign and evidence gate

[scripts/go_fixture_campaign.py](../../scripts/go_fixture_campaign.py) inspects
an exact clean commit before building, hashes production library bytes plus the
campaign/SQL/guide inputs, pins Go1.26.10, and keeps original receipts with
SHA256SUMS.json. It runs the actual guide first test, records the additive second
file, builds one integration test binary with -p 1, then runs cap1/2 crossed with
-test.parallel=1/4 in one test-package process. Each mode has one warmup and
three observed four-case batches. The production dependencies are wrapped only
for test observations; DB(t), pool ownership and actual driver execution remain
real. The callback imports the pinned64-table SQL, and each child verifies all
seed rows, prepared parameters and original schema before committed mutation.

Each mode retains1/2/3 independent prepared baselines. Steady observation windows
align OS RSS/available-memory samples with the exact retained count. FD counts,
physical pool connections (database/sql Stats.OpenConnections), starting/live
child owners, baseline owners and temp bytes stay separate. These connection
counts cover helper-owned driver connections, not arbitrary external pools.

RSS is a sampled process-tree ps sum, not Go heap or physical footprint. Linux
uses MemAvailable; macOS explicitly reports a free+inactive+speculative-page
estimate. FD peaks are sampled checkpoints, not a proof that no shorter peak
existed. Temp accounting includes allocated named files plus open-unlinked regular
file blocks deduplicated by inode; memory-resident files remain RSS, not disk.
The final owner/connection/temp counts must be zero. Total process FD growth has
an explicit allowance of8 for Go lazy process-global descriptors; it is not an
arbitrary-FD leak proof. Raw baseline/peak/final values remain visible.

The accepted guards remain2GiB incremental RSS,8GiB allocated owned temp,
16GiB minimum free disk and64 FD headroom. A violation stops further admission
and preserves STOP/cleanup evidence; unknown counters do not become zero/PASS.
An intentionally impossible FD-headroom negative control must STOP before source
startup, with no children/baselines/connections and confirmed empty cleanup.
This is stronger negative input, never a relaxed positive budget.

The first-test/second-test commands, authored lines and phase wall times are
separate from repeated batch wall time and per-case admission/SQL/owned cleanup.
Parallel phase durations are not summed. Toolchain acquisition is unmeasured;
existing caches are declared, not called cold. No human authoring minutes are
invented. One-line SQL loading is solely for the fixed authored diagnostic;
the first failed attempt at779a482 mishandled a semicolon in its comment and
failed preparation with1064. That failed receipt is preserved, not relabelled.

Live CI uses its existing both-host jobs/cache instead of a second host matrix.
Each host must run/validate the campaign and upload go-fixture-host-OS-SHA.
The existing Live required gate downloads both artifacts and independently
checks source/architecture/OS version, all four modes, the64 cases and timings,
aligned retention counters, actual guard STOP and checksums. Missing host,
mode, measurement or receipt fails the gate. Guide-only workflow skip policy
and branch protection contexts are unchanged.

## Local observations and remaining conditions

Local source_commit `232fc19ae2c6ff4ce478735748e699846a0e5a44`, macOS27.2 arm64,
Go1.26.10: all four modes and the pre-admission FD STOP control passed.
[Raw receipts and checksums](v06x-go-fixture-campaign-evidence/local-232fc19/host.json)
are preserved under their original source. These are not macOS15 CI evidence.

| Cap | -parallel | Peak child owners | Peak physical pool connections | FD baseline / sampled peak / final | Sampled RSS peak MiB |
| --- | --- | --- | --- | --- | --- |
| 1 | 1 | 1 | 2 | 4 / 13 / 4 | 161.2 |
| 1 | 4 | 1 | 2 | 4 / 13 / 4 | 165.6 |
| 2 | 1 | 1 | 2 | 4 / 13 / 4 | 166.9 |
| 2 | 4 | 2 | 4 | 4 / 22 / 4 | 252.0 |

Each retention1/2/3 has an aligned RSS/available-memory observation and separate
FD/connection/temp counters in the raw report. Every final children/baselines/
connections/linked+unlinked temp count is zero. The FD guard control stopped
before source startup and confirmed empty cleanup. RSS numbers above are
absolute sampled process-tree RSS, not incremental RSS or physical footprint.

The first authored sample has36 lines and ran in5.366s with existing caches;
the second adds13 lines, repeats no lifecycle wiring and runs both tests in2.875s.
Per-mode batch and setup/admission/SQL/cleanup timings are in the receipts.
These elapsed observations are neither controlled latency comparisons nor human
authoring time. The [first failed receipt](v06x-go-fixture-campaign-evidence/local-779a482/host.json)
retains original source779a482, FAIL/1064 and confirmed cleanup. It is not
relabelled as the successful source.

Focused policy/receipt tests:206 PASS. The unchanged helper unit/race gate also
passed; it started at2414043, whose Go production/component-test bytes match
232fc19. Its separate compilation ran concurrently on this local machine.
The available-memory observations therefore include shared-host activity, and
timings are not exclusive-host comparisons. The actual resource campaign is not
a full-guest race qualification.


These finite observations can support retaining the proposed static defaults
for this diagnostic input; they cannot establish safe concurrency for arbitrary
legacy apps, justify raising the16-session runtime cap or establish universal
setup-cost/performance superiority. Complete G1 acceptance still needs the new
both-host CI receipts plus the separately tracked actual cleanup/backing fault
and installed-consumer controls. Difficult Django-specific work remains
nonblocking for v0.6.0. No support/defer decision is silently expanded here.

## Ubuntu CI collector exit race — run40724194463

[Job122944776649](https://github.com/masahitojp/mariamem/actions/runs/40724194463/job/122944776649)
completed canonical integration, then stopped in the G1 validator with RSS absent.
The original artifact12834155230 is preserved as exact ZIP bytes/base64 with its
GitHub SHA256 digest and [assessment](v06x-go-fixture-campaign-evidence/ci-40724194463-ubuntu/assessment.json).
Its source_commit is db86a2c8be656df3022456c2ac0a2a855a42f31b (the executed PR merge),
while PR head was a9cc82b. Neither is substituted for the fixed candidate.

The first mode's Go result/cleanup were PASS/true and process exit was0. Of46 OS
samples, the last alone reported RSS0, approximately8ms after the Go final cleanup
record. The collector checked liveness before calling ps but did not check again
before admitting that result as a live measurement. This evidence matches an exit
race; the old receipt did not capture process state, so it does not prove a
specific kernel zombie state.

The fix polls exit status after counter collection. Only an exit-confirmed
observation goes to terminal_observations (raw members/RSS and exit code retained).
A process disappearing during collection also retains the terminal error. Live
RSS0 still fails closed, runtime nonzero exit still fails, and live-sample count,
retention alignment, memory/FD budgets and checksum requirements are unchanged.
Deterministic tests cover zero/positive terminal RSS, a disappearing process,
nonzero exit and live zero; the failed CI receipt stays FAIL. A fresh source-bound
both-host run is still required. The separate macOS dump job122944044147 was
cancelled with no executed steps in the bounded metadata read; no code failure
could be diagnosed from its unavailable log. It is not treated as a PASS.


Fix verification: focused tooling/receipt/workflow tests214 PASS. The full local
four-mode campaign and pre-admission FD STOP passed at source_commit
549be266b4342e1a45a657f48a2d4c3c079c5606 on macOS27.2 arm64/Go1.26.10.
[Local assessment/archive checksum](v06x-go-fixture-campaign-evidence/local-549be26/assessment.json)
binds the raw zipped receipts (including their original SHA256SUMS). This is local
verification of the corrected collector, not a replacement Ubuntu/macOS15 receipt.
Fresh both-host CI remains pending. The production helper/guest/generated code
was unchanged; no broad runtime rebuild was needed for this Python-only fix.

## Both-host resource/time receipt confirmed — run40730646806 attempt2

[Live CI40730646806](https://github.com/masahitojp/mariamem/actions/runs/40730646806)
and required gate123000356113 succeeded. Executed source_commit
b59452738265b2237875e026d5c6063d01a1c8b8 was verified as a commit object and has
exactly the same tree a7af7dfec191bec5badbed7abb259c745f9be45e as PR head
e8c0380852c273af5b4e5e18dde4ef22dd265904. The receipts keep the executed merge
SHA rather than being relabelled as the PR head or a later documentation commit.

| Host | Actual execution | Artifact | Four cap/parallel modes | Retention1/2/3 and three-time outcomes | FD STOP/cleanup |
| --- | --- | --- | --- | --- | --- |
| macOS15.7.9 arm64 | attempt2, job122991219282 |12837603561| PASS | PASS | expected STOP / complete |
| Ubuntu24.04 x86_64 | attempt1, job122967361491 reused |12836002279| PASS | PASS | expected STOP / complete |

The cancelled Mac attempt1 remains cancelled; Ubuntu's successful attempt1 is
not renamed attempt2. Latest-attempt API metadata also lists the reused Ubuntu
job as122991220769; the host receipt's own execution attempt remains1.
Both official ZIP digests, internal file sums, actual source/input hashes, host
architecture/version, all mode/case/retention/time counters and guards were
checked locally with the same matrix validator: G1_BOTH_HOST_CAMPAIGN_PASS.
Raw ZIP bytes/base64, run/jobs metadata, digests and measurements are saved in the
[assessment](v06x-go-fixture-campaign-evidence/ci-40730646806/assessment.json).

The accepted static default2/pool budgets stayed within the finite guards for
this fixed diagnostic on both hosts. Mac FD baseline/peak/final was4/13/4 for
single-child modes and4/22/4 for cap2/parallel4; Ubuntu was6/15/6 and6/24/6.
Active child peaks1/2 and physical pool connection peaks2/4 remain separate.
These observations close the previously missing **time/resource campaign**
evidence, not arbitrary-app scalability, the16-session-cap question or full G1.
Actual backing/disposal fault controls and an installed Go consumer using
mariamemtest remain required. The existing Live installed-consumer step is not
relabelled as helper-consumer acceptance. Main adoption and release remain
separate decisions. Earlier pending/failure paragraphs retain historical context.
