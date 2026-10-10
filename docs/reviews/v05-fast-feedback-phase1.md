# v0.5.x Fast Feedback — Phase 1

## Bounded implementation plan

Human approved assessment candidates 1/2; candidate 3 is design only.
Baseline main: `b1666e4a6f4b3b77269b294de0fe225031ad12ce`.
Released v0.4.6 source: `b56be17206b6beef18f55c8ea39b254638da8590`.
Branch: `experiment/v05-fast-feedback-phase1`.
The [approved assessment](v05-fast-feedback-assessment.md) is retained as input.

1. Add a small shared opt-in subprocess observation helper to the existing
   verification, guest-build, regeneration and host-wheel build call sites.
   Keep command order, streams, exit/timeout behavior and qualification gates.
   JSONL is diagnostic data, never release qualification evidence.
2. Use an explicit active experiment workspace to assign task-local Go cache
   paths through existing callers. Reject conflicting/other-task paths. Default
   execution without that opt-in stays unchanged. Go owns cache invalidation.
3. Focused tests cover process success/failure/timeout/signals, observer-off
   equivalence, resource units/unavailability, caller environment consistency,
   current source oracles and unchanged release rejection gates.
4. Sequential bounded measurements compare uninstrumented/instrumented cold and
   warm host builds; a small compiled fixture proves host/shim/toolchain cache
   invalidation without altering production generated files. Preserve hashes,
   actual compiler, flags, trials and uncertainty. Build the wheel through its
   existing path; do not rerun platform runtime acceptance for tooling changes.
5. Describe the dev-only guest lifecycle and promotion/contamination controls in
   [design review](v05-dev-guest-build-design.md). No dev flag or guard changes.
6. Commit/push reports and implementation; remove task caches/builds/worktree.
   Main, v0.4.6 tag/assets, runtime/converter/guest inputs and CI stay unchanged.

Results and the final Human Review packet will be appended after verification.
