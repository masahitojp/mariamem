# Go-owned Live candidate — adoption review

Decision now: accept the bounded implementation as the basis for preparing a
minimal main candidate. **Recommend conditional acceptance for that preparation;
hold direct main integration of the current tree.** Same-process/same-endpoint
Go/Python E2E behavior, native comparison and installed consumption now have real
both-platform evidence. Before main integration, connect the maintained main/PR
acceptance gate and reconcile production cleanup-retry semantics with its tests.
The selected production diff must then be reviewable on its own exact source.

The strongest objection is application coordination: retained physical sessions
or delayed jobs prevent a safe reset. The authored reconnecting applications meet
the documented quiescence condition, making this useful within the agreed bound.
Automatic pool retirement/session continuity/job fencing would require another
contract. This recommendation does not decide main integration, version inclusion,
Qualification or release, or authorize any code changes during this review.

## Pinned object and reconstruction

The Human asked to continue after CI receipt completion rather than supplying new
review fields. These identities and the preparation/adoption decision above are
reconstructed from that conversation and verified against Git:

- Artifact: [CI result report at cd8033f](https://github.com/masahitojp/mariamem/blob/cd8033f53bc73b84a0be2b69e908464e6386de66/docs/reviews/v06x-live-host-ci-results.md),
  source_commit `cd8033f53bc73b84a0be2b69e908464e6386de66`, design/v06x-dogfood-e2e-plan.
- Candidate: `a1baaad83922d9ac6ff7fe46d64db3fbfcde542f`, experiment/live-host.
- Base: `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`, local stable main.
- Prior conditions: [approved implementation design](v06x-live-host-design.md),
  [design review](v06x-live-host-design-review.md), and the separate-live/version
  decision in v06x-shadow-maria-entry-design.md:64.

One metadata read confirms [CI40349469630](https://github.com/masahitojp/mariamem/actions/runs/40349469630)
success on exact a1baaad: native jobs121665248537/121665249172, Ubuntu121672990953
and Mac121672991392. Original ZIP/API digests and every saved member checksum were
rechecked. The saved validator re-applied the exact candidate's native/public
predicates to raw XML/events. No runtime, CI rerun or benchmark was executed.

## Conditions before main integration

### F1 — actual Live acceptance is still scheduled only on the experiment branch

[.github/workflows/live-host.yml:2](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/.github/workflows/live-host.yml#L2)
only has push for experiment/live-host and workflow_dispatch. Main/PR development
checks run verify.py check/integration, but
[scripts/verify.py:83](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/scripts/verify.py#L83)
does not invoke tests/live_acceptance. Ordinary checks run state-machine/wrapper
unit tests; the positive public Go test uses a fake backend
([live_test.go:24](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/live_test.go#L24)).

Impact: after landing, real Live/browser/native/installed-consumer regressions
would lack the supplied automatic main/PR execution path. Current unit/race tests
remain useful, but do not replace that real-use net. No supplied check asserts
that the Live workflow runs on main/PR. Repository branch-protection settings
were not audited here.

Required: prepare a maintained main/PR workflow with relevant shared-host, SDK,
Snapshot, API and acceptance input paths, preserving source-bound native references
and both OS/Python routes. Re-run that candidate's bounded matrix; retain a1baaad's
receipt unchanged. This is an integration prerequisite, not a failure of its
observed experiment matrix.

### F2 — real adapter cleanup retry differs from the transient fake's behavior

[endpoint.go:199](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/internal/live/endpoint.go#L199)
retains a child on Close error; FinalCleanup calls Close on it again at
[line357](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/internal/live/endpoint.go#L357).
The production shared-host child caches the complete close result in sync.Once
([internal/control/live.go:40](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/internal/control/live.go#L40)).
The public Go child embeds Database.Close, which also returns the cached result
once closed ([mariamem.go:175](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/mariamem.go#L175)).
Calling these again replays the recorded error rather than retrying the original
shutdown/filesystem work.

The cleanup-retry test instead uses echoChild, whose first injected error is
cleared for the next call
([endpoint_test.go:79](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/internal/live/endpoint_test.go#L79),
[test313](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/internal/live/endpoint_test.go#L313)).
Real replacement-failure acceptance injects Factory.Start failure, not retirement/
Close failure (tests/live_acceptance/live_checks.py:49). It proves that recovery
path, not production adapter cleanup retry.

Facts: ownership/error retention and fail-closed admission are implemented.
Unknown: successful retry of unresolved cleanup through the real adapters.
A real normal-use resource leak was not reproduced. A terminal Close error can
legitimately remain stable; the prior design also requires unresolved cleanup to
be retained for retry/final disposal (design:115–119,166–169). Those meanings must
be made explicit together before counting this condition fully satisfied.

Required: retain stable public Close errors, choose the internal final-disposal/
terminal-error policy, and add adapter-level fault coverage showing that policy
for Go and the shared host. If actual cleanup retry is required, it needs an
internal path that performs work beyond replaying the cached public Close result.
If a narrower terminal policy is chosen, record the Human's agreement rather than
silently reducing the accepted condition. The current transient-fake test cannot
detect this adapter distinction.

### F3 — select the main diff and publication wording explicitly

The candidate is directly based on bf3a29c, with no exploratory engine patch, but
its74-file diff includes production code, test owners and copied historical
reviews/failure receipts. A blind history merge is not the requested smallest
production integration. Some copied historical relative links point outside this
tree: design.md:23,32–33 and design-review.md:30–31 reference prior E2E evidence/
plans that are absent at a1baaad. The actual API guide has no broken local link.
check_public.py checks inventory/content, not Markdown target existence, so those
historical link omissions are invisible to its green result.

Required: a reviewable inclusion list/patch for runtime+SDK, necessary tests/native
inputs, maintained CI and usage guidance. Preserve original historical reviews in
their evidence context and link pinned originals when needed. docs/live.md:1–4
still correctly calls this a candidate/unpublished API; adjust current-source
adoption/discoverability wording when preparing the main candidate. Keep version
inclusion and release approval separate. No code selection or integration was
performed by this review.

## Prior acceptance and detection net

| Prior condition | Judgment / decisive evidence / detection |
| --- | --- |
| Actual public Go/Python Live; retain Go Fork control | Satisfied in bounded matrix:8 positive Live routes and12 Go Fork control campaigns; raw candidate assessor validates PID/HTTP/DB address/generations and native rows. tests/live_acceptance/conftest.py:97; go_owner/main.go:122. |
| Same app/native inputs; explicit reused Go variant | Satisfied: input hashes, fresh a1 native controls and variant source hash in the receipt. native.py/run.py reject source/variant mismatch. No cross-platform binary-byte equality is inferred. |
| Drain idle/transaction/handshake, failed replacement blocks SQL, explicit retry | Satisfied for those tested paths: real busy/parent/factory-failure controls48 passes; live_checks.py:10–64 and run.py:105–111 require cleanup and control flags. Retirement cleanup-error retry is F2. |
| Commit/cancellation and concurrent Reset/Close | Satisfied at the deterministic engine/control boundary: endpoint_test.go:209,282,331 and control/live_test.go:47. Canonical integration races control/public packages and the explicit workflow races internal/live. Other operations retain cancellation handling. |
| Late creation, capability refusal, Session ownership and EOF/shutdown | Satisfied within tested routes: typed registry/late cleanup in control/shared.go:397,426; internal/control/live_test.go:84,125; Python test_live_unit.py:68,102,111,139. Original Mac failure has deterministic two-boundary detectors and its own source receipt. |
| Parent lifetime; short startup pins | Sequential parent-close behavior is real-tested in Python controls and external Go consumer: live_checks.py:38; go_consumer/main.go:98. Go factory delegates to Snapshot.Fork's existing short pin (live.go:50; snapshot.go:63); ordinary Fork/Close race tests remain in canonical integration (mariamem_test.go:335; tests/gointegration/owned_prepared_test.go:238). Shared adapter explicitly holds only a startup RLock (control/live.go:60). A dedicated Live close-during-startup runtime campaign was not observed; no claim of one is made. |
| Resource bounds/binary transport | Source and unit/race evidence: reserve before dial/capacity at endpoint.go:119; binary/half-close, capacity and pending-dial tests at endpoint_test.go:139,259,331. Completed workers are removed. W8 large-count/FD/memory/performance remains outside this bound. |
| Real installed consumers and ordinary regressions | Satisfied for observed installed Python3.14 on both OSes and external Go with exact local source replacement; not remote published-module qualification. Canonical1030 passes/45 skips/76 subtest passes per host and integration include old SQL/Fork/routing gates. Python3.11 has source-SDK browser/focused coverage, not full installed/broad duplication. |
| Maintained integration gate/minimal adoption patch | Still open: F1/F3. Experiment execution was valid; main integration prerequisites are not yet prepared. |
| Delayed jobs/session continuity/parallel shared Live | Explicitly outside the first contract (design:202–212; docs/live.md:24–28,51–56). Transport drain cannot detect old jobs opening fresh connections; no CI detector exists for that promise and none is made. |

All candidate code references above are at a1baaad. These judgments distinguish
runtime observations, deterministic fake/control tests and source composition;
they do not turn unobserved paths into runtime PASS.

## Confirmed non-gaps / missing-things scan

- No changed guest/canonical patch, generated owner list/output, release baseline/
  ledger, version metadata or dependency pin was found. New handwritten files are
  outside internal/generatedgo. The public-source allowlist explicitly adds
  live.go/live_test.go (scripts/check_public.py:9), and installed acceptance proves
  inclusion. Engine regeneration is not missing for this boundary.
- No contradiction was found in unchanged version-gated README.md, docs/go.md,
  docs/python.md or docs/releasing.md. Their references to ordinary live owners/
  baselines are not promises of this new endpoint API. F3 is future adoption
  wording/link selection, not a published0.5.3 support claim.
- No live marker argument, automatic preparation routing, SQL parser, public fault
  API or guest protocol rewriting was introduced. The replacement fault probe is
  test-only and uses the common engine plus real public Fork children.
- Both supported host OSes and Python3.11/3.14 have real bounded Live evidence.
  Ordinary Django W3 Ubuntu/mixed-suite coverage is a different workstream and
  is not inferred from or required to reinterpret this receipt.
- Original ca74140/df018fd failures retain their identities; a1baaad is not a
  relabeled source. No new benchmark/cold/setup-cost claim or silent Qualification/
  release decision was found. No stale claim of preserved physical sessions was
  found in the current API/guide; cleanup retry wording is the specific F2 issue.

## Next action and review limits

On the Human's decision, prepare the smallest main-oriented candidate, closing
F1–F3 with an explicit cleanup policy and real-adapter tests. Reuse the behavior
already tested, keep a1baaad fixed and bind the revised candidate's own CI receipt.
The existing finite native/both-host/Python matrix provides its integration check;
no engine regeneration or unrelated whole-Django/resource benchmark is required.

This review inspected the pinned runtime/control/SDK diff, its tests/workflow/
usage and source-inclusion boundaries, prior decisions and original CI data.
It did not implement fixes, mutate tests/evidence, create a new runtime result,
audit repository branch-protection rules, qualify release artifacts or integrate
anything into main. No unconditional main-adoption judgment is issued while
F1/F2 and the selected production patch remain open.
