# v0.4.1 generated-Go distribution cleanup

Isolated implementation experiment from `v0.4.0`, SHA
`39537e9bb2fbbc28315e1ff672960ad734a9e399`.

The only production-source removal is the unreferenced `internal/builtinruntime`
package and its image-only build script/verification. The canonical guest,
generated source, handwritten runtime, public API and legacy fallback are not
changed. Local macOS distribution acceptance and same-boundary size measurement
are complete as of 2026-10-04. This remains an isolated experiment, not a merge
or release approval.

## Result and exact inputs

**PASS LOCAL DISTRIBUTION VALIDATION.** Removing the unused encoded runtime
images reduces the complete Go module zip by **73.0%**, with installed-wheel and
external Go consumer lifecycle/isolation acceptance preserved on this platform.

- Before: `39537e9bb2fbbc28315e1ff672960ad734a9e399` (released v0.4.0).
- After: `01d39dffedbb3f2af00395a6cc7b1a627cdd4c8e`.
- Apple M1 / macOS27.0.1 arm64 / Go1.26.8 / Python3.14.8.
- [Checked values, command receipts, log hashes and attempt history](v041-distribution-cleanup.json).

## Same-boundary module size

Both zips use exact `git archive` extractions and
`golang.org/x/mod/zip v0.4.2` `CreateFromDir`, the same module prefix/version and
sorted filesystem traversal. This includes the complete eligible source tree,
docs and tests; it differs from earlier reduced consumer-probe fixtures.
Sizes below are bytes divided by 2^20, not filesystem allocated space.

| Boundary | Before | After |
| --- | ---: | ---: |
| Complete module zip | 115.22 MiB | 31.13 MiB |
| Uncompressed zip members | 328.15 MiB | 216.28 MiB |
| Encoded-image package compressed payload | 84.09 MiB | 0 |
| Zip member count | 583 | 578 |

The zip saving is 88,172,989 bytes / 84.09 MiB / 72.98%. All 65 common
`internal/generatedgo/` members are byte-identical; no common guest source member
changed. The zip difference matches the seven removals, two additions and four
changed documentation/verifier files recorded in the checked JSON.

Before zip SHA-256: `b9594b203bc23e13e948d60ae0c60cdac5ef712e7b2cdd954743fde0341ad387`.
After zip SHA-256: `054f40701c02fcba3d77755c6313f6f2746155445a60fc5ad551397b67b20bff`.

## Acceptance

Previously completed exact-candidate checks were reused, with all log hashes
verified: `verify.py check` (427 passed / 6 skipped and public source inventory),
`verify.py integration`, and the explicit legacy `TestPublicLifecycle` smoke.

Resumed work completed:

- A clean exact-candidate host-only macOS wheel build, with source receipt,
  binary provenance, archive/license checks, and only `manifest.json` plus
  `mariamem-host` in the native directory. Wheel size is 42.71 MiB; there is no
  before/after wheel-size claim.
- Installation outside the checkout, two platform/session/error-recovery tests,
  and a separate Snapshot/Fork write-isolation smoke. Existing validation-venv
  dependencies were appended after the installed wheel's site-packages; the
  smoke asserted the imported package came from the new installed environment.
- An external Go module requiring `github.com/masahitojp/mariamem v0.4.0`, with
  no `replace`, `GOWORK=off`, isolated module/runtime caches, and the exact after
  zip supplied by a local file proxy. The fixture version does not publish or
  override the real public v0.4.0. Only this local mariamem fixture bypasses the
  checksum database; ordinary dependency verification remains enabled.
- All four copied public `godefault` integration tests: Start/Snapshot/Fork
  write/schema isolation, repeated/concurrent lifecycle, graceful failure paths,
  and retained-closed-handle FD lifetime. Normal runtime cache remained empty.

The wheel SHA-256 is
`282f3c5bfa342fd4190c53f12fea639f72aaefdfb2679d390a66fffffdb04d46`.
Its full clean-source inventory and build information remain in the raw wheel
receipt linked through the checked JSON.

## Stops, storage guard and limits

The resumption held both fan-out measurement locks. Every real command had a
900-second watchdog, 8 GiB available-disk floor and 1 GiB new-output budget,
sampled every 0.25 seconds. These guards cover owned scratch/staging/evidence,
not growth of the pre-existing shared Go build cache or other macOS processes.

The first installed-wheel attempt lacked pytest; the next reached SQL but the
sandbox rejected localhost bind. After correcting the validation dependency
setup and allowing local socket operation, installed-wheel acceptance passed.
These harness/environment failures are retained separately from product results.

The first external-consumer compilation crossed the owned-output budget at
1,046.90 MiB and was terminated. Completed wheel/zip evidence was retained and
owned temporary state was removed. Resuming only the remaining consumer boundary
with that exact zip and the already populated build cache succeeded, with
653.39 MiB peak new output and at least 23.27 GiB observed available disk. All
attempts removed their owned scratch/staging; source and useful shared caches
were preserved. The recorded sampled overshoot is not a strict instantaneous
disk ceiling.

This is a source-distribution size and compatibility result. The interrupted
compilation and reused cache do not establish a clean cold-build speed/memory
benchmark. No new runtime-memory fix, forced GC, guest regeneration or full ORM
campaign was performed. Ubuntu acceptance and any integration/release decision
remain separate work.
