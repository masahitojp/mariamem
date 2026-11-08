# One primary legacy case: missing positive marker, stopped

**FAILED / NOT_READY.** The single authorized `flush_sync=OFF` /
`lru_scan_depth=100` case still did not emit `ISSUE138_BRANCH spare_archive` within
its unchanged5s observation. The root stayed healthy/ready, active connections0,
busyfalse, with only the timed_wait marker. Configuration readback confirms that
the approved settings were actually applied. No capture, digest, restore or
child checks followed this failure, and there was no retry, alternate parameter,
optional hook, engine change or native producer.

The original legacy smoke/P1/P2 and common archive/capture/restore/isolation case
PASS. Fresh guest **and host bytes reproduce exactly**. This distinguishes a
failed finite coverage stimulus from a new engine/build regression. It does not
establish whether a request was never generated, consumed while non-idle, or
bypassed another internal gate. The two-setting proposal was insufficient for
this observed run; no old FAIL is relabeled and no branch proof is waived.

Recommendation: keep137/138 Open and stop parameter attempts. If the Human wants
more investment, choose one separately bounded causal-observation execution using
the [previously proposed observer](../issue138-spare-archive-source/optional-request-observer.diff),
rather than infer correctness or cause from the checkpoint/timed_wait line. That
requires a new tooling/source pin, full pre/postimages, fresh binding review and
one guest<=60min / translation+binding+host<=30min / finite suite<=15min; estimate
active20-30min/tooling<=10min and at least the prior~12.5GiB start free at floor6,
with~14GiB preferred for variation. This is a costed option, not authorization or
a new mandatory tool gate. Its main objection is another build/binding investment
with no promised net maintenance benefit. Retaining the current gap is an explicit
alternative; changing acceptance would need a Human decision.

## Authorization, exact source and fixture

Human approved the primary proposal only. [PLAN.md](PLAN.md) was posted to138
before expensive work. This task permits active30min/tooling5min/wall2h, one fresh
legacy guest60min, translation/binding/host30min, one finite suite15min,
CI0/benchmark0/public expansion0/native0. Both guards use and assert actual
free floor6GiB / owned ceiling24GiB for this task; no global default changed.
Initial checkout was clean including ignored state, and capacity/activity was
audited before launch. Available16.42GiB exceeded the prior12.5GiB estimate.
The estimate was not treated as a new permission gate or a storage guarantee.

| Identity | Actual exact value |
| --- | --- |
| Tooling source commit |ffc1cfd3e22267e47217804fa321d2115b1e2cdc|
| Applied fixture SHA256 |ac822754c81aec03b62802d0df8bae9fe8f2c488a0a45e7520e8466274bc4661|
| Producer / host source commit |32c799031f619164d3730b61a0bc9d7ae48dcd9b|
| MariaDB source commit |620a4b5624222048fece7fe1789978ae0675cae2|
| Annotated tag object |308a50778fb4916ddde0d2923feea3d11dcc92c8|
| Fresh guest SHA256 |d29caafda1ed32851df856dc7fcba3871c3c7ea75df8f2c5d4976b3eb9132c95|
| Host SHA256 |2379e23373cf8f2c84f67774499343beb63db31acc8173464c9dd4a05b66ef21|

Actual upstream Git objects were fetched and checked with `git_identity` before
build; tag and commit objects are saved distinctly. The producer is a clean exact
32c799 clone, not tooling HEAD. Git blob and full-byte identities are saved in
[evidence/tooling-identity.json](evidence/tooling-identity.json) and
[evidence/git-identity.json](evidence/git-identity.json).

The proposed diff was applied in disposable staging, then copied into this new
directory so old source/FAILs remain immutable. Added evidence logs save initial
archiveOFF and all four controls, applied values and successful restoration;
readback equality uses exact numbers without integer truncation. These additions
do not alter workload, wait limit, data/capture predicates or branch conditions.
The new driver changes only the supplemental fixture path. The original wait
helper's AST is unchanged. The pinned fixture and guards were committed/pushed
before the producer, and did not change afterward. Optional observer applied0.

Complete original helper16 plus observer3:19/19 PASS, no -x. Both actual full-file
profiles and selector/TIME/corruption negatives PASS; AST and touched-public checks
PASS. All31,014 fresh prepared files equal the previous legacy inventory, and
canonical source/patch/toolchain inputs remain fixed. The guest also reproduces
exactly, with independent empty-work/absent-SDK/source/unpack preflight and actual
canonical producer success: `verify_guest` was not substituted for freshness.

New generated worker bodies Fn153/free, Fn131/yield, Fn214/entry were reviewed
completely and the binding is byte-identical to the prior exact d29caafd record:
TLS505 / ABI16,40,44. The real installer rejects corrupted expected whole-body
digest and map_size44->48, and the successful installer revalidates the actual
complete bodies/manifest before host compilation. No altered runtime was compiled
for negative controls. Host bytes reproduce exactly too.

## Actual runtime sequence

[Raw finite suite](evidence/primary-legacy-suite.txt),
[machine result](evidence/result.json).

- Original smoke1 PASS, no skip/error; P1all6 checks PASS; P2all15 cases PASS,
  failures0. Original protocol/type/metadata expectations and the previously
  hash-bound exact13.0.2 version rebind are unchanged.
- Original common paired archive case PASS:4MiB log/archiveON-OFF,256rows /
  16777216bytes, LSN36889->16947892, checkpoint16960294. Immediately after Close:
  active_connections1/busytrue/ready; after existing real disconnect wait:
  active_connections0/busyfalse/ready. A single capture, restored payload/id-sum
  predicates, private child insert/sibling independence and cleanup succeed.
  This newly observes Close-before-drain live ownership on legacy, but does not
  retrospectively establish the exact cause of old128's failure.
- Primary saved controls: max dirty90.0, LWM0.0, flush_sync1, LRU1536; archive0.
  Applied readback: archive1/log4194304/flush_sync0/LRU100/max-dirty0.0/LWM0.0.
  Buffer pool16777216, page size16384, adaptive-flushing1, IO-capacity200.
  Before workload, logs contain timed_wait only and positive marker is absent.
- All256 inserts and redo>2initial-log source assertions complete. Supplemental
  exact numeric start/end LSN values were not logged before failure; the common
  case's LSN numbers above are not substituted for them.
- At archive-on-drained: active0/busyfalse/ready, timed_wait only. The single5s
  observation expires; the failure observation about5.002s later remains healthy
  and drained with the same logs. No positive marker, no assertion relaxation.
- Primary settings restoration, ordered payload digest, one capture/two children
  and isolation are **NOT RUN** after this failure. Context cleanup disposes the
  root. No post-failure SQL/runtime command follows. Original common-case PASS
  does not stand in for these unexecuted primary-case checks.

Aggregate suite exit1 is preserved. The old driver's generic `test completed`
line precedes supplemental execution and is not evidence of aggregate success.
Root health does not expose request production/consumption or the page-cleaner
idle/LRU/sync-target flags. Readback rules out an unapplied OFF/100 setting here;
it does not prove which remaining interleaving consumed or failed to produce a
pending request. Even a positive result would not identify the old cause, and
no native entry executed this new SQL case.

## Measured costs and boundary

| Stage | Wall seconds | Outer peak owned GiB | Outer minimum free GiB |
| --- | ---: | ---: | ---: |
| Fresh producer |1245.19|6.467|16.096|
| Translation |130.39|5.183|16.321|
| Exact binding |15.87|4.151|16.249|
| Installer negatives |5.91|4.211|16.175|
| Single host compilation |178.89|5.532|14.612|
| Finite suite including failed5s case |22.47|5.159|14.985|

The canonical producer reports1238.14s; nested guard duration/peak/free are saved
in producer/disk-result.json and differ from the outer whole-checkout samples.
No guard or time breach occurred. All owned host/container/source/SDK/archive/
cache/download/generated/output/TMPDIR/GOTMPDIR were counted; SDK/C source/build
scratch was removed after evidence capture and before host compilation. One
producer/translation/host/suite, native0, retries0, CI0, benchmark0. Do not rank
native/legacy speed from these setup-dependent, unequal programs.

Active work is estimated20-25min including preparation, evidence/reporting and
cleanup, with runner/fixture tooling3-5min; waits are separate, not charged as
measured active work. These are estimates, not stopwatch values, within30/5.
Wall through execution is about33min from17:03Z to17:36Z, within2h.

The existing native4b3954/889f79 cases and601 named observations plus its common
archive PASS remain their original exact logical counterpart for unchanged shared
inputs, not a new native execution or available binary. Native positive branch
coverage remains unverified.137/138 stay Open; publicC3/factory/Python/bothOS132/134,
128 final comparison, main/product13.0.2 selection and release remain outside.
Native still removes two old CAPI metadata adapters and MYSQL_BIND-only repair,
but explicit profiles, helper repair, source diagnosis, binding and additional
verification cost remain real. Overall maintenance burden is **INCONCLUSIVE**.

Personal owner paths and trailing producer diagnostic whitespace are normalized
with original and normalized hashes; SQL/readback/failure content is unchanged.

Runtime evidence was committed/pushed as108c5985 before final disposal. Clean
ordinary32c799 clones and retained owner history were inspected before removal.
The helper protected the converter's uncommitted extracted Git tree; all420 files
were proven equal to the locked archive plus13 exact source32 patches, with no
HEAD/history or unique edit, then this owned copy was removed. The remaining
scoped helper cleanup succeeded. A final audit paused on an unlisted tools folder;
its sole wrapper matched the committed guard, then it was removed too.

All owned source/SDK/archive/download/cache/build/translation/output/binary/venv/
TMPDIR/GOTMPDIR/public-check staging is removed. Final helper dry-run has no
decisions, retained>1GiB paths or debt; ignored state empty, checkout about419MiB.
Cleanup details and exact final free sample are in evidence/cleanup.json; free-space
changes on the whole volume are not attributed to this cleanup. No user state,
other checkout/image, protected parent file or historical result changed.
The final checksum manifest and source checks cover this new report only.
