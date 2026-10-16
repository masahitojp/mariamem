# Released v0.5.1: bounded Go 100 MiB Fresh investigation

Question: where does the observed extra time go, and is block-storage/GC/guest
SQL CPU a plausible dominant explanation? Investigation only; no runtime fix,
generated-source edit, wider product matrix or release action.

1. Reuse all four historical pairs, retaining the first adverse observation.
   Compare same-time pairs and setup/count/mutation CPU versus wall, separately
   from ratios of unpaired medians. Neither aggregation erases an observation.
2. Compare typed released v0.5.0/v0.5.1 on macOS arm64, pinned Go1.26.8,
   CGO_ENABLED=0, four serial Fresh DBs, 100 MiB payload, eight tables and the
   unchanged app-connections SQL/transaction/cleanup oracle.
3. One pair of unmodified calibration binaries, then two alternating pairs each
   of profiling-off/on observer binaries: **10 executions**, no parallel campaigns.
   Each pair runs the same binary with profiling enabled or disabled; profile
   timings are diagnostic, never pooled with ordinary timings. Calibration
   exposes differences from adding the unused profile flag/linkage.
4. The only build overlay is the benchmark main: runtime/pprof import, optional
   flag, Start/StopCPUProfile and result marker. Runtime/guest inputs remain
   clean. Exact overlay source/map hashes accompany stamped binary identities.
5. Preserve raw profiles/checksums and pprof text; assess storage, allocation/GC,
   guest SQL and CPU-versus-wall bounds. Sampling cannot by itself prove a
   historical one-off cause or rule out transitive effects.

Run through experiment_workspace with 3600s timeout, 8 GiB owned disk budget and
20 GiB free reserve. Stop on oracle/identity failure or limits; a stopped run is
incomplete. Per workload timeout180s; process RSS above8 GiB stops after a cell
(sampled safeguard, not a hard RAM quota). Remaining uncertainty is reported
with a concrete next decision; elapsed budget is not completion. Ubuntu is not
measured. Finish with evidence/Human Review, commit/push and disposable cleanup.
