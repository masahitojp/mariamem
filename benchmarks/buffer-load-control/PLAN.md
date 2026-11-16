# Startup buffer loading value control

Product baseline 6558ee8fb2211313a8aa0ea6070ac5256767811a; unchanged comparison-variance harness 1977fff480c2f976bc23f4d2e1b8ff8db36ad128 except control validation.
Question: does disabling startup buffer pool preload improve complete lifecycle, including deferred reads? No pending causal tracing and no product adoption.
First validate that per-instance /etc/my.cnf reaches embedded startup: query effective global setting on fresh and restored instances, run matched semantics. Abort measurement if ineffective; do not relabel a post-start abort as OFF.
If valid: one identical binary ON/OFF, fixed 10 ABBA/BAAB blocks at P8, 2 warmups (42 processes, 2940 case bodies). Same 70 cases, SUM/audit, preaggregated revenue, synchronous Close, MaxForks16. Entire elapsed includes initialization, setup/sample/tests/final cleanup. Report means, medians, paired block ratios, adjacent within-arm A/A, all values and >1.2x arm median tails. No exclusions/adaptive reruns. CPU/RSS and phase spans retained. No recursive disk scans during measured processes. P1 and cross-engine comparison deferred until value signal at target P8.
Go1.27.4 darwin arm64, GOMAXPROCS8 GOGC100 CGO0. Budget6GiB, free floor8GiB, build15min, campaign10min. Existing root changes untouched. Configuration adapter is experiment-only, not canonical guest provenance or merge-ready implementation.

Validation correction before timing: srv0start.cc:1968–1970 forces load_at_startup=FALSE for create_new_db. Fresh must therefore report0 in both arms; restored reader must report the selected value. Initial ON validation failed only because its fresh expectation was1. No measurement had run.
