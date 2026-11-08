# Source-only Issue129/130 integration preparation

Question: do exact settings/lifetime/evidence source slices coexist, and can the
settings observer consume a lifetime-derived receipt without changing the C2
producer identity or overwriting the original receipt?

Parents: lifetime846e181185d2ed0d311ab6a9850109a245f1e2fc,
settings3c47dfbcd3b44691e99cbcf2fe3b1b1d042b049c (includes4c10a1f8),
evidence c24cbb6ec2063088cf2edd08eb9358ecb0579f19 (includes ae9c243f).
Exact commits are merged as ancestors; historical records retain their original
source context. Current source-only checks do not rerun historical acceptance.

Scope/exit: read-only inventories and combined focused Python checks; public
source guard PASS, original fixture assertions unchanged, explicit receipt chain
and any conflict reported before a guest build. Inconclusive exit lists the
missing artifact/adaptation; no runtime or adoption claim. Remaining original
budget only: 2h active / 30min tooling total, with an estimated <=10min tooling
remaining on entry; no guest/runtime/staging/build/CI/benchmark execution here.
No new harness project or compile-only check is needed for this followup.

## Result and receipt chain

Source integration is ready for a later shared-artifact wave, with no guest
spend in this followup. Both exact commits merged without conflicts. The one
source-tool conflict was receipt selection: #129 previously hard-coded
`WORKSPACE/evidence/public-source.json`, whereas #130 emits a distinct derived
inventory. The minimal observer change adds `--source-receipt` and
`--base-source-receipt`; default C2 behavior remains supported. Derived mode
requires the original receipt hash/inventory, unchanged producer/guest/installer
identities and a real lifetime observer commit. Both receipts are rechecked after
later observation. Existing fixture assertions and duration/control oracles are
unchanged; #130's strict C2 preimages are unchanged.

Later observation must retain this chain, without executing it in this task:

1. **B, original C2 producer receipt**: original host source_commit
   `3602b186f309eb3af349df494470d28b8bb800c2`, guest and installer source_commit
   `be244a0bdb510a22417241c2aa2f76a9093aac1b`, guest SHA256
   `d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`, full
   original staged inventory. B is never replaced. The saved C2 receipt and the
   three strict host preimages agree at source level; no product directory or
   guest artifact was inspected/created here.
2. **L, lifetime derived receipt**: #130's installer, run later on a separate
   matching product copy, records SHA256(B), B's original inventory and producer
   fields unchanged, the lifetime observer commit/file hashes, and the full
   derived inventory with `runtime_executed=false`. Its observer commit identifies
   the integrated observer code; it is not substituted for B's producer SHA.
   Preserve B and L separately outside the inventoried product.
3. **S, settings observation**: pass `--source-receipt L --base-source-receipt B`
   to #129's observer with `--expected-host-source-commit` equal to B's producer
   (not L's observer/integration commit), and the unchanged exact guest SHA.
   `--workspace` must identify the separate copy whose `temp/public/product`
   inventory matches L. S records SHA256(L), SHA256(B), lifetime observer commit,
   settings observer commit/script hash, fixture hashes, platform, exact
   observations and positive/control binary hashes. Its fixed5000 control mutates
   only the lifetime-derived backend's restored-instance timeout expression;
   the new Python composition test verifies that every lifetime hook survives.
4. **Binary/acceptance ownership**: S compiles a fresh settings test binary from
   L's product plus the additive settings Go overlay; old C2 `public-binaries.json`
   remains evidence of B's binaries only. Do not reuse/relabel those binaries as
   L/S output. The settings binary includes the lifetime root fixtures, but the
   settings-only invocation does not execute them. Later root lifetime runs and
   control-package/standalone-host binaries need their own hashes/logs tied to
   the same L inventory and any applied settings overlay. Python fault-driver
   work and both-OS acceptance remain unexecuted.

If #127/#131 changes any of the three pinned core preimages, C2 factory or
lifetime completion/binding contract, the current lifetime installer must refuse
it. Required adaptation is an explicit reviewed new preimage/factory/runtime
binding and a new producer/derived receipt chain; never edit B, weaken the C2
preimage checks or change a guest/producer field merely to pass the observer.

## Checks and limits

- Combined settings/lifetime Python tests:13 PASS, including three new
  source-composition/receipt-chain tests; no Go/build/runtime mode invoked.
- Existing evidence-normalization preservation tests:5 PASS.
- Full `scripts/check_public.py`:PASS on the integrated tree; the six former
  blockers are handled by the exact ae9 normalization ancestry, not by altering
  the guard or removing raw provenance.
- Touched Python compile checks, source identities, read-only fixture hashes,
  original assertion preservation, and diff/status checks pass; compact hashes
  and results are in `results.json` next to this report.
- No compile-only check, staging installer, guest/runtime build, native run,
  benchmark or CI was executed. No Issue65/project-status/134/main/adoption/
  release changes were made. Both #130 and #132 remain incomplete.

Owned Python bytecode and the guard's generated report are removed after checks;
pre-existing build files/shared compiler cache remain untouched. This followup
uses the remaining original budget, approximately several minutes active/tooling
(estimate), with cumulative tooling still below30min; no expansion is authorized.
