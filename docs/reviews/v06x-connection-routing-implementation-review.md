# Connection switching — spike complete, implementation Human Review

2026-10-24. Reviewed source_commit:
`2851246e8cd5fda89777558f4f3f3dfc4b004f7c` on
`experiment/connection-routing-contract`; base/review checkpoint:
`804ff502e487a89fa690126ab4de375ff7d818ef`. Both are commit identities checked
with `scripts/git_identity.py`. Review inputs are reconstructed from the Human's
instruction to proceed with the [productization design and closure](v06x-connection-routing-product-design.md)
and subsequent CI completion report. Earlier reports retain their original
pending statements. This report and current project status own the later result.

## Human Review — one decision requested

**Approve production implementation of the proposed routing boundary.**
Recommendation: proceed with optional Python routing, the explicitly enrolled
SQLAlchemy adapter and early pytest integration described in
[design sections2–6](v06x-connection-routing-product-design.md#2-proposed-user-entry-and-public-surface),
alongside explicit configuration injection and child-owned Go pools. The bounded
spike is **COMPLETE**: both OSes passed all15 cases and detected all six deliberate
defects, including the two formerly missing session/ownership checks. This
supports keeping ordinary application SQL/connection code while fixtures supply
independent test databases; it does not yet make the proposed API available.

The strongest objection is that an already-running connection or a cached
advanced factory can bypass a later fixture. The proposed support boundary
requires installation before application activity, explicit engine ownership
handoff, and an adapter/injection path for unsupported entries. Saved advanced
Connector factories are not included in the initial support claim. This makes
the initial implementation useful for the tested application construction paths
without presenting arbitrary live applications as automatically redirected.
Early-import enforcement and production cleanup remain implementation acceptance
work, not results already proven by the prototype. Main adoption, version
placement, Qualification and release remain separate decisions.

## 1. Native evidence and identity

[CI40032530547](https://github.com/masahitojp/mariamem/actions/runs/40032530547)
finished SUCCESS at the exact reviewed SHA. Both native jobs, including receipt
gate tests and real-guest execution, passed:
[macOS15 arm64 job120684027833](https://github.com/masahitojp/mariamem/actions/runs/40032530547/job/120684027833),
[Ubuntu24.04 x86_64 job120684028046](https://github.com/masahitojp/mariamem/actions/runs/40032530547/job/120684028046).
The saved [summary](v06x-connection-routing-evidence/ci-40032530547/summary.json)
records job/artifact IDs, API-reported archive digests and mode outcomes.

Runtime source_commit remains `dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776`;
Go1.26.10; guest SHA256
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
Host buildinfo names that runtime commit and `vcs.modified=false` on both OSes.
The host hashes are identical to the previous campaign on each platform:
Mac `be35ea19d2757378f6f67774ee768a13c170ae24a4d961b4571229b181f5e7c6`;
Ubuntu `3be532ba4a44f87a53ee959cc06f72adf0e440f0e57965bd45d4b3fc33972315`.
These are recorded build identities, not independent regeneration receipts.

PyMySQL1.2.3, SQLAlchemy2.0.54, Connector/Python26.7.0 and Go driver1.9.3
remain fixed. The [Mac inputs](v06x-connection-routing-evidence/ci-40032530547/macos-15/inputs.json)
and [Ubuntu inputs](v06x-connection-routing-evidence/ci-40032530547/ubuntu-24.04/inputs.json)
record package file hashes, prototype hashes and actual environments. All19
evidence-file hashes per platform matched the downloaded originals; all5
prototype-file hashes matched `git show 2851246:<path>`. The prototype-source
receipt equals the full reviewed SHA. Re-evaluating the saved JSON using that
unchanged runner accepted the exact control and six expected mutation outcomes.

## 2. Scope closure

Source:
[Mac control](v06x-connection-routing-evidence/ci-40032530547/macos-15/control.json),
[Ubuntu control](v06x-connection-routing-evidence/ci-40032530547/ubuntu-24.04/control.json),
and [campaign.py](../../tests/spikes/connection_routing/campaign.py) at the reviewed SHA.

| Approved requirement | Both-OS outcome | Observed boundary |
| --- | --- | --- |
| R1 driver direct/alias/deferred/reconnect | PASS | All five observations query child A |
| R2 cold/warm generation and old session state | PASS, 2 cases | Original A/B/A destination check plus A/A/B/A distinct physical sessions; old variable, temporary table and prepared statement absent at every new generation |
| R3 active/custom/unknown ownership | PASS, 2 cases | Existing refusals retained; first enrollment of a real untagged active connection rejects without closing it or ending its transaction; after return, idle connection closes and an owned replacement queries B |
| R4 concurrent/nested/thread/asyncio scope | PASS, 3 cases | Markers/writes isolated; explicit thread propagation and missing-context rejection; asyncio uses synchronous DBAPI |
| R5 lifetime and failure cleanup | PASS, 3 cases | Expired/missing/closed target refuses; original setup/test exception retained, cleanup failure attached, outer context restored |
| R6 options and logical schema | PASS for executed options | Socket/option-file/TLS conflicts reject on their tested entries; named/qualified schema, charset, autocommit and rollback preserved |
| R7 required prepared consumers | PASS, 2 cases | Connector default/pure on both OSes, Mac explicit C, Go separate pools with explicit Prepare and non-interpolated execution; Ubuntu explicit C remains SKIP |
| R8 preparation and two independent tests | PASS | Injection and routing both reuse one prepared baseline with independent child commits and completed cleanup |

Every control has zero original-endpoint attempts and all hosts reaped; no fatal,
uninstall or close error occurred. The exact15-case runner contract is
`routing-r1-r8-session-ownership-v2`. This meets the finite exit condition in
the approved closure design. It closes the two gaps identified by the earlier
review; it does not expand the investigation to unspecified frameworks.

R2 first seeds and reads each session resource, then checks its absence in the
next session. Its same-child A→A transition is essential: the destination marker
alone would still look correct if a prior session leaked. R3 removes its local
bootstrap listener before enrollment and does not mutate retained creator
arguments. Source assertions check `@@in_transaction=1` before and after rejected
first enrollment; the JSON's PASS is tied to those assertions and the source hash.

## 3. Negative controls

Both platforms exit1 at the intended case for all six mutations, with no fatal
setup error, expected sentinel counts and all hosts reaped. Individual JSON/text
receipts are retained beside each platform's control.

| Deliberate defect | Actual observation on each OS | User consequence demonstrated by the injected defect |
| --- | --- | --- |
| `no_pool_check` | A/B/A requests read A/A/A | A test can use the previous child's DB |
| `fallback` | One controlled original-endpoint attempt | Missing binding can escape to the original destination |
| `ignore_retired` | Required expired-target refusal does not occur | Background work can connect after its test scope ends |
| `global_target` | A worker reads B/B/B | Concurrent tests can select each other's DB |
| `retain_session` | Second A observes `scope-0` | Correct DB selection alone does not prevent old session state from affecting a test |
| `adopt_unknown` | Requested B observes A through an untagged connection | Unknown physical ownership can silently reuse an unrelated DB session |

The last mutation disables **both** idle discard and unknown-owner checkout
refusal. Either defense can prevent reuse; the evidence does not say that
removing only one necessarily produces that consequence. New mutations require
their exact structured observations, not an arbitrary failure. These deliberately
broken prototype outcomes are not defects observed in released mariamem.

## 4. Prior conditions and remaining implementation work

| Prior condition | Judgment | Detection / next owner |
| --- | --- | --- |
| Close R2 old-state and R3 unknown physical ownership | Satisfied | New real-guest cases, specific negative observations and exact runner contract |
| Keep original13 cases, four controls, both OSes and original-target oracle | Satisfied | Control/mutation JSON, runner receipt and successful native jobs |
| Keep fixed runtime/driver inputs and consumer defaults | Satisfied for the spike | Source/installed-file hashes and actual driver class receipts |
| Preserve exact Prepared exceptions | Satisfied; no reclassification | Accepted decision and production code have no diff. This campaign does not rerun the full P6 exception matrix |
| Preserve consuming Snapshot and child independence | Satisfied for the exercised workflow | R8; no production/storage change |
| Production early guard, hook ownership, partial-install unwind, retirement/connect race handling, actionable diagnostics | Still implementation acceptance work | Current spike CI does not prove these proposed production behaviors. Implement the targeted tests in design§6 before main adoption |
| Python>=3.9 and pytest>=7 behavior | Existing contract retained; production implementation unverified | Version-compatible error handling and early-import subprocess tests are required; no minimum-version change approved |
| Broader framework/import workflows | Remain companion decisions | Django/mysqlclient/async drivers, migration/dump tooling and wider multi-profile coverage are neither implicitly supported nor removed |

macOS15.7.9 uses Python3.14.7/OpenSSL3.5.7; Connector default selects
`CMySQLConnection`, and pure/C cases pass. Ubuntu uses Python3.14.8/OpenSSL3.0.13;
default selects `MySQLConnection`, and default/pure pass. Explicit Ubuntu C is
SKIP because its extension requires `OPENSSL_3.2.0`, per the retained
[environment receipt](v06x-connection-routing-evidence/ci-40032530547/ubuntu-24.04/connector-environment.json).
This is the previously allowed mode policy; no default was forced to pure by
the campaign and no driver was patched. The earlier Homebrew import SKIP remains
historical and is not relabeled PASS.

The [implementation design](v06x-connection-routing-product-design.md#6-implementation-work-and-finite-acceptance-after-human-approval)
already divides the work into the optional routing core/two driver adapters,
SQLAlchemy ownership adapter, early pytest integration and ordinary Go/user
examples. It names the finite production checks and maintenance cost. No new
exploration or performance campaign is required to make this implementation
decision. API spellings remain proposed; approval should include selecting the
declared initial entry boundary, particularly saved advanced Connector factories.

## 5. Missing-things scan and evidence preservation

No additional unlisted spike-completion condition was found. No current public
usage document promises the proposed routing API. No contradiction with the
continuing Snapshot or accepted Prepared contracts was found. No guest,
converter, generated-source inventory, license/provenance, release-ledger or
public runtime change is present. No stale production comment was introduced.
Independent regeneration, performance comparison, Qualification and publication
are not unfinished claims of this spike; they were not run or claimed here.

This review checked the exact candidate helper/campaign/runner/workflow and
both native artifact bundles against the original R1–R8 design, the two earlier
reviews, the productization design and continuing contracts. It does not certify
the proposed early pytest hook or production module before implementation, and
does not repeat the external source survey. Earlier pending reviews are left
unchanged; current status links this completion review.

[Mac files.json](v06x-connection-routing-evidence/ci-40032530547/macos-15/files.json)
and [Ubuntu files.json](v06x-connection-routing-evidence/ci-40032530547/ubuntu-24.04/files.json)
bind original/stored SHA256 and bytes. Known CI paths are replaced with stable
placeholders and `.log` renamed `.txt`; outcomes and diagnostic causes are
unchanged. `inputs.evidence` retains original-file hashes. Archive digests in the
summary are API metadata, not a claim to reconstruct the archive from its files.
The tested code remains fixed; this review branch changes only documents and
compact evidence. It records a recommendation awaiting Human approval.

Documentation/evidence checks:146 local file-link targets exist, saved hashes
and original-to-stored lineage match, JSON parses, public-source/version checks
and `git diff --check` PASS. Tested source and historical reviews have no diff.
No unchanged runtime tests or builds were repeated for these documentation edits.
