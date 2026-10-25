# Dump post-spike Human Review

Decision now: start productization of a **bounded Python library reader** for
the observed MariaDB12.3.3 producer profile. Recommend proceeding with that
limited scope: it preserved the canonical input and native semantics through
the ordinary preparation/child lifecycle on both supported OS/interpreter
boundaries, and its import route does not require a native MariaDB executable.
The strongest objection is maintaining a second client parser. The current
prototype does not enforce a complete supported-format/resource contract, so
it is not ready to adopt. Make that contract and its rejection tests the first
productization deliverable; if preserving the agreed format requires expanding
into a general client, choose the demonstrated external-client recipe instead.
No setup-time or maintenance-cost saving has been measured.

This recommendation authorizes nothing by itself. It is a route/scope decision,
not acceptance of the prototype diff. Host correction adoption, main integration,
Qualification and release are separate decisions.

## Reviewed objects

The candidate reconstructed from the closure record is source_commit
`c417e21ba7dabefa5d95600ea322091732430c97`, experiment/dump-import. The
pre-comparison base is `353bf9291d96785f8dcaa3585cec00e56242256e`; the immediately
preceding host-corrected candidate is
`9494e755a5e7d79a9702e1d1dc7c1caae993e801`. This review was written from closure
documentation source_commit `3e62ef78d814c56db0b8bf0a0800a46ba4e172a1` on
design/dump-import-comparison. Main remains
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a`; no integration is proposed here.

Reviewed evidence: [spike exit](v06x-dump-spike-exit-status.md),
[assessment](v06x-dump-comparison-evidence/ci-40197606173/assessment.json),
the three saved raw artifact ZIPs and their
[checksums](v06x-dump-comparison-evidence/ci-40197606173/SHA256SUMS.json).
One live metadata read confirmed
[CI40197606173](https://github.com/masahitojp/mariamem/actions/runs/40197606173)
success at exactc417e21; saved jobs121181728703/121181983291/121181983298 all
bind that source. Archive/file digests and interpreter results were independently
rechecked. No CI, build, benchmark or runtime acceptance was rerun for this review.
Code references below refer to c417e21, not the design checkout.

## Prior conditions and result

| Condition | Judgment and evidence |
| --- | --- |
| Same migration app source/data | Satisfied. users/addresses owner inputs are hash-checked by bind_input.py:49; the extension remains part of that app. This meets preparation-import-design.md:14. |
| Fresh exact-candidate dump and native reference | Satisfied. BOUND receipt records candidate producer PASS and canonical081ef027 bytes; both native references and guest observations match. bind_input.py:78/107 enforces provenance without relabeling6d81a2f. |
| Definer, producer options, normalization and acquisition | Satisfied for the observed profile/hosts. Retained root@localhost DEFINER/SQL SECURITY and routine behavior are in raw observations; producer.py:43 pins options. No routine/engine/collation rewrite. |
| Guest client then reader; two independent children | Satisfied. Both direct probes PASS, followed by eight positive lifecycle scenarios and16 child passes. workflow.py tests commit then independently restores the imported baseline. |
| SQLSTATE/failure/partial-state/cleanup admission | Satisfied. run.py:63 requires1146/42S02; test_dump_import_spike.py:117 rejects wrong/absent states. All four reader failure records show42S02; all24 negative scenarios are accepted with no Snapshot/test admission. |
| Host dependency recorded and not adopted | Satisfied as an experimental condition. The exact before/after hashes and unsigned32/low16 contract are saved in the new receipt; adoption remains unsatisfied and separate. |
| No hidden scope expansion | Satisfied. Views/triggers remain excluded; no cold Mac/setup-cost, arbitrary legacy/MySQL/Django claim. The prior xdist gap is closed by migration adoption and was not re-tested. |

The bounded comparison is complete. No remaining spike-exit blocker was found.
The PASS remains conditional on the experimental host correction, not proof
that the unmodified main host imports this corpus successfully.

## Productization gaps and detection net

| Gap / consequence | Existing detection | Required bounded continuation |
| --- | --- | --- |
| Supported format is currently a test fixture, not a product contract. frame() uses UTF-8, one escape treatment and only `;`/`;;` delimiters (reader.py:27/67/88), without validating changing SQL modes. Inputs outside that profile could be framed incorrectly. No such failure was observed in the accepted corpus. | Canonical hash/producer binding plus quote/comment/framing mutations detect changes in the exercised corpus. No gate proves handling/rejection of a broader family of SQL modes or producer variants. | Enumerate accepted producer/options, charset, SQL modes, comments, identifiers, delimiter/client commands and schema targeting. Add finite acceptance/rejection cases around those boundaries. Pass executable comments through; do not interpret or discard SQL to obtain PASS. |
| Input/resource bounds are not specified. frame() materializes statements and counts original newlines per location (reader.py:29/41), and has no public file/statement-size limit. Larger-input behavior is unmeasured. | The small fixed dump and CI workspace/timeout guards do not verify a product limit or large-file behavior. | Select explicit limits and deterministic error/location behavior. Test the boundary; do not make large-app or performance claims from the small spike. |
| Runtime prerequisite is not adopted. The earlier uncorrected host terminated on65538 during the data-reading function. | Both-host guest/mysqlwire tests and the unchanged routine/subsequent-SELECT campaign catch that regression. The approved delta hash guard prevents an unrecorded runtime substitution. | Prepare a separately reviewable host-correction adoption candidate and relevant normal host/wire/consumer verification. Do not treat dump CI as full runtime/release Qualification. |
| Product API/dependency/docs and maintained CI ownership are absent by design. The reader is under tests/, not installed product code. | Existing spike CI checks source imports and the fixed preparation lifecycle; it does not exercise an installed reader entry point or enforce a new public contract. | Propose an explicit opt-in preparation helper, its dependency/error boundary, installed-consumer test and maintained native differential gate. Keep automatic preparation routing and parser fallback out. |
| The design/evidence branch is not a publication candidate. Its existing raw Mac server log and ZIP receipts violate the public-source file policy. | check_public.py stops at docs/reviews/v06x-dump-acquisition-evidence/macos/macos-server.log; that tracked log predates this review in44b37b5a180a6d00922feedc1ad721da051c16c9. This is an actual failed check of the design checkout, not a failed comparison candidate. | Select production changes into a clean candidate and preserve historical evidence under its original receipt policy. Do not merge this branch wholesale or weaken the public-source guard. Evidence packaging for a future landing needs an explicit compliant representation. |

The format contract must describe a bounded family of generated inputs; a helper
that accepts only the single fixture hash would not be useful productization.
Conversely, producer-profile agreement is not proof of every data/routine shape:
keep claims at the cases and rejection boundaries the maintained tests establish.
Do not weaken errno/SQLSTATE, original-file diagnostics, cleanup or two-child
oracles to expand that family. Productization owns these gaps; none reopens the
already satisfied fixed-input comparison exit.

## Route choice and host separation

| Route | Judgment now |
| --- | --- |
| Bounded library productization | Recommended scope for the next work. Current reader import uses the existing supported Python driver path and no native client executable; parser/contract ownership must be explicit. Final API and packaging require design before implementation. |
| Optional external-client recipe | Viable alternative demonstrated on both hosts. It retains native client framing/directives, with executable acquisition/version/dependency upkeep and no statement ordinal in native diagnostics. Prefer this if bounded parser ownership cannot be accepted. |
| Defer the format | No current corpus blocker justifies deferring it. Defer remains appropriate if neither parser ownership nor native-client setup is acceptable; the spike has no measured cost comparison to settle that preference. |

Both working routes depended on the same host correction. Selecting the external
client does not remove that dependency. Assess the host decoder separately:
guest.go:69 validates unsigned32 input and projects at line87 into the existing
uint16 protocol field, with invalid/nested input and text/prepared-chain tests.
Its three-file delta is a plausible isolated adoption candidate, not permission
to merge the experiment or design branch. Preserve all guest/generated inputs
and carry only reviewed production-quality changes into a later main candidate.

## Missing-things scan and next decision

No new mismatch was found in unchanged README/Go/Python/release guide contracts,
SDK/dependency files, guest/generated ownership or release ledgers. The current
preparation guide correctly says it does not implement dump import. Comments
calling this reader test-only remain accurate. Source diff inspection against
main identifies only the recorded decoder plus its two tests in the runtime
boundary. No additional hidden runtime delta was found.

Verification of this documentation review: references, raw receipt checksums,
diff whitespace and public-source checks of the two changed Markdown files
passed. The whole-design-checkout public-source check failed
on the pre-existing log noted above; no full public-source PASS is claimed.
The old evidence was left intact. This failure does not invalidate the pinned
experiment CI receipt, but prevents treating this checkout as merge-ready.

Not established: installed reader behavior, other producer/client versions,
views/triggers, privilege-context equivalence, Go dump entry, large inputs,
parser maintenance cost or cold/warm setup cost. Opposite-platform/interpreter
execution and SQLSTATE coverage are established by this receipt, not missing.
The existing migration adoption remains the lifecycle/xdist authority; there is
no reason to repeat its census for an unchanged callback/worker contract.

If the Human selects bounded library productization, first fix the format,
resource, API/dependency and maintained-test contract; then implement and verify
that agreed scope on an experiment branch. Return a separate host adoption
assessment and later a product candidate review. If that finite contract cannot
preserve inputs without becoming a broader client, stop and recommend the
external-client recipe with the concrete unsupported case. This review starts
none of those implementations or later gates.
