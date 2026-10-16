# Memory Snapshot / shared Python host comparison

`campaign.py` requires two clean source checkouts and their Go1.26.8-built,
VCS-stamped hosts. It verifies commit **type**, clean HEAD and embedded build
identity before running any case. It never builds or publishes a release.

Each scale uses six alternating ordinary pairs and three separate resource pairs.
The public Python workflow prepares once, takes a Snapshot, checks isolated CRUD
and commit/rollback in two children (small/medium) or sixteen (100 MiB payload),
then closes every owner. It asserts guest version, exact seed bytes, child
independence, reaped hosts and empty owned scratch. Small/medium reuse the earlier
Python spike's two-table seed shape; the large extension is **not** the historical
one-table Go benchmark and its numbers must not be pooled with that benchmark.

Resource runs additionally sample the sum of live descendant-host RSS using
`ps`, then wait 25ms. The actual interval also includes `ps` execution time.
This is an observed sampled peak, not an exact high-water mark or Go
reachable heap measurement. It can miss short peaks. Their wall times retain
probe overhead and stay separate from ordinary latency. `RUSAGE_CHILDREN` maxrss
is also retained in native OS units; it is not a simultaneous-host total.

Run with `python campaign.py --baseline CLEAN_BASE --baseline-commit COMMIT
--baseline-host HOST --candidate CLEAN_CAND --candidate-commit COMMIT
--candidate-host HOST --output NEW_OUTPUT --scratch OWNED_SCRATCH`.
Use an isolated Python environment with pytest/PyMySQL and the same machine,
compiler and execution order. No trace/instrumentation environment is inherited.
