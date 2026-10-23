# Connection switching — native CI results and Human Review

2026-10-24. Reviewed prototype source_commit:
`dd3b44d46012093fa7dfa05f0ed8f5b8729740a2` on
`experiment/connection-routing`. Evidence/review branch:
`experiment/connection-routing-review`. The inputs and decision are reconstructed
from the approved [design](v06x-connection-routing-design.md), its
[local checkpoint](v06x-connection-routing-spike.md), and the Human's CI completion
report. The local checkpoint remains a historical record, including its SKIP.

## Human Review — decision requested

**The native campaign passed on both OSes, but the full approved spike is not
yet closed.** Review found two missing explicit oracles: old session/statement
state after pool retargeting (R2), and a physical connection with unknown
ownership (R3). CI counts 13 implemented cases, not every clause of the design.
This checkpoint supports selecting a productization direction, not adopting the
prototype unchanged.

**Recommendation: proceed to productization design for scoped Python routing
with an explicit SQLAlchemy adapter, alongside configuration injection and
child-owned Go pools.** Carry the two original-scope checks into that step and
close them before recommending production implementation; they are not waived.
The decisive evidence is actual SQL reaching independent children on both OSes,
while deliberate removal of the protections reproduces wrong-child execution
and contact with the controlled original endpoint. Supported applications could
therefore keep their existing connection/query code and bind a test child in
their fixture.

The strongest objection is that a cached factory or an already-running pool
can bypass the intended boundary: a misleadingly successful test could still
use an unintended DB. The current evidence does not support universal interception.
An explicit adapter/injection path remains necessary for those cases. The design
must specify enrollment before application activity, accepted factory forms,
and ownership through teardown; if it cannot make an advertised path enforceable,
that path needs explicit integration and a Human scope decision, not an implied
support claim. This is why the recommendation is design, not implementation or
main adoption. API names, broader framework coverage, integration and release
remain undecided.

## 1. Fixed inputs and independently checked receipts

[Run40026373681](https://github.com/masahitojp/mariamem/actions/runs/40026373681)
is SUCCESS at the exact prototype commit above. Both native jobs passed:
[macOS](https://github.com/masahitojp/mariamem/actions/runs/40026373681/job/120663485113)
and [Ubuntu](https://github.com/masahitojp/mariamem/actions/runs/40026373681/job/120663484583).
The retained [summary](v06x-connection-routing-evidence/ci-40026373681/summary.json)
records job/artifact IDs and API-reported archive digests.

- Runtime source_commit: `dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776`.
  `scripts/git_identity.py inspect` confirms both source identifiers are commits.
  The runtime baseline differs from adopted main
  `9f29194bbddd6a9431a4a250bd2f93ee813734af` only in two design/status documents.
  Both host buildinfo receipts name this runtime commit and `vcs.modified=false`.
- Go1.26.10; guest SHA256
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
  Host SHA256: macOS
  `be35ea19d2757378f6f67774ee768a13c170ae24a4d961b4571229b181f5e7c6`;
  Ubuntu `3be532ba4a44f87a53ee959cc06f72adf0e440f0e57965bd45d4b3fc33972315`.
- PyMySQL1.2.3, SQLAlchemy2.0.54, Connector/Python26.7.0,
  go-sql-driver/mysql1.9.3. Each platform's
  [Mac inputs](v06x-connection-routing-evidence/ci-40026373681/macos-15/inputs.json) /
  [Ubuntu inputs](v06x-connection-routing-evidence/ci-40026373681/ubuntu-24.04/inputs.json)
  includes installed package file hashes, compiler metadata and consumer hashes.
  All15 evidence-file hashes per platform matched the downloaded originals;
  all5 prototype-file hashes matched `git show dd3b44d:<path>`.

The recorded host hashes are build receipts; binaries were not uploaded or
independently rebuilt for this review. This is no new generation/Qualification
claim. No guest, converter or production runtime change was needed.

## 2. Results against the approved R1–R8 scope

Source of observations:
[Mac control](v06x-connection-routing-evidence/ci-40026373681/macos-15/control.json),
[Ubuntu control](v06x-connection-routing-evidence/ci-40026373681/ubuntu-24.04/control.json),
and [campaign.py](../../tests/spikes/connection_routing/campaign.py) at the reviewed SHA.

| Requirement | macOS arm64 | Ubuntu x86_64 | What the evidence actually establishes |
| --- | --- | --- | --- |
| R1 direct/saved/deferred/reconnect | PASS | PASS | Five PyMySQL observations all reach A, including an object created before hook installation |
| R2 cold/warm pool | PASS destination; SKIP explicit old-state assertion | Same | A/B/A markers and two generation invalidations in the held-idle case. No deliberate old session variable/statement is seeded and checked for absence |
| R3 active/custom/unknown ownership | PASS executed refusals; SKIP unknown physical-owner case | Same | Active checkout/transaction re-enrollment, custom creator and unknown **profile** reject. Unknown profile is not a test of an untagged physical connection |
| R4 concurrency and context | PASS, 3 cases | PASS, 3 cases | Two threads query/write their own children; nested binding restores A; propagated thread works, unpropagated thread rejects; asyncio tasks select A/B using synchronous DBAPI |
| R5 lifetime and failures | PASS, 3 cases | PASS, 3 cases | Retired copied context and missing/closed targets reject; original setup/test exceptions survive; cleanup failure is attached; outer binding restores |
| R6 options/schema | PASS executed cases | PASS executed cases | PyMySQL socket, option-file and explicit TLS conflicts reject; schema `app`, qualified SQL, charset/autocommit and rollback preserved; Connector module-entry option file rejects |
| R7 prepared consumers | PASS default/pure/C and Go | PASS default/pure and Go; explicit C SKIP | Actual bound marker, prepared execution, commit/rollback; Go non-interpolated execution and separate pools for A/B |
| R8 preparation and two tests | PASS | PASS | One schema/seed, disconnected source Snapshot, two children per injection/routing path, independent committed writes and completed teardown |

Both control JSONs have13 PASS cases, zero original-sentinel attempts and all
hosts reaped. The runner's `complete=true` accurately describes those executable
cases; it does **not** close the two design-coverage gaps above. No new behavior
failure was observed in the unmutated runs. The R2/R3 SKIPs mean missing targeted
checks, not reproduced failures or unavailable operating systems.

R2 deliberately disables normal scope cleanup to keep an old idle connection
available for the checkout oracle. Code inspection of
[router.py:164–175](../../tests/spikes/connection_routing/router.py) supports the
inference that invalidation replaces the physical connection and thus its
session state. That inference is useful but is not the missing explicit oracle.
R3's active test uses an already-enrolled engine; it does not independently
exercise first enrollment of a previously active/untagged engine.

The control recorded27/26 physical connections (Mac/Ubuntu) and3 pool
invalidations each. These are whole-campaign diagnostics, include different
numbers of Connector modes, and cannot be compared as efficiency measurements.
There was no performance benchmark or quantified first-test productivity claim.

## 3. Connector modes and limits retained

| Environment | Default/prepared | Explicit pure | Explicit C |
| --- | --- | --- | --- |
| macOS15.7.9 arm64, Python3.14.7, OpenSSL3.5.7 | PASS, `CMySQLConnection` | PASS | PASS |
| Ubuntu24.04 x86_64, Python3.14.8, OpenSSL3.0.13 | PASS, `MySQLConnection` | PASS | SKIP: extension needs `OPENSSL_3.2.0` |
| Earlier local Homebrew Python3.14.8/OpenSSL4.0.3 | SKIP at package import | SKIP | SKIP |

The Ubuntu driver itself selects pure mode when its extension cannot load; the
test did not force `use_pure` for the default case. Its environment receipt's
`direct_import=FAIL` refers to `_mysql_connector`, not to the Python package,
which ran successfully. The separate explicit-pure case is labeled as such.
See [Mac environment](v06x-connection-routing-evidence/ci-40026373681/macos-15/connector-environment.json)
and [Ubuntu environment](v06x-connection-routing-evidence/ci-40026373681/ubuntu-24.04/connector-environment.json).
These results resolve the earlier required default-path SKIP for CI's supported
environment; they do not repair or relabel the Homebrew import failure.

The [accepted Prepared exceptions](../decisions/prepared-consumer-exceptions.md)
are unchanged. This campaign composes routing with simple prepared
SELECT/write/commit/rollback; it does not rerun or overturn the P6 CALL/NUL
exceptions. Explicit Ubuntu C remains an environment SKIP under the design's
mode policy, not evidence of C-mode routing behavior there.

## 4. Failure oracles and user consequences

All four mutations were detected on **both** platforms, at the intended case,
with exit1, no fatal setup error, and all hosts reaped. Per-platform JSON and
text logs are adjacent to the control evidence.

| Deliberately removed protection | Observed consequence | Detection |
| --- | --- | --- |
| Pool-generation check | A/B/A requests read A/A/A; the second test uses the previous child's DB | R2 marker assertion fails |
| Missing-target rejection | One attempt reaches the controlled original endpoint | R5 sentinel and connection failure |
| Scope retirement check | A copied expired context opens another connection | R5 required rejection absent |
| Context-local target | A worker reads B/B/B instead of A/A/A | R4 marker assertion fails |

These are defects deliberately introduced into this prototype. They are not
observations of faults in released mariamem. The original endpoint was a local
listener, never a real application database.

## 5. Remaining conditions and detection net

| Condition | Judgment and next bounded action | Current detection |
| --- | --- | --- |
| R2 old session/statement state | Unfinished: seed observable session state in the held-idle test, record physical replacement, and assert no carryover on A/B/A; keep the existing wrong-target mutation | Current marker detects wrong DB, not independent session-state assertions |
| R3 unknown physical ownership / first active enrollment | Unfinished: seed a real untagged connection in the supported pool using only a local test DB; check active enrollment refusal, then idle discard/recreation before a query is admitted. Distinguish this from unknown-profile refusal | Current R3 does not create this state; no CI detector for that missing case |
| Saved Connector factory with advanced options | Not established: saved ordinary factory works, but option files, DNS/failover and built-in pooling may execute before the patched abstract connect method. Product design must select an enforceable entry/explicit adapter; this is not a supported advanced-alias claim | R6 tests the replaced module entry only; saved advanced-factory bypass is outside its oracle |
| Enrollment and teardown ownership | Prototype assumes quiescent enrollment; a checkout count is not an admission barrier. Application work is joined by the campaign, not by automatic task discovery. Specify fixture/admission ownership and preserve original errors before implementation | Cooperative R4/R5 cases cover their stated paths, not concurrent enrollment or arbitrary leaked handles |
| Maintained dependency hooks and diagnostics | Pin/guard supported hooks and define actionable context fields. Current errors have stage/reason/action; they do not yet carry all proposed profile/child/generation/mode fields | Version pins exist; no public adapter/version gate or complete diagnostic-schema test yet |
| Runtime identity, independent children, required default Prepared paths, mutation controls and both OSes | Satisfied for the executed campaign | Hash receipts, R1/R4/R7/R8 and all four deliberately failing controls |

The two original-scope oracle additions are finite prototype work, not a new
survey of arbitrary frameworks. Reuse the same guest, baseline, drivers, two
children and sentinel; retain all existing cases/mutations. They can accompany
the productization design, but their results must be reported before marking the
approved spike complete or recommending production implementation. An unexpected
protocol/runtime requirement would stop for a separate decision.

Broader Django/mysqlclient/async-driver coverage, multi-profile selection,
GORM integration UX and actual migration/dump preparation remain companion
decisions from the original design. R8's hand-authored schema callback is not
proof of those workflows. Their scope is neither removed nor implicitly approved
by this recommendation.

## 6. Cross-checks, preservation and review limits

No new contradiction was found in current public usage guides: they describe
explicit configuration, not a shipped routing helper. No guest/generated-owner,
license, provenance, release-ledger or accepted-exception change was found in
the prototype diff. Snapshot's consuming lifecycle and child independence are
unchanged. No independent regeneration, main adoption, Qualification or release
is required or claimed for these review/evidence-only edits.

Cross-check basis: the approved design's sections4–6; the local checkpoint's
limits; [workflow alternatives](v06x-workflow-design-options.md),
[capability map](v06x-capability-map.md),
[Snapshot contract](../decisions/snapshot-product-contract.md),
[Prepared exceptions](../decisions/prepared-consumer-exceptions.md), and
[current project status](../project-status.md). The review inspected the pinned
helper, campaign, runner, Go consumer and workflow plus both artifact bundles.
It did not rerun the unchanged runtime, repeat the earlier driver survey or
claim an all-framework safety result.

Reproduction uses the [existing two-checkout procedure](v06x-connection-routing-spike.md#reproduction-and-evidence-retention)
with prototype commit `dd3b44d46012093fa7dfa05f0ed8f5b8729740a2`. Saved
[Mac files.json](v06x-connection-routing-evidence/ci-40026373681/macos-15/files.json)
and [Ubuntu files.json](v06x-connection-routing-evidence/ci-40026373681/ubuntu-24.04/files.json)
bind original and stored hashes. Only known runner paths are replaced and `.log`
files renamed `.txt`; outcomes are unchanged. Hashes in `inputs.evidence` refer
to downloaded originals, not the scrubbed copies. Artifact archive digests are
API metadata, not a claim that the extracted directory recreates the ZIP hash.

The review records are pushed separately to avoid rerunning an unchanged spike
for documentation. The tested prototype SHA and CI evidence stay fixed. This
document is a recommendation awaiting Human decision, not Human approval.

Documentation/evidence verification:152 local file-link targets exist; both
saved evidence inventories and original-to-stored hash lineage match;
`check_public.py` and `check_version.py` PASS. No runtime test was repeated for
these documentation-only changes. The reviewed prototype/runtime and accepted
consumer-exception document remain unchanged.
