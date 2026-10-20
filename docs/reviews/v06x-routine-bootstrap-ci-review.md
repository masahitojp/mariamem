# Minimum routine bootstrap — post-CI Human Review

2026-10-20. **Recommend including the bounded routine bootstrap in the adoption
scope and proceeding to a minimal canonical candidate.** Users can create and
call the minimum procedures/functions immediately after Start, and reuse them
through independent Forks, on both supported native platforms. The decisive
new evidence is successful exact-candidate guest build and native acceptance,
including default Connector/Python 26.7.0. No further feasibility spike is
recommended for these minimum cases.

The strongest objection is that **only mysql.proc is initialized**. This does
not make arbitrary production dumps, accounts, DEFINER/privilege behavior or
prepared CALL supported. Keep that boundary explicit rather than promising
full system-schema compatibility. Within that boundary, finite positive,
negative, isolation and cleanup evidence supports adoption. A demonstrated
in-scope routine or cleanup failure would reverse this recommendation.

**One Human decision now:** include this minimum routine initialization and its
product-managed proc-structure boundary in the canonical adoption scope, or defer
it. Implementation scope was already approved; this review does not retrospectively
approve canonical promotion. Version placement remains a separate Human decision.
Neither choice here authorizes main integration, Qualification or publication.

## Reviewed object and primary evidence

- Candidate/source commit: `2c599bb904e3d523585347ccefc57ee1d833a993`,
  `experiment/routine-bootstrap`.
- Main baseline: `de0e08a9c4248969a7522abebfdee8aea6ef9657`.
- Reviewed implementation report: [candidate report](https://github.com/masahitojp/mariamem/blob/2c599bb904e3d523585347ccefc57ee1d833a993/docs/reviews/v06x-routine-bootstrap-implementation.md).
  Its pending-CI statements describe the earlier evidence cutoff; this review
  supersedes those statements without changing the historical report.
- [CI run 39379752111](https://github.com/masahitojp/mariamem/actions/runs/39379752111):
  guest job 118485907703; Ubuntu job 118488426699; macOS job 118488426773;
  all success, exact candidate above.
- [Structured receipt](v06x-routine-bootstrap-ci-evidence/summary.json) and
  [46-file evidence index](v06x-routine-bootstrap-ci-evidence/files.json).
  Artifacts `routine-source-build-<SHA>`, `routine-native-ubuntu-24.04-<SHA>`
  and `routine-native-macos-15-<SHA>` were downloaded and their contents inspected.
  Raw files are gzip-compressed losslessly; the index records original and stored
  hashes/bytes. No runner paths or failure text were normalized.
- Prior conditions: [approved design](v06x-routine-bootstrap-design.md),
  [feasibility findings](v06x-guest-system-schema-spike.md),
  [Snapshot product contract](../decisions/snapshot-product-contract.md).
  The implementation-scope approval explicitly includes rejection of incompatible
  restored definitions, not Fresh bootstrap alone.

This receipt is a documentation follow-up. It does not claim its own later commit
was the CI source. `git diff 1e2834c 2c599bb -- guest scripts internal release`
is empty: the submitted CI candidate retains the locally tested ordinary
runtime/build owners. Only evidence/docs/tests/candidate-CI changed afterward.

## Conditions checked against evidence

| Condition | Result | Evidence / limit |
| --- | --- | --- |
| Fixed-source fresh guest build | PASS | Source builder artifact; native development records bind guest SHA256 `118ef83ee066d57f946603f7e2a2b2c60d9b5f1cd4d627c3d18a73cbd963350c`, matching the earlier local build. This run performs one guest build, not full Qualification |
| Input/extraction/schema/mode/lifetime binding | PASS both | `input-tests.log`: 55 tests each; exact source receipts identify the candidate |
| Normal generation/compilation/SQL smoke | PASS both | `regeneration.log` and `development.json`; Go 1.26.8; product remains explicitly UNQUALIFIED |
| Immediate routines, existing six-case native oracle, events restriction | PASS both | `routine-runtime.log`: 8 tests each; first case reuses the previously compared native six-case oracle. Native MariaDB was not re-run in this CI. Events remain unsupported1235 |
| Fork independence, recapture, baseline Close, repeated invalid restore rejection | PASS both | Same runtime suite, including concurrent child changes; actual test owner is [test_routine_bootstrap_runtime.py](../../tests/test_routine_bootstrap_runtime.py) |
| Failed-start resources and unrelated DB health | PASS both | `go-routines.json`: all three mutated definitions rejected, snapshot Close completes, transfer directories unchanged; nine creates/nine releases and final zero active mappings. These are allocator counters, not an RSS bound |
| J1 failure and protection oracles | PASS both | Six cases each in `j1-results.json`; unprotected heap/mmap exit1 with early-free canary165→1 and both controls PASS; protected cases exit0 with/without race instrumentation. Not a general shared-memory proof |
| Python default connector | PASS both | `connector-regression.json`: 26.7.0, text CALL produces7/8 and prepared expression20. macOS defaults to CMySQLConnection; Ubuntu defaults to MySQLConnection. This does not cover both connector implementations on each OS |
| Boot mode, wire and explicit auth diagnostics | PASS both | `mode-unit.log`, `wire-unit.log`, `auth-diagnostic.log` |
| Full canonical release provenance/inventories | NOT DONE | Canonical checked-in guest/release inventory intentionally still selects old product guest. Experimental guard was not weakened; canonical adoption is the next implementation boundary |
| Target version, final Qualification, publication | NOT DECIDED / NOT RUN | No release decision or qualification evidence is inferred from candidate CI |

## Identity comparison and environment limits

Both platforms consumed the same CI-built guest and source commit. Their raw
translation manifests contain **51 identical file hashes**, and the same13
converter patch hashes. Converter executable hashes differ across OS/architecture;
that is not claimed as a binary mismatch defect.

Their installed inventories each contain99 entries. **98 are equal; provenance.json
differs.** Installation-input records include different real runner paths, and
converter binaries are platform-specific. This is not an identical-input99-file
comparison, and those provenance bytes were not normalized. The earlier local
52 raw/99 installed identical-input reproduction remains a separate evidence
cohort described in the implementation report; it is not substituted for this
cross-platform comparison.

macOS arm64: Python3.14.7/OpenSSL3.5.7; Ubuntu x86_64:
Python3.14.8/OpenSSL3.0.13. Local OpenSSL4 Connector import remains a local SKIP;
CI PASS does not remove that environment limitation. Exact host hashes and all
six J1 result codes per OS are in the structured receipt.

## Gaps, detection net and exclusions

1. **Canonical promotion is outstanding, not a failed CI condition.** Construct
   the smallest production diff, including the independently decided text-result
   prerequisite, authored guest input, generated artifacts, lifetime identities,
   license/provenance and release inventories. Release/canonical guards detect
   experimental or stale inputs; this candidate is intentionally not promoted
   by bypassing them. The experiment history is not a merge-ready unit.
2. **User-facing routine limits must accompany adoption.** Full system tables,
   accounts/DEFINER/privilege coverage, arbitrary routine-containing dumps and
   prepared CALL are not tested/supported by this result. Events remain excluded.
   Broad documentation claims are not caught by these functional tests; review
   README/Go/Python usage wording during canonical candidate preparation.
3. **Fresh SQL failure injection is a C API shim, not real-guest fault injection.**
   Real restored-definition failure/cleanup and the earlier real Fresh syntax
   failure are recorded separately. Do not conflate their coverage.
4. **No new performance qualification.** Prior macOS diagnostic costs remain
   valid only for their reported cohort. This CI adds functional platform
   evidence, not an Ubuntu startup-cost estimate or performance comparison.

No additional gap was found in source ownership: the authored helper/environment
and deterministic adapter remain the owners; no transpiled Go editing was
introduced. Canonical source.patch/converter patches and existing negative
oracles remain unchanged by the CI fixes. No public contract is changed on main.
The narrowed product-managed proc boundary remains an experimental adoption
condition, not an already published promise.

## Next action and stopping point

If accepted, prepare the minimal canonical adoption candidate and reconcile
usage docs and provenance; preserve all existing negative tests, then validate
that final tree. Do not merge exploratory history. Target version and main
integration still need explicit Human decisions; final Qualification and release
remain later gates. This task stops at Human Review. No new engine experiment,
main update, tag or publication was performed.
