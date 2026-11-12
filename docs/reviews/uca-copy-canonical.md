# UCA private-copy canonical migration — installed checkpoint

**Human adoption is approved; main integration is not complete.** This minimum
candidate starts at main500020e7dc6d702ef059f0e73a4bab738103b774, retaining that
main's timer implementation and current API. [Decision](../decisions/uca-default-private-copy.md).
No measurement history, raw CI response or observer implementation is merged.

## Current changes and evidence

The exact216,045-byte accepted experimental patch from source
f43257225e1fd65c58ea8f5d7b220c3a509c203b is appended to guest/source.patch.
The old canonical prefix is unchanged. This includes the private-copy helper,
prepared numeric tables and allocation-error propagation/partial-state reset.
The retained word “Experimental” in its comment is historical; preserving the
complete source bytes makes this migration directly comparable.

Local patch application to SHA-verified pinned MariaDB ctype-uca.c reproduces:

| Prepared source | SHA256 |
| --- | --- |
| strings/ctype-uca.c |7f8708a3f5be2f3b05df572b9f6a2f003b3cf72bd5588e20be72f64f0ccf69c8|
| strings/mariamem_uca_copy_prepared.h |e98564588cdff8076e747b0be6780a6e23c981a7769322db52ba26738cc5f5e7|

These match the accepted prototype exactly. Preparation now inventories the new
header when present. The current12.3.3 selected profile pins the combined patch;
13.0.2 remains frozen. Stage1 made no speculative installed-runtime change. The subsequent
[installed checkpoint](uca-copy-installation/README.md) records the actual
generated source and remaining verification.

Local focused checks:119 tests and20 subtests PASS (migration, selected-input
resolver/context, Development workflow contract, timer and previous build guards).
The public-source and diff checks pass. No local guest or Go runtime rebuild was
run for this source-only stage.

Source controls reject changed base/delta bytes, stale selected-profile pins,
an experimental overlay, wrong guest/linked/source identity, and absent/changed
prepared source evidence. These run before Go compilation through SOURCE_TESTS.
They guard migration identity, not SQL behavior or full failure correctness.

## Execution sequence and bounded cost

1. Submit existing manual uca-canonical.yml on this branch: one isolated Linux
   arm64 C build, upper bound100min, exactly one build, no natural sampling.
   Existing UNQUALIFIED output must have no experimental overlay and reproduce
   accepted guest332e0108443d68c20362247bfe96592da99beb1729a3a3ba107cbc0a5dea4a22
   and linked432200d991a53f56dcbb3ddd5e2ef49a8d3099b9702dc48d3c9ddd26bfc43b6c.
   A mismatch stops migration rather than silently rebinding.
2. After that receipt, install normal generated-Go sources, exact worker/CRC
   bindings and fixture relocations, input/provenance metadata and permanent UCA
   correctness controls. Validate their boundary against the accepted experiment.
3. Restore the workflow's full candidate gate: two independent canonical C
   builds; both-platform independent Go regeneration; UCA payload/corruption/
   profiling/fallback/isolation; existing lexer/CRC/worker/timer protection;
   native SQL, two children, reSnapshot and cleanup. Existing experimental CI is
   not relabeled. No new performance campaign is an adoption prerequisite.
4. Submit the minimal product PR and merge through normal required checks and
   strict-base protection. Only then mark main integration complete.

Stage1 passed at c4c60edaf7c6c9bd51023f352be696033e17438d in
[CI43185761193](https://github.com/masahitojp/mariamem/actions/runs/43185761193).
[Compact verified receipt](uca-copy-stage1-43185761193.json) retains the job,
artifact ZIP hashes and individual-file checksums; no raw logs/REST are added.
The normal generated runtime and exact worker/CRC fixtures are now installed.
Local actual-guest correctness and clean-source host attribution pass at
cd33ad5d; license-evidence follow-up changes only records/mirrors. The full
canonical workflow is restored. Both-platform acceptance and merge
remain pending; no old receipt is relabeled as this installed source.
No Release CI, tag or publication is requested. The staged workflow does not
run automatically on push; after submission CI owns execution and Codex hands off.

## Residual wait investigation stays separate

[#156](https://github.com/masahitojp/mariamem/issues/156) records the finite natural
observation:0/504 PREPAREs at least100ms, with creation_pending refusals but no
long stall. The diagnostic emits about100,000 events per process, so schedule
perturbation is plausible but unproven. The later follow-up should distinguish
observer effects from the pending-clear/task-wait interleaving, with a controlled
case rather than repeating until a tail appears. Integration does not claim that
the original unfavorable observer-off P8 result disappeared.

## Subsequent canonical acceptance and Development correction

Both-platform canonical verification passed at 6da771df in
[CI43190662084](uca-copy-ci-43190662084/README.md).
The compact receipt records exact source/artifacts and the separate Development
failure caused by an outdated init-flag address in the image test. The follow-up
relocates that test fixture and strengthens its preconditions; product runtime
bytes are unchanged. Protected merge remains pending new Development checks.
