# Issue156: C candidate and ordinary-workload comparison

Question: does the localized dictionary eviction wait notification preserve normal
SQL/lifecycle behavior and improve the complete workload or its PREPARE tail?
Do not confuse the27-case controlled success with natural-tail causal closure.

Human authorized this continuation after the controlled report at b18aad04.
No product adoption, canonical guest change, Qualification or release follows.

## One experimental change

`guest/experimental.patch` adds an explicit tpool header and changes only
`dict_sys_t::evict_table_LRU`'s lock acquisition: try-lock first; on contention,
notify begin, call the original private lock_wait, notify end. Unlock and the
entire eviction body remain unchanged. `input.json` pins upstream preimage,
complete postimage, patch hash and exact fragments. Canonical patch unchanged.
Purge shared-lock waits are excluded. The previous caller audit and non-nesting
precondition still apply; this is not a generic dict_sys_t::lock wrapper.

## Stage1: one build / source-only translation

- Exact committed experiment branch, product baseline8df45792a927e440972266ee799d6f7223713e14.
- Reuse existing single-build `development-unqualified-v1` route on Linux arm64,
  pinned Ubuntu image/toolchain. One C build, job timeout100min.
- Verify candidate source identity and actual prepared dict0dict.cc postimage
  in guest.json; never substitute the baseline guest if build fails.
- Source-only translation on Ubuntu x86_64, timeout45min. Inspect existing
  thread/CRC binding anchors, retain full source as CI artifact only.
- Source-only code is reused from tests/uca_copy_translate.py at f4325722,
  changing only its descriptive docstring; no relaxed guard/normalization.
- Translation COMPLETE or green CI **does not authorize execution**. Preserve
  full function/data identity and review any binding change before installation.
  No new general binding framework or silent identity override.
- Submit once, return run URL/source/operation, and hand off. No polling.

Local preparation uses2GiB/free6GiB. Source checks apply/reverse the patch against
the pinned primary file and reject six invalid synthetic receipt variants.
No local C/Go runtime build is needed for this preparation step. CI owns build
and translation. A failed build stops this submission; diagnose separately.

## Stage2: fixed local comparison after artifact/binding checks

Ordinary workload: the existing shop70 Go Pipe runner from source
`d24087eedd21c6384c231fb119c8e98da7b370aa`, with identical injection in both arms.
Baseline is the committed product8df45792 guest; candidate is Stage1's exact
experimental guest installed into the **same host source** using existing dev
provenance. Go1.26.10, same Mac, GOMAXPROCS8/GOGC100,16MiB/read1, cap=P+1.
No pgmem update, buffer-pool tuning or other product change in this comparison.

- P4/P8,50 shared-child reads and20 isolated-child writes;21 forks/sample loads.
- Observer-off primary: one warmup per arm/P, then five paired suites per P.
  Alternate arm order and P order. Retain every suite; no tail filtering/rerolls.
- Secondary SQL phase timing: three pairs at P8 using existing injection from
  `e556c36570e1be023f8a9c8243381c6605079592`, with statement timing enabled but
  stack capture disabled. Keep separate from observer-off results because even
  lightweight instrumentation can change scheduling. Three PREPARE calls/load,
 40 orders,100 items,100 stock updates, one commit; verify counts.
- Report paired total wall/process CPU/RSS, Fork/sample/cleanup distributions;
  secondary PREPARE per-call p50/p95/max and >100ms counts by arm. Do not average
  away tails. Keep secondary and observer-off denominators separate.
- Existing SQL row/count assertions, subsequent queries, clean child isolation,
  all mappings0 and empty owned temp are mandatory. Failed correctness or cleanup
  invalidates that sample and stops; do not silently continue with fewer cases.
- Budget: up to four Go runner builds (two modes × two arms), fixed30 suites
  (4 warmup +20 primary +6 secondary),2h active cap and8GiB/
  free6GiB. No C rebuild or full platform campaign in Stage2.

An improvement is a measured paired result, not an adoption threshold invented
afterward. Report inconclusive/no-tail/no-benefit honestly. A clean0/0 tail count
cannot establish removal of the original latency. Any harmful SQL/lifecycle
change stops the candidate. Original pending/refusal/read-generation/recovery
causality remains unproven unless separately observed; no additional sampling
is authorized by a quiet result.

## Retention / next decision

Retain compact report/JSON or CSV, exact source/artifact digests and reproduction
commands. Full guest/generated artifacts and raw logs stay in CI artifact storage,
not main. Delete local downloads/build/cache/worktrees after preserving knowledge.
At Stage2 exit recommend continue/adopt/reject with limitations; Human decides
product direction. #140/#156 remain open during this experiment.
