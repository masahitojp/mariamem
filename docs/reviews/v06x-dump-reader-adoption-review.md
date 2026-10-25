# Bounded dump reader adoption review

Decision now: accept this as a verified product candidate, or adopt it on main.
Recommend **retain the verified candidate and complete the maintained-CI handoff
before main adoption**. The installed Python helper and its host prerequisite
pass both platforms, but the differential workflow currently runs automatically
only on the experiment branch. The strongest objection to delaying adoption is
that all five candidate CI jobs already passed. That establishes this candidate's
behavior; it does not supply continuing regression coverage after integration.
No new parser functionality or broader format support is needed to close this gap.

## Pinned objects and evidence

Reconstructed from the authorized productization and CI handoff: candidate
`07c9d7ec26ea57bc2ff0c192d6b2cffd686b4207`, base
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a`, branch
`experiment/dump-reader-productization`. The reviewed artifact is the
[contract](v06x-dump-reader-product-contract.md) at that candidate, with the
[usage guide](../importing-dump.md). This report was written on the candidate
branch; its later documentation commit is not a newly tested runtime source.

[CI40207664068](https://github.com/masahitojp/mariamem/actions/runs/40207664068)
is success on that exact SHA. Saved [assessment](v06x-dump-reader-evidence/ci-40207664068/assessment.json),
[run](v06x-dump-reader-evidence/ci-40207664068/run.json),
[jobs](v06x-dump-reader-evidence/ci-40207664068/jobs.json) and
[checksums](v06x-dump-reader-evidence/ci-40207664068/SHA256SUMS.json)
bind the original three artifacts. ZIPs are stored losslessly as base64 text;
decode them before comparing with GitHub's archive digest. No source guard was
weakened to store binary evidence. Every archive's digest was independently
verified, then its campaign/reference/interpreter JSON was checked against the
candidate. All four reader SQL-failure event streams preserve1146/42S02 and
contain neither Snapshot attempts nor admitted tests.

| Gate | Job | Result |
| --- | --- | --- |
| Native canonical producer/reference and same-app data variant | 121211974188 | PASS |
| Installed wheel, macOS arm64, Python3.11/3.14 | 121212176795 | PASS |
| Installed wheel, Ubuntu x86_64, Python3.11/3.14 | 121212176797 | PASS |
| Full development checks | 121211974213 | PASS |
| Development integration | 121211973989 | PASS |

Each of four interpreter reports has eight accepted route/scenario runs and a
passing native-produced data variant. Across both OSes this is eight positive
lifecycle scenarios with16 child test passes and24 accepted negative scenarios.
The earlier run40204907935 at2d76ba1 remains cancelled because integration exceeded
its30-minute job budget. The only subsequent candidate change was the workflow's
60-minute integration budget and explanatory comments; individual test deadlines
were retained. The old run is not relabeled.

## Prior conditions and detection net

The preceding productization conditions are reconstructed from
`418823a:docs/reviews/v06x-dump-post-spike-review.md` and the candidate contract.

| Condition | Judgment and evidence |
| --- | --- |
| Same users/addresses app, canonical bytes, exact candidate producer | Satisfied: bind_input.py:49/81 retains original producer/input hashes and checks fresh candidate receipts. Saved native reference and campaign bindings identify07c9d7e. |
| DEFINER/producer/options/normalization preserved | Satisfied within the observed profile: producer.py OPTIONS, retained routines and oracles.py metadata/behavior projections; no engine/collation/routine rewrite. |
| Bounded family and rejection contract | Satisfied for the finite profile: dump.py:290 checks headers, schemas and statements before connecting; test_dump_import.py exercises modes, comments, identifiers, framing and limits. The native-produced variant changes data without depending on the canonical hash. This is not exhaustive schema/routine-shape coverage. |
| Explicit installed API, dependency and discard boundary | Satisfied: dump.py:316, setup.cfg dump extra, campaign.py installed-path/packaged-host checks, both interpreter receipts. Failures preserve cause/errno/SQLSTATE and attempt DB close; cleanup failure remains explicitly reported. |
| Two children and failure admission | Satisfied: run.py assess plus unchanged stable preparation owner; four raw SQL-failure streams confirm42S02. Successful scenarios exercise commit and independent baseline. No new xdist census. |
| Separate host correction and normal regression | Technical evidence satisfied; Human adoption outstanding. guest.go:68 decodes unsigned32 then projects low16, with invalid/nested/flag-preservation tests in status_test.go and text/prepared tests in status_decode_test.go. Full checks and integration now PASS. |
| Maintained differential CI after integration | Unsatisfied: workflow lines3–15 select only the experiment branch; no pull_request/main trigger. Normal development CI runs unit checks/integration but does not invoke this installed dump/native matrix. |
| Publication-compatible evidence and clean base | Satisfied for this candidate: clean main-based branch, no design-history merge. Original archives are text-encoded; old design receipts remain untouched. |

## Remaining adoption gap

The maintained CI handoff has two connected parts:

1. Wire the dump differential gate to relevant main/PR changes, including its
   stable migration owner and runtime inputs. Current CI does not detect loss of
   that trigger: a manual or experiment run can pass while future main regressions
   are never subjected to the native comparison.
2. Separate the historical spike delta approval from continuing product input
   identity. `tests/dump_import_acceptance/bind_input.py:22–45` requires an exact
   runtime-path set relative to the old experiment origin and hard-pins host file
   hashes. An ordinary future unrelated runtime change therefore fails this gate
   even when dump behavior is unchanged. Existing mutation tests detect extra
   paths by rejecting them; they do not prove a reusable product gate. Preserve
   canonical producer/data checks and exact current source/host binding while
   moving historical approval into the adoption record. Do not simply delete
   identity assertions or allow arbitrary stale host substitution.

These are directly observable workflow/guard constraints, not reproduced user
SQL failures. Add deterministic trigger/identity mutation checks and run the
revised gate on its exact new SHA before returning for adoption. Current
success is retained, not transferred to the revised workflow.

## Host assessment and missing-things scan

The isolated host correction is technically recommended for adoption: valid
internal status65538 no longer kills the host, while the low16 protocol flags
remain intact and invalid unsigned32 input is rejected. The main objection is
changing decoding shared by all consumers; guest/mysqlwire regression tests,
the routine comparison and full development integration address that boundary.
Human acceptance of this prerequisite remains distinct from approving the reader
or a release. No Go dump API is included.

No additional changes were found in guest sources, generated runtime ownership,
HANDWRITTEN_FILES, release ledgers/baselines or version metadata. No conflict was
found in the version-gated README/Go/Python/releasing guides: the new helper is
explicitly an unreleased candidate, not a general dump importer. No stale comment
claiming the public helper is test-only was found. The contract's earlier handoff
paragraph describes pre-CI status; this review and current project status own the
new receipt rather than rewriting historical results.

Unknown/unclaimed: other producers/versions, arbitrary schema/routine shapes,
views/triggers, MySQL/legacy/Django compatibility, privilege enforcement,
large-input performance, parser maintenance cost and cold/warm setup cost.
Resource-limit tests use reduced constants; they establish rejection mechanisms,
not throughput or memory measurements at16MiB. Both OS/interpreter boundaries
are covered and do not need to be described as missing. No new independent guest
regeneration is required by this host/SDK delta; Qualification remains separate.

Review work was read-only for runtime/tests/workflow. Only evidence, this report
and current status were added/updated. No runtime suite was rerun and no main
integration, host adoption, Qualification or release was performed.
