# Legacy continuation: finite PASS, positive branch coverage FAIL

The requested verification is **incomplete / NOT_READY**. The fresh legacy
producer, exact binding/negative controls, original smoke/P1/P2 and common
archive→drain→capture→restore/isolation case pass. The one supplemental positive
spare-archive stimulus fails: after5s the root is healthy/ready, no SQL sessions
remain, and logs contain timed_wait only. No positive marker is present.
This is missing branch coverage, not proof of an engine regression.

Recommendation: retain the verified paired result and helper repair, keep137/138
Open, and do not adopt13.0.2 or claim a maintenance win. The material limitation is
that the source-grounded stimulus still does not establish the archive rollover
request reaching the idle branch. Checkpoint/redo progress cannot replace that
evidence. Further work needs a separately bounded source investigation of that
request's production/consumption, followed by an explicitly agreed finite case;
there is no retry or additional native producer in this continuation. A possible
next cost is30–60min source work, then up to one60min producer plus30min
translation/host and15min suite per required route, subject to a new decision.
These are estimates/options, not an approved extension or mandatory tooling gate.

## Scope and physical capacity

Human approval for this continuation only changed both outer and nested guards
to free floor6GiB / owned ceiling24GiB.
[Approval](https://github.com/masahitojp/mariamem/issues/138#issuecomment-6723383106).
137 was updated before the producer. Global helper defaults remain unchanged.
The old floor12 stop at free11.98/owned4.04GiB remains historical. Raising the
owned ceiling alone had not supplied physical disk; lowering the approved floor
changed required available headroom from~18.22 to~12.22GiB using the prior
6.217GiB incremental estimate. Actual launch available15.80GiB was sufficient
for that estimate; this was never a guarantee against other filesystem writers.

Outer guard counts the entire assigned checkout. Nested /owned contains every
owned mount, source clone, archive/download, SDK, work/output, host/cache,
TMPDIR/GOTMPDIR and venv. Both6/24 configurations were asserted before launch,
and the nested wrapper asserts actual numeric thresholds too. The operational
wrapper lives outside the pinned clean checkout and invokes its unchanged
build_checked.py. The existing shared Docker image was used, not deleted or
modified; no other checkout/user files were cleaned.

## Exact identities and verification

- MariaDB source_commit620a4b5624222048fece7fe1789978ae0675cae2 and
  tag_object_sha308a50778fb4916ddde0d2923feea3d11dcc92c8 were fetched as actual
  Git objects and checked with git_identity.inspect_ref/require_commit before build.
- Legacy producer/host source_commit32c799031f619164d3730b61a0bc9d7ae48dcd9b.
  Fresh empty work/absent SDK/source/unpack and actual canonical success are saved.
  Guest d29caafda1ed32851df856dc7fcba3871c3c7ea75df8f2c5d4976b3eb9132c95;
  host2379e23373cf8f2c84f67774499343beb63db31acc8173464c9dd4a05b66ef21.
- Full prepared tree, pre/postimage record, flags/link/cache, linked digest,
  source/translation/install inventories and exact worker maps/bodies are saved.
  Fn153/free, Fn131/yield, Fn214/entry; TLS505; ABI16/40/44.
  Complete bodies equal the original after the explicitly recorded mapping.
  Real installer rejects a corrupted expected body digest and map_size44→48;
  neither negative runtime was compiled. Original native split/source guards remain.
- Helper plus source observer19/19 pass (complete helper16 plus observer3, no -x).
  Both full-file profiles and selector/TIME/corruption negatives pass again.
  Syntax and touched public-source checks pass; the broad public check still has
  ten unchanged historical evidence/reference findings, outside this boundary.
- Engine/UCA/shared patches/toolchain/prepare bytes match the existing native
  source4b3954a0faf42986459bc1ee68727be16d67bcbb / guest889f21b796c4daaf5244486cce84bfe6a82c758437af400e831d0ed10f0a067e.
  Declared profile/native-overlay differences are explicit. Old native79 cases and
  88+38+234+241=601 observations remain their original logical counterpart; its
  binary was already cleaned. No receipt is relabeled and no helper-only native
  rebuild occurred. Original f0 helperFAIL and old701 prose stay historical.

## Actual runtime outcomes

Original dev smoke1/1 PASS, P1 all6 checks PASS, P2 all15 cases PASS with failures0;
no smoke skip/error. Original protocol/type/metadata expectations are unchanged;
only the existing exact13.0.2 version rebind is retained with both hashes.

The original paired archive case PASS:4MiB log/archiveON-OFF,256×64KiB writes;
LSN36889→16947491, checkpoint16959831;256rows/16777216bytes. Close and drain
observations have active_connections0/busyfalse/ready. Exactly one capture
succeeds, children retain row/byte/id-sum/payload predicates, and a private insert
leaves the sibling unchanged. This is the matched common scenario alongside the
old native PASS, not a timing comparison or proof of the old busy failure's cause.

The added archiveON/dirty-threshold-zero/idle case executes once and times out
waiting5s for ISSUE138_BRANCH spare_archive. Both observed states remain healthy
and drained; logs contain ISSUE138_BRANCH timed_wait only. The supplemental
capture, ordered-data digest and child checks are NOT RUN after that failure.
No native supplemental case, parameter retry, altered branch condition, throwaway
observer build or further runtime command follows. The aggregate suite exits1;
its earlier generic 'test completed' line precedes supplemental execution and is
not an aggregate success. See raw suite output and result.json.

## Costs, limits and remaining scope

| Actual stage | Wall seconds | Outer peak owned GiB | Outer minimum free GiB |
| --- | ---: | ---: | ---: |
| Fresh producer |1360.53|6.462|15.795|
| Translation |141.06|5.649|18.530|
| Exact binding |15.86|4.140|18.399|
| Installer negatives |5.93|4.200|18.347|
| Host compilation |196.21|5.508|16.751|
| Finite suite including missing-marker failure |19.73|5.136|16.951|

Canonical producer reports1349.45s; nested guard1352.42s/peak6.070GiB/minimum
free16.391GiB. These are distinct boundaries/samples, not replacements for the
outer records. No disk or time breach occurred. One guest/translation/host/suite
was used; the conditional second native slot was not spent after the failure.
CI0/benchmark0/public expansion0. Fresh archive acquisition and unequal programs
preclude a native/legacy speed ranking.

New active work is estimated20–30min including source/staging/diagnosis/reporting,
with new measurement-runner/tooling edits estimated3–5min; waiting is separate.
Prior helper phase was charged29min active and10–15min tooling, so conservative
cumulative active59/tooling20min fits90/20. These are estimates, not stopwatch
measurements. Wall remains within the original4h30 from~14:28Z; execution stopped
at16:10Z. Preservation/cleanup follows without expanding the investigation.

Native removes the two old CAPI metadata adapter definitions and MYSQL_BIND-only
repair obligation, while retaining TIME/bootstrap OOM/native conversion/lifetime
protection. Added explicit profiles, full-image bookkeeping, helper compatibility
repair, exact binding review and regression execution are real costs. **Overall
update burden remains INCONCLUSIVE**; this run establishes no automatic net win.
Public C3/factory/installed Python/bothOS132/134,128 final comparison, main/product
version adoption and release are separate. All four protected parent files are
byte-identical to f0; no pre-existing user edits were present at this phase's start.

Cleanup result is recorded separately after compact evidence is committed/pushed.
