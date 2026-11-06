# Issue65 G1 native input repair

Human continuation after CI42303099940,2026-11-07: repair the demonstrated G1
differences, preserving the profile and D2. The prior234 observations completed
on macOS/Linux with the same195 PASS/39 mismatches. The original fixed-guest
receipts remain under [issue65-prepared-input](../issue65-prepared-input/README.md)
and are not relabeled. The [Linux assessment](evidence/baseline-ci42303099940.json)
records all234 observations matching macOS,including the39 failures.

The experimental guest adds checks to decoded command/EXECUTE entry, checks the
advanced native decoder pointer for surplus input, and restores native conversion
metadata when a fresh-descriptor bind fails. It does not add a host decoder.
Fully decoded overdeclared strings retain D2's empty-string acceptance; their
remaining bytes are consumed by the native string helper. Temporal decoding does
not get that exception. Empty PREPARE still invalidates the last-statement alias.

Only guest/experimental.patch changes engine behavior. Canonical source.patch,
production generated code, controller ownership and public APIs remain unchanged.
Future G2 metadata/result chains and P1/P2/adoption/release remain separate.

Bounded verification:2h active work,30min measurement tooling,local native plus
at most one Linux CI; owned builder/runtime12GiB each,free floor12GiB. New guest
identity and full worker-body binding review precede installation. Repeat22
lifecycle/126 prior observations,existing controls/supporting checks and unchanged
G1 fixture234 observations. Add narrow controls for multi-parameter rollback,
retained charset conversion,first rejected bind and empty-PREPARE alias state.
Save failures,do not refresh expectations to match output. Dispose SDK,converter,
archives,build trees,binaries,caches/worktrees after retaining compact evidence.

Guest/checked host source_commit is `65b49e3dc31e9b2da63b317e015f8f471e79a83e`.
New guest SHA256 is `7103c8116151a386b1359e9ea02fda7e31fe8145f37a221001f97e7de2ce9a91`.
It remains a development UNQUALIFIED artifact,with new guest attribution. The initial mount
preflight and interrupted/restarted SDK setup are preserved as setup records,
not native execution evidence.


## Fresh macOS native result

Execution at tooling source_commit `d7c701926fa159597a9e878147ca3608bd4a80b8`
passes the unchanged7 G1 groups/all234 observations,zero mismatches and missing0.
[Raw G1 evidence](evidence/macos-g1-raw.txt),[parsed result](evidence/macos-g1-result.json)
and [reference](evidence/macos-reference.json) retain the execution/source binding.
All39 previously failing named observations now pass with the same expected values.
Cached reuse recovers for short_scalar/extra_scalar/prefix13..20. The original
D2 malformed-string acceptance remains in the passing baseline.

Existing22 lifecycle,88 compatibility and38 limit observations,2 existing
FOUND_ROWS/UCA controls,3 policy controls and supporting checks(including22
installer tests) also pass. Four new native controls pass: partial two-parameter
descriptor rollback,original bind charset retained across SET NAMES and rejection,
first rejected bind without installing a usable cache,and empty-PREPARE alias
invalidation while the explicit old handle/cached type still works.

The worker [binding](binding/identity.json) verifies free/yield/entry complete
bodies against canonical prepared-P2 with recorded relocation/name mapping.
All3 full bodies also match the previous reviewed4caa guest byte-for-byte;
ABI offsets remain16/40/44. This is body verification for the new guest,not reuse
of the old guest's runtime PASS. The new runtime's full7372-file source inventory
and binary remain unchanged after execution. Its283 staged Go/assembly/data
files(not all compiled on both OS) are the Linux comparison reference.
Binary SHA256: `c78d70d016ca03854ce1b815e387f474040761132b25f3c29bc122b07c277403`.
Reference SHA256: `e115653700e232e9420a5898e3b61ef01a38b2891052a8d207e31250b211bec4`.

Recommendation: repeat this exact candidate once on native Linux with strict
283-file comparison before closing this repair. G2 remains the next compatibility
scope; public APIs,30s timeout,controller relocation,performance and adoption
remain pending. Canonical guest/generated production code are unchanged.
Local builder/runtime SDKs,archives,converter,generated code,binaries,Go caches
and worktrees are disposed with [cleanup debt0](evidence/local-disposal.json).
One strict Linux submission remains;its result has not been observed.
