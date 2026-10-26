# Go-owned Live design — Human Review

Decision now: approve implementing the bounded Go-owned Live candidate described
in the pinned design. **Recommend approval for implementation**, because the
existing two-platform browser experiment establishes a useful same-app/same-DB-
address workflow and the proposed ownership boundary reuses existing Forks.
The strongest objection is that retained physical connections/pools and delayed
application jobs prevent safe reset: users must explicitly quiesce them. The
verified Django fixture already meets that condition, making this a useful first
contract; if automatic pool/session preservation is the requirement, this design
should not be approved as satisfying it. Implementation approval is separate from
main adoption, version inclusion, Qualification and release.

## Reviewed artifact and reconstruction

Artifact: [v06x-live-host-design.md](https://github.com/masahitojp/mariamem/blob/fdca312a3b4640da09f45f7c009840eb31c28e3a/docs/reviews/v06x-live-host-design.md)
at source_commit `fdca312a3b4640da09f45f7c009840eb31c28e3a`, branch
design/v06x-dogfood-e2e-plan. Design's starting branch source is original
`778e6d6da05aed53455e0d18c909cee8cd7e7cf8`; product code basis is
`bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. Reviewed runnable prototype is
`ab085d3c432b6b1483b7b937500b775d4a3faf53`. The user supplied continuation after
CI success rather than review fields; these artifact/base/scope identities and
the current decision were reconstructed from that context and Git.

One metadata read confirms [CI40304818129](https://github.com/masahitojp/mariamem/actions/runs/40304818129)
success on exactab085d3, jobs121511214468 (Mac) and121511214929 (Ubuntu).
Both original ZIPs and all recorded member checksums were verified again;
raw same-PID/DB-port observations and original source/result identities were
cross-checked against the four positive/eight mutation campaigns. This review
uses the [saved receipt](v06x-e2e-guest-live-evidence/ci-40304818129/assessment.json)
and [checksums](v06x-e2e-guest-live-evidence/ci-40304818129/SHA256SUMS.json), not a
new browser run. Neither metadata nor prototype code demonstrates Go-host Live.

## Material implementation conditions and detection net

| Condition / possible user impact | Current code evidence | Detection now and required candidate check |
| --- | --- | --- |
| Go implementation could compile while Live is never called | CI-tested source tests/e2e_guest_spike/conftest.py:87 constructs Python LiveRelay; Go provider uses ordinary Fork | Existing positive/mutation tests validate the prototype topology only. Replace Python relay fixture with actual host-backed public Live and add same-process Go Live acceptance; retain original Go per-test Fork as control. |
| Cancellation after reset publication could report failure although new SQL is already admitted | internal/control/shared.go:399 unconditionally joins ctx cancellation into a completed result | Existing shared_test.go:12,67 tests generic cancellation/EOF, not Live commitment. Deterministic barriers before/after commit and a narrowly scoped committed-success rule are required. Preserve other operations' cancellation behavior. |
| Cancelled/late creation could orphan endpoint, child, Session or temporary backing | control.runWith:400 cleans database/snapshot keys only; python/mariamem/_session.py:173 likewise handles only those resource types; shutdown/cleanup currently count ordinary DBs and Snapshots | Current generic tests cannot catch an unregistered Live. Add typed live cleanup in both paths, live-only shutdown/EOF tests, exact Session refcounts and actual process/temp-directory cleanup. |
| Closing the parent baseline could block forever or make Reset reuse dirty data | snapshot.go:63 pins only startup; snapshot.go:79 permits child survival after parent Close; Owned.Acquire:280 holds a read lock until release | No existing test covers a Live borrowing that parent. Require short-lived startup pins; parent Close must finish without waiting for Live lifetime. Reset from closed baseline must reject while preserving old child; caller stops test admission. |
| In-flight handshakes/idle pools could bypass drain or accumulate workers | internal/host/server.go:122 reserves existing backend session slots; Python prototype tracks accepted clients before dial | Existing live_checks has a held transaction; additional direct-Go idle-session/handshake, capacity, repeated-connection/worker cleanup and race tests are required. Expose capacity through the private Go backend adapter; ordinary backend fakes need corresponding changes. |
| An old application task could reconnect after reset and write into the next test | Fixed endpoint has no caller/test generation token; guide target W5 registers worker/late-job work separately | Invisible to transport-only drain and existing browser cases. Caller must quiesce app work; arbitrary delayed/retried workers are explicitly outside the first contract. Old physical-endpoint rejection is not a proof about fresh connections from old jobs. |
| New host code changes might never start the experiment CI | ab085d3 .github/workflows/e2e-guest-spike.yml filters workflow/test paths and uses the prototype branch | Candidate workflow must include new host/public/SDK paths and the implementation branch, not merely reuse the old success badge. Existing normal CI cannot prove Live semantics while no test invokes it. |
| Source-only success could be mistaken for a distributable API | Existing receipt explicitly loads source SDK and source-stamped binaries | Product candidate needs installed Go/Python consumer acceptance and relevant normal SDK/routing/Fork regressions. Earlier source spike is not that evidence. |

All eight are bounded implementation conditions or explicit capability limits,
not observed defects in the current stable product. The design accounts for them
at lines96–198 and214 onward. Do not mark any unimplemented check PASS or treat
an absent CI detector as evidence that its property holds.

## Prior conditions cross-check

| Prior acceptance boundary | Judgment |
| --- | --- |
| Same authored application/migrations/UI, native observation reference | Satisfied for ab085d3: hash-pinned inputs and four raw positive comparisons. Original3446b5c native receipts remain original. New Go reused-app variant needs its own pinned native control. |
| Python same process/HTTP/DB endpoint, failure-after-commit isolation | Satisfied for test-only relay on both OSes/Python versions. Does not establish Go-owned endpoint behavior. |
| Go independent per-test Fork/configuration | Satisfied by actual Go public Snapshot/Fork owner. Go reused-app Live remains unverified and is a named candidate exit, not inferred from Fork. |
| Held transaction refusal, reset failure blocks admission, explicit retry, cleanup | Satisfied for bounded prototype SQL controls. Direct-Go idle/handshake, late reply, cancellation and concurrency extensions remain unverified. |
| Separate live decision; explicit preparation settings; marker arguments unchanged | Preserved by design: new explicit lifecycle, no live=True, automatic preparation routing or implicit registered-profile switching. See separate-live decision at v06x-shadow-maria-entry-design.md:64 and routing contract. |
| Snapshot immutable/consuming-source contract | Preserved in proposal: successful original Snapshot consumes DB; new Live borrows that open Snapshot, replaces only private children. Verify implementation later. |
| Worker/parallel/resource workload registration | Still outstanding W5/W8. Sequential browser proof does not close the entire dogfood plan or existing-session continuity target C4. |
| No arbitrary framework, cold/setup or performance claim | None found in the proposed guarantee. Measured protocol-hop overhead and reliable effort estimate remain unknown. |

## Confirmed non-gaps and missing-things scan

- No public implementation change is present in this design/review diff. Current
  README, docs/go.md, docs/python.md and docs/releasing.md do not promise the new
  Live methods. No contradictory current usage claim was found. Historical
  separate-live wording is contextualized by the latest status proposal.
- No guest/generated-source, canonical patch, HANDWRITTEN_FILES, baseline pin,
  version or release-ledger change is present. Proposed new files are outside
  internal/generatedgo; installer list ownership (generate_runtime.py:19) need
  not be broadened merely for a new public Go source file.
- Both supported app-host OSes and Python versions are covered by the prototype
  receipt. No native Mac MariaDB-server result is inferred; native reference is
  the originally recorded Ubuntu observation. The explicit numeric HTTP-bind
  harness adjustment and failed original sources remain documented.
- No stale implementation comment about a removed Live behavior was found:
  current product has no Live implementation. Current ordinary SQL/session/
  Snapshot behavior is inspected as the baseline, not claimed as Live acceptance.
- No silent integration/release decision is bundled. Qualification, performance
  testing and publication remain later gates. Those are not omissions from this
  design-only scope; Go-host runtime/installed-consumer verification is expressly
  unfinished until an implementation candidate exists.

## Concrete next action and review limits

On approval, implement on experiment/live-host using a disposable budgeted
workspace and preserve a minimal production candidate against stable main.
Implement the common Go endpoint/lifecycle first, then both adapters, typed
control ownership/cancellation tests, actual Go/Python browser acceptance and
source-bound CI. Preserve the real mutation oracles and publish PASS/FAIL/SKIP
with installation/resource cleanup evidence before a product adoption review.
Do not merge the exploratory history into main.

This review inspects the pinned design, relevant existing host/control/SDK code,
prior decisions and saved native/guest E2E receipts. No new runtime build,
benchmark, broad ORM acceptance or opposite-platform execution was started for
these documentation changes. Byte-forwarding edge cases, cleanup races and real
Go Live runtime behavior cannot be judged complete from the prototype; their
finite candidate checks are specified above.
