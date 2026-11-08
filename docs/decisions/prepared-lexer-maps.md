# Prepared compiled lexer maps: adoption decision

On2026-11-08 the Human accepted the recommendation to adopt this bounded
optimization and prepare a minimal product candidate. This does not authorize
main integration, Qualification, version selection or publication.

Reviewed evidence source_commit: `8d5f8284cedde31751d4e53e52ddfd61f69432ab`.
Product base: `3d8b2201c1f36fa5b7264e0450104055f3822272`.
[Actual C measurement and limits](https://github.com/masahitojp/mariamem/blob/8d5f8284cedde31751d4e53e52ddfd61f69432ab/benchmarks/lexercmeasure/results/README.md).
[Both-host receipt](https://github.com/masahitojp/mariamem/blob/8d5f8284cedde31751d4e53e52ddfd61f69432ab/benchmarks/lexerbinding/ci-42437059943/README.md).

## Accepted behavior and limits

Only the compiled-registration callsite before XML loading uses prepared
state_map/ident_map pairs:638 descriptor IDs,28 unique512-byte pairs. The data
contains no pointers. CHARSET_INFO, state, allocator and locks remain per guest;
normal compiled relocation supplies pointers into that guest's static data.
Unknown/noncompiled descriptors and dynamic XML/copy callsites retain the original
producer. This is not cross-guest memory sharing or initialized-engine cloning.
Removing each known map allocation also removes that allocation's OOM failure;
other failures are not suppressed. Internal verifier/force-original switches
are private and must remain inaccessible through ambient public startup.

The single-Mac actual-C comparison reports ordinary Fork p50
21.15→19.35ms/P1 (-8.5%) and28.97→28.21ms/P4 (-2.7%). All three P1 pairs improve;
batch CPU falls in every pair at both parallelisms. Accept those bounded results,
not a promise of stable P4 whole-batch speedup, RSS reduction or Ubuntu speedup.
Candidate ordinary/diagnostic P4 COUNT/SUM tails790/798ms remain retained and
unassigned; the change is neither blamed nor cleared of causality. No extra
sampling is a condition of adoption. Dynamic XML loading has component/source
coverage, not an actual full-loader runtime acceptance claim.

## Fixed implementation and completion gates

1. Canonical source inputs: preserve exact numeric pairs and compiled-only wrapper,
   reject source/config/input drift, and keep guest/source.patch canonical.
   Two separate clean builder jobs must match each other and the accepted
   guest14b41cea… / linked69dbde34… bytes. A mismatch stops for inspection.
   Stage1 uses the existing UNQUALIFIED bootstrap output format; a pair of such
   builds is source-reproducibility evidence, not Qualification.
2. After Stage1, install the canonical generated Go from these exact inputs;
   promote reviewed CRC/thread bindings without relaxing their body/data checks.
   Update HANDWRITTEN_FILES for the table oracle, build/translation/input
   inventories, worker layout and retained-function license evidence. Preserve
   prior receipts under their original identities. No whole experimental-history
   merge and no new public API.
3. On the resulting exact candidate, both macOS15 arm64 and Ubuntu24.04 x86_64:
   full638-table equality, corruption rejection, ordinary/profiling separation,
   CRC, worker-failure and forced J1 controls; native SQL comparison, two pristine
   children and confirmed cleanup. Add a fixed binary prepared case with
   Unicode/NUL/quotes/backslash parameters and an arithmetic parameter. The
   existing PyMySQL reference only exercised normal SQL; Mac Go measurement
   alone does not close Ubuntu/prepared-native coverage.
4. Preserve exact CI source/job/artifact identities and checksums; review the
   minimal final candidate for main integration. Existing product CI remains
   required. Versioned release is a later decision.

Stage1 source and reference acquisition is **pending**, not a new PASS. Stage2
canonical runtime installation and both-host acceptance are **not yet run**.
The experimental run42437059943 at6134274a stays experimental evidence, with C
origin b1a265cc; it is never relabelled to the canonical source commit.
