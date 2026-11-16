# Empty mixed-vector writes, response transport interaction

Question: does the known empty-iovec omission reduce the extra Go-pipe handoff,
and does it improve GetOrder and the complete suite beyond contemporaneous AA?
Prior c2cadc50: OS pipe wall -1.63%, CPU +1.68%; unadopted.
Prior 10665616: response Go pipe moved CPU syscall -> thread wakeups; empty
writes added8001 zero-byte host reads. No stable whole-suite speedup established.

Base experiment94123a47, product6558ee8f. Retain all SQL/assertions, trigger,
Close, capacity16, Go1.27.4 and P8 settings. Same binary, four arms:
OS/Go response pipe x skip-empty off/on. Request remains OS pipe.
Overlay uses the prior writeVec algorithm, including all-empty behavior; canonical
generator/product sources unchanged. This affects mixed vectors through all WASI
writeVec callers, not solely stdout. Do not attribute all wall change to stdout.
Arbitrary Writer empty-write side effects are not guaranteed equivalent.

Before measurement: identity pin, both skip-arm base tests, guest tests,
closed Go pipe/all-empty and mixed Go pipe boundary checks; real SQL semantic check
for four arms. Diagnostics: GetOrder4000 counters and one profile each/four arms.
Timing: query4000 and70-test suite each4 warmups plus40 processes:
OS-AA, OS-skipAB, Go-AA, Go-skipAB each5 pairs, shuffled block order with seed119,
alternating arm order. 88timing processes total. No adaptive repetitions/exclusions.
Record CPU/process/query/suite wall, full traces and logs, timeout180s.
Counter/profile runs separate. No cross-cohort subtraction or10% claim.
6GiB/8GiB free workspace;1200s limit. Correctness failure stops measurements.
Adoption remains separate; bounded experiment may conclude no gain/inconclusive.
