# Dump comparison resumption — exact candidate and ordered campaign

2026-10-25. After accepting acquisition evidence and archiving the353bf92
producer preflight, the Human explicitly resumed the bounded comparison:
new minimal experiment candidate -> canonical dump bound to that candidate ->
fresh native reference -> guest native client -> library reader -> independent
children -> failure/admission controls. This is spike authorization, not
productization, main integration, Qualification or release approval.

## Candidate and fixed input

- Base source_commit: `353bf9291d96785f8dcaa3585cec00e56242256e`.
- Candidate source_commit: `5a9661d821150b3992466fa49a071a213cbaab78`, branch
  `experiment/dump-import`. The candidate restores selected test-only paths from
  parked03cad71 and adds binding/orchestration. It does not merge parked history.
- Product/API/SDK/guest/converter/generated/release inputs are unchanged.
  The candidate diff contains18 test/workflow files, including the unchanged
  canonical input and offline Mac acquisition pins; no production implementation.
- Canonical application dump SHA256:
  `081ef0273c3625cb1d2a143415b90e9845bc2132312853a047eed09c8807e87c`.
  Its original production source_commit remains
  `6d81a2f99d0b5bd09bb5ab48dbf1ae23ca27e149`; original manifest SHA256 remains
  `2850011163620f3a9e6c8dd0b343e54835c6d8b475706b0671302121de8a0b10`.
  Those bytes and that earlier PASS are not relabelled as candidate execution.

The existing users/addresses revisions/seed and the same extension/routines are
retained. `bind_input.py` verifies nine current migration/seed/producer source
files, literal extension/values/options, original input bytes and unchanged
runtime/build inputs. Before submission the exact clean candidate passed this
local source/input verification (`INPUTS_VERIFIED`, not producer/import PASS).

## Ordered execution in the submitted workflow

The [candidate workflow](https://github.com/masahitojp/mariamem/blob/5a9661d821150b3992466fa49a071a213cbaab78/.github/workflows/dump-import-spike.yml)
implements these stages. Actual native/guest results are not claimed by this
pre-submission record.

1. **Fresh Ubuntu producer and native reference.** Repeat the exact identity /
   TCP/root/definer preflight at the candidate SHA. Re-execute the unchanged
   application producer at that same SHA and require its output to match the
   canonical dump byte-for-byte. Preserve the new producer manifest separately.
   `BOUND` requires this fresh producer PASS, exact current source, matching
   schema/data/options and the canonical hash. Different bytes stop the campaign;
   there is no normalization/replacement of the canonical file.
2. **Native reference rerun.** Import the bound bytes into clean native12.3.3
   app databases using the pinned native client. Collect schema/constraints,
   engine/collation, exact values, routine definitions/results, restored session
   state and subsequent SELECT; also retain native negative-input controls.
   Each reference receipt carries the new SHA and complete binding. The guest
   jobs require this reference job to succeed.
3. **Both native OS jobs.** Ubuntu x86_64 and macOS arm64 each build one exact-SHA
   Go1.26.10 host and verify its embedded VCS/toolchain/hash before use. Reuse it
   across Python3.11/pytest7 and Python3.14/pytest9. Mac selects its OS-specific
   pinned12.3.3 bottle, records dependencies/relocation/hashes, repeats native
   acquisition and reruns a native reference before any guest import. Compare
   its native observations to the fresh Ubuntu reference.
4. **Ordered guest imports, then child lifecycle.** Probe native client import
   and reader import independently, in that order, against the same bound bytes
   and native observations before attempting Snapshot. Then run the stable
   preparation/routing lifecycle with two independent ordinary application child
   tests for each route/interpreter. The first commits a change; the second must
   retain imported state. Check routine/value/metadata retention and constraints.
5. **Guest failure/admission matrix.** After the success cases, run invalid SQL,
   malformed framing and SOURCE controls on both routes. Check exact known SQL
   causes where available, original-file locations, partial source state,
   connection/process/directory cleanup and no Snapshot/test admission. Native
   client ordinal/SQLSTATE availability remains reported honestly. Preserve raw
   inputs, stdout/stderr, JUnit, lifecycle events and per-case classifications.

Every consumer recomputes the binding against the exact clean checkout and
fresh producer manifest; wrong-source references and reused old host stamps are
rejected. The original manifest and the fresh candidate manifest have separate
source fields. The two same-byte files are not different route-specific corpora.

## Local checks, receipts and stopping boundary

Local verification passed25 canonical-binding/framing/classifier tests and the
25 existing native-acquisition/source/capture tests. The checks include changed
dump/manifest/input rejection and a fresh-producer receipt with wrong source or
changed bytes. They do not establish native import or guest behavior. Python
syntax, YAML/native-reference prerequisite/both-platform matrix and public-source
boundary checks also passed. Raw canonical input preserves original whitespace.

The local disposable checkout uses a2GiB budget and8GiB free-space reserve and
only runs focused local checks. CI uses guarded8GiB workspaces with a4GiB
free-space reserve for host/native work and removes owned binary/datadir/cache
scratch after completion, retaining evidence only. The pinned workflow contains
reproduction commands and artifact paths. Native reference and both-platform
comparison artifacts are named with the candidate SHA; the handoff provides the
run URL. No broad release qualification is run.

The bounded reader remains a test-only prototype, with no public API
or product dependency. No engines/collations/routines are rewritten or stripped,
and no continue-on-error import mode is enabled. Preparation automatic routing,
MySQL-produced/external legacy input, views/triggers/packages/events and new
framework coverage remain outside this corpus. Mac dependency availability is
recorded without a cold-install/setup-cost claim. Guest/runtime fixes, if needed,
must return as a separate scope decision; a failing route stays visible in the
comparison. No productization, main integration, Qualification or release is
authorized by executing this campaign.
