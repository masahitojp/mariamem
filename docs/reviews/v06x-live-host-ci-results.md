# Go-owned Live — exact candidate CI result

[CI40349469630](https://github.com/masahitojp/mariamem/actions/runs/40349469630)
succeeds on source_commit `a1baaad83922d9ac6ff7fe46d64db3fbfcde542f`,
experiment/live-host. The original run/jobs/artifact metadata, all four original
artifact ZIPs, their API SHA256 digests and per-member checksums are preserved
in the [receipt](v06x-live-host-evidence/ci-40349469630/assessment.json).
The CI-tested ref remains fixed. This records candidate verification; main
adoption, version inclusion, Qualification and release remain separate decisions.

## Confirmed matrix

| Observed host | Python3.11 | Python3.14 |
| --- | --- | --- |
| Ubuntu24.04 x86_64 native reference | PASS,3.11.17 | PASS,3.14.8 |
| macOS15 arm64 public Go/Python Live | PASS,3.11.9 | PASS,3.14.7 |
| Ubuntu24.04 x86_64 public Go/Python Live | PASS,3.11.17 | PASS,3.14.8 |

Both native jobs check exact native image/program/source identity and the bounded
TCP/root/definer probe, then run fresh native Python and Go application controls.
The reconnecting Go variant retains its source hash and native executable hash.
Mac consumes the same-source Ubuntu native reference; executable bytes differ
across platforms and are not compared as one artifact.

Both guest-host jobs pass canonical check (Go tests/vet, public/generated/source
checks,1030 Python passes/45 explicit skips/76 subtest passes), canonical runtime
integration and the internal/live race suite. Each Python-version cell passes53
focused ownership/oracle/HTTP-harness tests and the browser/real-control campaigns.
Canonical broad checks and installed-wheel execution use each job's default
Python3.14 interpreter, not a claim of full broad/installed3.11 repetition.

The artifact re-assessment recompiles the exact candidate's native and public
comparison predicates and applies them to original XML/events, not only PASS
summary JSON. It also verifies original artifact digests, source stamps, fresh
native binding, required SQL control flags and installed-consumer outcomes.

Confirmed campaign totals:

- Four fresh native application controls: Python and the Go variant for both
  interpreter versions.
- Eight public Live positive routes: both languages on all four OS/Python cells.
- Sixteen actual lifecycle defects detected: skipped reset and restarted app on
  both languages in every cell, with their exact row/PID/setup-error signatures.
- Twelve retained original Go per-test Fork control campaigns.
- Forty-eight real SQL/lifetime/failure control tests: idle/transaction-held
  session busy refusal and recovery, handshake refusal/old-data preservation,
  closed-parent refusal, and a common Go engine replacement-failure probe with
  admission block, explicit retry and retired-endpoint closure.
- Installed candidate wheel/default bundled host and external Go-module Live
  consumption pass on both OSes; source consumption, cleanup, busy refusal and
  closed-parent refusal match their oracles. The external module uses an exact
  local candidate replacement, not a downloaded published-module release.

Raw positive browser suites intentionally have one named post-commit assertion
failure. Their expected pattern and the next test's fresh baseline are required.
Mutation suites also contain exact expected failures/errors; these results are
not a claim that all raw browser pytest invocations exit0. Canonical45 skips and
its existing unknown-shadow-marker warning remain explicit.

## Failure history and boundary

The original ca74140 run40330300896 stopped at a missing source SDK import path.
The subsequent df018fd run40335866184 passed Mac3.11 application campaigns but
failed a Mac3.14 late-cleanup unit assertion. Its test observed host deletion
before the asynchronous Python reference release. Correction2434876 changes
only the waiter/its deterministic regression tests; sourcea1baaad adds preserved
failure records. Product/runtime/SDK code is unchanged across df018fd -> a1baaad.
The [original failure receipt on the fixed candidate](https://github.com/masahitojp/mariamem/blob/a1baaad83922d9ac6ff7fe46d64db3fbfcde542f/docs/reviews/v06x-live-host-evidence/ci-40335866184-macos/assessment.json)
retains its own source/digest. No failed result is relabeled PASS.

The candidate implements the [approved design](v06x-live-host-design.md).
Applications must quiesce requests/jobs and release physical SQL sessions before
Reset; examples use Django CONN_MAX_AGE=0 and Go MaxIdleConns(0). Session continuity,
automatic application-pool retirement, generation fencing of delayed jobs,
parallel tests sharing one Live and cold/setup/performance claims remain outside
this result. The separate W3 ordinary-Django investigations are not part of this
CI candidate or a general adapter-support claim.

## Receipt reproduction

The [checksums](v06x-live-host-evidence/ci-40349469630/SHA256SUMS.json) cover metadata,
assessment, validation script and losslessly encoded original ZIPs. To re-assess,
copy those JSON files and validate.py to a disposable directory, decode each
`*.zip.base64` there to its `*.zip`, and run that copy of validate.py from a
repository containing the pinned commit. The validator reads candidate source
with git show and original artifact members; it does not build or execute the
runtime or contact GitHub. Temporary download copies were removed after durable
receipt verification.
