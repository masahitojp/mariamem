# Bounded controlled startup-order reproduction

Use the pinned MariaDB thread-pool method bodies from upstream commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e, retained in the preceding investigation. Compile a native C++ reduction; do not rebuild the guest or run randomized suite sampling.

Hypothesis: A and dependent completion task B are submitted while the first worker has not cleared creation_pending. The second submit is coalesced by pending. After clearing pending, that worker executes A, which waits for B without wait_begin. B can remain queued despite ample concurrency until maintenance rechecks backlog.

A/B are synthetic dependency tasks, not SQL or actual InnoDB I/O. Reproduction proves this mechanism is reachable in the copied policy, NOT that this order caused the original394ms trace. The synthetic missing wait_begin is an explicit prerequisite, not a newly discovered defect in buffer loading.

Keep exact maybe_wake_or_create_thread, add_thread, submit_task, worker_main, maintenance, set_concurrency, wait_begin/wait_end and throttling method bodies, apart from labeled counter hooks for return gates. Replace cache/list allocation, timer delivery, worker callbacks, task representation and get_task/idle teardown with small adapters. State adapters explicitly. Test four conditions, 3 runs each: pending/400ms manual maintenance; submission after worker starts; pending with wait_begin notification; pending/40ms manual maintenance. No added runs after outcomes. Verify queue/task identity, blocked_pending gate, active counts and completion/teardown. Deadline5s/process. No throughput claim from imposed delays.

End: report whether controlled-order stall is reproduced, distinguish policy mechanism from original guest cause, and recommend the smallest missing product observation. No optimization adoption, release or Issue140/143 reopening.
