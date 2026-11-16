# INSERT wait owner follow-up

Question: separate page-read work from delayed completion-task execution for the saved 394 ms guest wait.

Frozen source: dc2dbf37ff5b70104d3c434cdfda612a0654ae9b (product 6558ee8, previous harness/evidence only). Guest SHA77b2ab49... verified against CI artifact14103568702. Exact function-map SHA ad4c0607... binds to retained buffer-zero-candidate binding-review, not the older map.

First map saved stacks and inspect pinned MariaDB 83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e thread-pool source. Then one overlay build, fixed eight P8 suites, no repeats after non-reproduction. Original SQL/trigger/close settings unchanged. No comparison baseline, performance claim, parameter change or guest rebuild.

Observer: runtime trace labels include module memory base, futex address/expected/timeout/result, page pointer at read_wait and read_complete, task/pool pointer at submit/execute, maintenance/add_thread. Region begin/end identifies sample caller. Pointer identities are process-local; same address across modules is distinct. Notification is not automatically lock ownership. Read_callback argument is an aiocb pointer, task_execute argument is a task pointer; no equation of these without source/layout proof.

End: bind >100 ms wait to same-module/address notification and, if possible, same-task submit/execute; otherwise record missing identity and NOT_REPRODUCED. Do not infer queue delay merely from 400ms resemblance or new worker creation. Fixed eight cases may not reproduce. No recursive disk monitor during execution; pre/post checks only. 150s/process, 300s campaign. Preserve all traces, selected events and scripts with hashes; clean owned builds/worktree. Record outcome in #182, no automatic reopening #140/#143 or product adoption.
