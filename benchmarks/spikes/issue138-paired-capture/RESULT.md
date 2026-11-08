# #138 result: native PASS; legacy stopped by free-space guard

**Combined acceptance is incomplete.** Native fresh generation, exact new binding
review, original79-case suite and added drain/capture/restore/isolation scenario
passed. The matched legacy producer stopped during SDK setup at the12GiB free
floor; no legacy guest artifact, translation/host or runtime suite exists.
Positive spare-archive branch coverage is also missing. The final existing
prepared-helper compatibility check fails on its unprofiled generic fixture;
137 records that additional source integration gap. No retry, budget
extension, release/public acceptance or automatic issue closure follows.

Recommendation: after capacity is restored, propose a legacy-only continuation
at the pinned source with these native results as the matched experiment
counterpart, provided shared inputs stay unchanged. Do not rebuild12.3.3 or a
throwaway observer baseline. Total update burden remains INCONCLUSIVE; the
[137 maintenance map](../issue137-prepared-profile/RESULT.md) explains the real
removed source obligation and added bookkeeping.

## Artifact and scope tuple

| Item | Actual result |
| --- | --- |
| Target | MariaDB13.0.2 commit620a4b5624222048fece7fe1789978ae0675cae2 / tag object308a50778fb4916ddde0d2923feea3d11dcc92c8; git_identity verified |
| Native producer/host libraries | 4b3954a0faf42986459bc1ee68727be16d67bcbb |
| Native guest | 889f21b796c4daaf5244486cce84bfe6a82c758437af400e831d0ed10f0a067e /21237121bytes |
| Native linked WASM | ba457b19db7d41ea372e72685817bb872dcf7044e1a95512e41bc641dba903e3 |
| Native host test binary | b9949bb5b81901ca27d35b0e8f402c243f4818377b70c9520a3ff7292a05b0e8 |
| Legacy-full producer source | 32c799031f619164d3730b61a0bc9d7ae48dcd9b; SDK setup interrupted, no artifact digest |
| Environment | Fresh Linux arm64 canonical development producer, locked LLVM23/SDK/Binaryen; macOS arm64 Go1.26.10 native host |

This tuple differs from e650/b767's earlier13.0.2 trial and fd7/873c's12.3.3
public preflight. None of their acceptance receipts is transferred. Normal
factory/public C3, actual public faults, installed Python and bothOS are outside
this isolated test. All results stay UNQUALIFIED for release/adoption.

Native freshness is independently evidenced by empty work, absent SDK/source/
unpack in preflight and one successful canonical development invocation plus
producer-result; verify_guest alone was not treated as a freshness gate. The
new exact freeFn151/yieldFn129/entryFn520 bodies, explicit function/address maps,
no-op table target proof, TLS489 and ABI16/40/44 are saved in
[evidence/native/runtime/reviewed-binding](evidence/native/runtime/reviewed-binding/).
The real installer rejects a corrupted expected complete-body digest and ABI
map_size44→48; these controls did not compile an altered runtime. They are not
claims of fuzzing every generated instruction. Original binding inputs and
expectations remain unchanged.

## Actual finite execution

- **Original native79/79 top-level cases PASS, FAIL0/SKIP0**, exact name-set
  equality to the original reference. Raw whole-suite output was executed;
  separate analyzer views are not substituted for the suite.
- Original22 lifecycle cases are an explicitly verified subset. Native-completion
  hold, reader-relay hold and idle-pool drain controls are among the retained
  original cases and passed on the new guest/binding.
- Four original analyzer arrays all ready: compat88, limits38, G1234, G2241.
  **These total601 named observations, not701.** Historical127/128 prose and the
  task inherited701 although its four enumerated families sum601. The arrays
  were counted directly; no additional100 are evidenced or manufactured.
  [Audit](evidence/observation-count-audit.json). Old reports/oracles remain
  unchanged; this is an aggregate-prose discrepancy, not an expectation edit.
- Added dead-root sentinel PASS: the existing adapter returns nil for done, and
  the added drain wrapper rejects it. This ran before any other runtime test.
- Added archive/drain/capture/restore/isolation PASS,1.40s test-reported duration.
  It is separate from the original79 and the four analyzer arrays.
- **Legacy smoke/P1six/P2fifteen and common archive scenario: NOT RUN.** Planned
  common inputs and unequal route-specific programs are documented, not a
  completed same-condition paired runtime comparison.

## Close → drain → capture: measured observations

[Raw additional scenario](evidence/native/runtime/target-checkpoint.txt):

| Observation | Actual |
| --- | --- |
| Archive workload |4MiB log, archiveON/OFF,256×65536-byte committed rows; LSN36889→16947491 (>2log), checkpoint16956473;256rows/16777216bytes |
| Immediately after db.Close | slot0/generation1 **IDLE**, command778, started1/joined0, rollback_reports0, host1/leases1, no poison/cause |
| After bounded existing WaitDisconnected plus checks | sessions[], started1/joined1, rollback_reports1, host0/leases0, healthy live root |
| Single capture | Full original fenced→stop/receipt→guestjoin→freeze→memoryrelease→hostjoin→rootowned ordering and equal cleanup/join counts PASS |
| Restore/isolation |256rows/16777216bytes, idsum32640 and all payloads equal expected64KiB x; insert private row in one child leaves sibling at256; cleanup succeeds |

The extra test preserves the original count/byte oracles and adds content
predicates/id-sum and child isolation; it is not a per-row cryptographic image
comparison. The real observed IDLE-with-live-ownership state confirms the source
observation gap on this tuple. It supports the proposed race explanation but
**does not retrospectively prove the exact cause of the old b767 busy failure**:
profile/hook/observer changed together as authorized. Original1cFAIL remains.

No sleep/busy retry/gate weakening. Original open-idle capture helper unchanged.
Close/drain timestamps and state/identity are finite; rejection logging is
implemented before ordinary cleanup but not exercised by this successful extra
capture. No second capture was attempted after a rejection. Full root join stays
post-fence in the original capture owner; it was not substituted for session
drain before capture.

## Branch observation and remaining semantic evidence

The shared exact observational patch adds once-per-engine markers without
changing wait/LSN/control-flow algorithms. Actual extra-native output contains
`ISSUE138_BRANCH timed_wait`; it does **not** contain the positive
`create_spare_archive!=0`/spare_archive marker. The timed_wait marker can arise
in normal background/startup operation; we do not assign it to archiveON or
claim it proves the spare-archive transition. Checkpoint advancement is not
branch coverage. [Branch evidence](evidence/native/branch-observations.json).
A finite positive branch stimulus remains to be designed/verified with the
necessary candidate execution opportunity, not an automatic retry campaign.

## Stop, cost, disk and next bounded work

Native measured command/wait durations (not active work or benchmark):

| Stage | Seconds |
| --- | --- |
| Fresh producer including acquisition/preparation/build/postopt |1514.19 |
| Translation/source adaptation |124.60 |
| Host installation/compilation |247.68 |
| Native sentinel + original suite + extra scenario command |51.15 |

Binding review/negative-stage durations and exact commands are in the adjacent
stage JSON records. No compiler/link fixes or new algorithm repairs were needed.
Legacy attempt ran~269s inside the guard before interruption during SDK setup;
no compiler timing is available. Its LLVM archive had to be reacquired after an
inactive owned archive was removed to preserve native host headroom. Source/
SDK/cache acquisition conditions and host test programs differ; no speed ranking
or native-specific attribution of these setup/storage costs is valid.

Sampled native guest peak7.457GiB/minimum free14.613GiB; native host conservative
whole-checkout peak7.899GiB/minimum free13.033GiB; native runtime minimum14.565GiB.
Host TMPDIR/GOTMPDIR and Go caches were all inside owned staging, avoiding the old
Go temporary-directory gap. Guest guards counted all owned mounted source/SDK/
download/work/output/temp paths. Host guards conservatively include the whole
assigned checkout. Inactive native producer/source, SDK, caches and duplicate
translation inputs were removed after use, preserving their compact evidence.

**The outer legacy guard stopped at free11.98GiB**, owned4.04GiB, exit2; ceiling
12GiB/floor12GiB were unchanged. Its inner guard recorded an interrupted child
and a different sampled free minimum (~13.05GiB). We preserve both; the inner
number cannot replace or negate the actual outer breach. The cause of changing
whole-filesystem availability outside the counted tree is not established.
The owned container is confirmed absent; no other job/image/workspace was killed
or deleted. [Legacy stop and raw log](evidence/legacy/).

Accounting: prior run conservatively charged15min active/4min tooling. Resumed
wall starts12:43:10Z; conservatively charging the entire resumed wall through
handoff as active (including waits) keeps the total below the120min active
ceiling. Resumed measurement/run-tool authoring is estimated12–15min, cumulative
16–19min including prior tooling, within20min; estimates are not stopwatch
measurements. Two guest producer invocations were attempted (native successful,
legacy SDK-interrupted); one translation/host pipeline and one native finite
suite command completed. CI0/benchmark0/public expansion0. No retry after breach.

Remaining concrete work: restore/audit free-space headroom without raising
ceilings or deleting others; obtain a bounded legacy-only continuation at32c799
with identical shared pins, one clean guest<=60min, one translation/host<=30min,
original smoke/P1/P2 plus common scenario<=15min. Active30–45min/tooling<=5min
and wall<=2h15 are estimates/proposal, **not new authorization**; SDK acquisition
and available space remain unknown. Native7.457GiB sampled guest ownership is
useful capacity evidence, not a guarantee. Design the missing positive branch
stimulus before another relevant execution opportunity. Do not rebuild merely
to repair an observer. #128 final candidate-impact review and public132/134/C3
remain separate and pending.

Final source-helper verification: `tests/test_prepared_source_patch.py -x`
FAIL1 at the first old generic fixture (missing explicit prepared profile).
The new real-target full-file/profile controls passed before building; this
existing compatibility boundary was missed until final verification. No repair
or expectation change followed the resource stop. The source integration gap
requires5–15min focused work in addition to the proposed legacy continuation;
no overall green/helper-suite PASS is claimed.
