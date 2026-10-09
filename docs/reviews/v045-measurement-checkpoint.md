# v0.4.5 measurement foundation checkpoint

## Qualified source and measured boundary

[Native qualification](v045-native-qualification.md) passed for exact
`8a30e184890ba686caba65d1876aee829a4a178a` on both supported OS/architecture pairs.
It is not evidence for the diagnostic source additions in this checkpoint.
Main remains released v0.4.4 `8ede4ad65def07436b64801076004ff80aec0799`.
No merge, release, guest change or performance optimization is authorized here.

Reused `benchmarks/ownedprepared` with Go1.26.8 and the existing process-cost
helper, sequentially. Three trace-disabled trials per logical payload, each with
2 Forks; one separate trace-enabled attribution trial per payload. This is a
local macOS27.0.1 arm64 observation, not minimum-platform qualification.
[Compact source/binary identities, commands, all samples and selected traces](v045-snapshot-preliminary.json).

| Logical fixture payload | Full public Snapshot median | Observed range |
| --- | ---: | ---: |
| minimal | 353.5 ms | 347.3–409.5 ms |
| 10 MiB | 390.4 ms | 389.8–434.6 ms |
| 100 MiB | 721.0 ms | 700.0–735.9 ms |

These numbers include the public operation, not only host export. Three samples
are insufficient for a robust p95. Logical fixture payload is not prepared-file
size. Separate traced trials must not be subtracted from untraced medians to
invent a phase breakdown. COUNT work remains outside Fork-ready latency.
Actual Fresh-per-test suite crossover, Python import, parallel product workloads
and comparable external controls are still pending; no optimization decision yet.

## Minimal attribution changes

Existing opt-in `MARIAMEM_TIMING_DIR` diagnostics now expose:

- `public_snapshot`: destination, host return, source cleanup, owned acquisition;
- `snapshot_export`: allocation and logical read/materialization byte/file counts;
- `snapshot_publish`: enumeration, source inventory/hash, copy, target inventory/hash.

Nested scopes are not additive. Logical counters are not physical I/O; read and
hash remain a combined interval where they use the same streaming operation.
No copy/hash/lifecycle operation is removed or reordered. `Publish` retains its
existing interface; the internal context variant carries diagnostics. The
handwritten generated-Go execution adapter changes, but the compiled guest,
generated code and child filesystem implementation do not.

Focused tests prove traced/untraced published manifests agree, logical copy and
hash pass counts match known input, and corrupt published content still fails
validation. Existing timing/snapshot/host/generated-Go tests pass. Because these
calls lie on actual Snapshot export/publish/acquisition paths, this diagnostic
candidate requires fresh native runtime qualification using the existing
workflow. Old proof is preserved with its actual tested source.

## Build identity recurrence prevention

A first worktree build stamped the parent main commit, despite worktree Git HEAD
being correct. It was rejected before measurements. Pinned Go1.26.8's VCS scanner
recognizes a `.git` directory, not this worktree's `.git` file, and found the parent
checkout. Measurements instead used a disposable normal `.git`-directory clone
of the exact same clean source; no hand-stamping or identity override.

Shared `git_identity.verify_go_binary` checks exact clean checkout, embedded
commit, VCS kind, modified flag, duplicate identity settings and pinned toolchain.
`build_alpha --ci-candidate` applies it immediately after building, before staging
or packaging the host. Wrong/dirty/missing/duplicate identities fail closed.
The helper does not claim binary stamping proves generated-source reproducibility;
that remains a separate release build/input responsibility.

## Focused results and handoff

- 12 identity unit tests PASS.
- 147 identity/release/runtime-proof/workflow/development-scope tooling tests PASS.
- 28 handwritten-source inclusion/generated inventory/version/default-boundary tests PASS.
- Go timing/snapshot/host/generated-Go package tests PASS, including diagnostic
  content/count/integrity oracle.
- Existing real-guest modified-child/new-baseline test PASS with attribution enabled; both Snapshot operations emitted all three scopes and preserved parent/child state.
- Diff/working-tree inspection before commit; no runtime benchmark competition.

Temporary clones, caches, downloads, binaries and databases are disposable.
Preserve only committed reports, compact JSON and Git refs. Continue decomposition
and actual suite measurements after this source is qualified. Do not turn this
checkpoint into an optimization recommendation or v0.4.5 release approval.
