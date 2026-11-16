# Actual guest pool-order diagnostic

Frozen product:6558ee8, guest77b2ab49; parent evidence a1497c4f. Compile overlay on exact generated functions, no C guest rebuild or product patch.

Inspect function bodies/field offsets before build. Instrument enqueue/dequeue inside pool mutex, pending-clear without reading unlocked shared fields, add_thread's actual reject branches, worker task entry/exit, wait_begin/end successful accounting, maintenance entry, page read waits and worker futex calls with TLS pool identity. State snapshots only at existing mutex-held sites. Guest thread-pool pointer plus pool address is the identity; guest memory addresses alone may be reused.

Fixed8 P8 suite processes, alternating four natural(observer only) and four controlled(first worker per instance/pool delayed20ms immediately before pending clear). This delay is outside pool mutex, bounded, and logged; never call maintenance manually or change resource limits. It changes schedule and is not a natural reproduction/performance benchmark. Exact original SQL/SUM/audit/UPDATE OF status/revenue preaggregation/sync Close. No extra repeats after non-reproduction.120s/process,300s campaign. Build guard6GiB/minfree8GiB; only pre/post disk checks during runs.

Pass: 70 test cases/process and valid pointer/bounds. Analyze same pool/task enqueue→reject_pending→clear→dequeue/execute, worker waits with no wait_begin accounting and long queued tasks (>100ms). Link only when identity/time matches. A forced-start result is conditional mechanism evidence, not proof about previous uninstrumented394ms. If absent, record bounds and stop. No product adoption, no unbounded sampling, no Issue140/143 reopening.
