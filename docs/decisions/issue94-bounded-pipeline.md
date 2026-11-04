# Issue #94 bounded input pipelining

Human decision, 2026-11-05 JST: adopt per-connection bounded read-ahead for
production implementation, with a pending-input limit of 1,048,581 bytes and
instance abort on overflow. Preserve serial execution/responses and the existing
disconnect, deadline, stop and independent-root guarantees. This authorizes the
implementation and verification work, not release or publication.

The [source-pinned spike](https://github.com/masahitojp/mariamem/blob/253b03d269859cfb2d713f2cae18ea5b22f499c2/docs/reviews/issue94-bounded-pipeline/README.md)
uses runtime source_commit `31daa96905730e63242f01fca75f7bb36bb14c88` and stable
base `82f96435777079f38d01f5f2012eda3cb2329cda`, with an experiment-only Issue #93
overlay. It reports 28 default-pipelining Prisma Client/Live passes, 5 cooperative
real TCP ordering/failure cases and 20 selected wire/timeout/multiclient checks
on Darwin arm64. Those are historical spike results, not acceptance relabelled
onto a later production candidate or evidence of Ubuntu/race execution.

The strongest alternative was keeping pipelining disabled or waiting for buffer
space. The selected policy accepts a finite profile: a legitimate larger burst
may abort the instance. Stopping reads at capacity would hide a following EOF;
continuing with one overflow-detection byte keeps input memory bounded and
preserves disconnect observation. The bound is pending input/capacity, not a
measured whole-process memory guarantee. No performance campaign is authorized.

Production extraction removes experiment observation code, retains permanent
buffer/order/admission regressions, adds real TCP controls to the existing wire
acceptance owner, documents the limit and reconciles the active wire inventory.
Existing daily/Release owners provide source/race/platform acceptance; no new
Node CI job or automatic heavy campaign is added. Commands, capabilities, guest,
generated source, SDK signatures and version metadata remain unchanged.

Issue #94 owns completion. Issue #93 is an independent prerequisite for five normal
Prisma zero-parameter paths; Issue #95 owns the alias. Their integration/evidence
must remain explicit. The experiment branch is not merged wholesale.
