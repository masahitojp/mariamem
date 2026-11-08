# Issue128 — bounded real target comparison

## Authorized plan, recorded before preparation/build (2026-11-08)

Question: on the same MariaDB13.0.2 engine/prepared UCA base, do native's total
update investigation, patching, generation/binding and semantic verification
costs improve on legacy? Human authorized this follow-up in
[the review](https://github.com/masahitojp/mariamem/issues/65#issuecomment-6717727942).
Initial source-only evidence at `dbf269e38d64e93862bcd5f736876ae5745b7a8b`
remains immutable. This report owns new outcomes, including failures.

Inputs: base127 `46915e50c12795da4787c9d1ee0b73e6c6a829dc`; native guest origin
`8c8b5f1c09765c9fb51c2b640ed2fc32d759fbe3`, older native
`be244a0bdb510a22417241c2aa2f76a9093aac1b`, legacy source
`47121e1be0b399ba4e2270ce3e25c411ade0e2eb`. Target source_commit
`620a4b5624222048fece7fe1789978ae0675cae2`, annotated tag_object_sha
`308a50778fb4916ddde0d2923feea3d11dcc92c8`. Recheck Git identity before builds.

Workload: full pinned dependency acquisition and exact full pre/postimage
preparation; at most one fresh clean guest build per variant, sequentially;
regenerated Go and exact new worker/TLS/layout binding review; finite affected
common checks and native22 lifecycle/88compat/38limits/G1234/G2241 where runnable.
Preserve original semantics and expectations, label unavailable fixtures, and
do not turn isolated evidence into public C3/platform/adoption acceptance.
Published legacy's missing prepared UCA is shared baseline setup, not a native
benefit. Use identical locked compiler/sysroots/Binaryen/converter/platform.

Budget: **2h active including30min tooling;4h30min total wall;CI0**. At most2
clean guest builds, each60min timeout, at most2 translation/host builds each30min,
finite suites each30min; no benchmarks or consumer expansion. Stop at the first
unresolved shared/semantic failure or budget breach, preserve evidence, clean
owned scratch and report the missing evidence and bounded next cost. Repair
only the already understood three shared adaptations within this budget.

Disk: **12GiB total owned ceiling;12GiB minimum free**, guarding preparation
and run. Initial host free space approximately20GiB, with no observed active
guest/compiler build. Count all owned host/container SDK, downloads, caches,
work, logs and output under `build/issue128-real/temp`; do not delete shared
images/cache or any other checkout. Use a fresh SDK/work tree per clean build,
explicit fresh-producer assertions and raw builder status; incremental success
cannot be called clean. Existing image is an environment, not a warmed SDK input.

Exit: improved/worse/inconclusive total update burden, with actual sources and
artifact digests, reproduction commands, manual/tooling estimates and command
wait durations separated. Inconclusive or unfavorable evidence must not trigger
automatic productization; recommend internal-contact reduction/placement
reconsideration for131 if no convincing benefit. Final128 still needs comparison
against final adoption-candidate differences. No main integration/release change.
