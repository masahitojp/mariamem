# G2 native prepared repair

Human continuation after CI42330785223: repair the observed type/LONG_DATA gaps.
The Human explicitly chose to preserve upstream NULL fallback for BIT,GEOMETRY,
INT24,YEAR. Original G1/G2 oracles remain fixed;short handshake stays a visible
contract difference. No canonical guest/host integration or release.

Pinned upstream83e909fc sql_type.cc:8226 Type_handler::Item_param_set_param_func
sets NULL without advancing the packet. BIT,INT24,YEAR inherit that fallback;GEOMETRY explicitly performs the same
NULL operation in sql_type_geom.cc:680. The G1 exact-consumption check converted that upstream behavior
into1835. Preserve the native fallback without adding a decoder:only a non-NULL
parameter actually visiting one of these four handlers exempts the remaining
bytes from the added end check. This also preserves upstream cursor behavior in
mixed bindings;it is not a promise that those types decode their sent values.

Validate all fresh descriptors using the upstream type sanity predicate before
entering execute_loop,so rejection leaves pending LONG_DATA and conversion state
untouched. In both logged/nonlogged insertion paths,report native LONG_DATA type
mismatch as1210 before the existing generic malformed-packet remapping. Preserve
ordinary malformed-value1835,ordinary strict surplus rejection and D2.

Budget:one native guest build,one local regression execution and at most one
Linux CI for this repair;active2h,owned workspaces12GiB each,free floor12GiB.
The existing full G1 baseline and unchanged241 G2 observations are the runtime
regression checks. Short-handshake mismatch is expected to remain NOT_READY.
Until new guest/binding/runtime evidence exists,this is an unverified candidate.

The actual prepared source is SHA-pinned and compiled in a small C++ harness
with dependency stubs in [check_source.py](check_source.py). It checks descriptor
preflight(including an invalid second descriptor),the four NULL fallbacks,
bitmap-NULL surplus rejection,ordinary strict surplus and1210 in logged and
nonlogged insertion paths. This source-seam check is not an engine qualification.
The CI builder runs it immediately after source preparation and before the
unchanged build script disposes that source. The G1 patch-text guard now accounts
for added/removed lines when checking the replacement end condition;its runtime
oracles remain unchanged.

[Platform comparison](compare_results.py) retains every expected/actual/pass field
except the named mid-output drain byte count already observed to vary with
scheduling. It validates that quantity's integer schema and never changes the
contract readiness result. Missing/duplicate rows,another actual difference,
changed expectations/pass outcomes or a different guest cannot match.

## Native macOS result

Guest/checked host source_commit `76abfed4b5f920c79efd5fef33c848c21ac040c9`,
UNQUALIFIED guest SHA256
`242f5cfd446ac65dc3d7322ead668cd2ec5473193cf4bb58b69c7c5b3cfe6e87`.
Complete free/yield/entry worker bodies match the prior7103 guest byte for byte;
canonical P2 mapping and16/40/44 ABI offsets are checked in [binding](binding/identity.json).

At tooling6939d8625eaa8662d2ed40c9258a795ecd3c3e91,the unchanged G2 fixture
completes all241 observations:240 PASS,1 mismatch,0 missing. All10 intended
observations are repaired:four input types on fresh/reuse,wrong LONG type1210,
and pending LONG_DATA retained after a rejected descriptor. None of the original
230 PASS observations regresses. [Original result](evidence/macos-g2-result.json)
and [raw log](evidence/macos-g2-raw.txt) retain the failed short-handshake
expectation1045/28000 and actual1043/08S01. **NOT_READY** remains correct.
No original runtime oracle was edited or candidate output adopted as an oracle.

The strict regression baseline passes22 lifecycle,88 compatibility,38 limits,
all234 G1,2 existing/3 policy/4 repair controls and supporting checks(including22
canonical binding installer tests). A new [283-file source reference](evidence/macos-reference.json)
already includes the capture idle fixture correction and requires no additional
adjustment. [G2 build summary](evidence/macos-build-summary.json) pins a separate
binary and284 staged Go/assembly/data files:full7420→7421 inventory adds only
the original G2 test source. These are staged files,not a claim all283 compile on
both operating systems. Full original inventories remain in owned evidence.

Local results establish the finite repair;one Linux repeat is next and unobserved.
The expected remaining short-handshake mismatch still makes that CI NOT_READY.
Do not retry it to obtain green or silently loosen the expectation. A contract
decision or compatibility repair for that case remains separate,as do P1 public
wiring/ownership and P2 consumers/performance/adoption/release.

Reproduction uses Python3.14,Go1.26.10 and owned fixed-source workspaces:

```sh
python3 benchmarks/spikes/issue65-g2-repair/probe_baseline.py build --workspace "$BUILDER_WORK"
python3.14 benchmarks/spikes/issue65-g2-repair/probe.py local --workspace "$HOST_WORK"
# Native Linux x86_64,with the frozen Mac source/result comparisons:
python3 benchmarks/spikes/issue65-g2-repair/probe.py runtime --workspace "$HOST_WORK"
```

The first local measurement explicitly ran translate → complete binding review
→ baseline record-local → observe. Subsequent local and Linux replay use strict
reference comparison. The workflow is issue65-g2-repair.yml;submit exact candidate
SHA once,hand off its run URL/operation,and stop.

Local builder/runtime disposal is complete with [cleanup debt0](evidence/cleanup-summary.json).
SDK,archives,generated code,binaries and Go caches were deleted after evidence
collection. Author scratch/worktree is disposed after the final evidence commit;
retained refs and compact originals reconstruct the run. Existing user changes
in the shared checkout are outside these owned workspaces and remain preserved.
