# P5 Human Review — native consumer limits, before P6

**Decision now: accept the two bounded Connector/Python26.7.0 limitations below
as explicit consumer exceptions and proceed to P6. Recommendation: accept and
proceed.** Actual guest and pinned native MariaDB produce the same values and
errors; Go prepared execution, Python normal CRUD/typed binary/text controls,
and existing application regressions pass on both supported platforms.
Changing the server to disguise these observations would have no demonstrated
correctness basis. No runtime repair is proposed by this review.

**Strongest objection:** native parity does not make Python's failed CALL or
shortened value useful, and the north star requires preserving application
behavior. These cases cannot be advertised as working one-line switching.
Behavior against MySQL itself has not been compared. I still recommend the
bounded exceptions because the current MariaDB compatibility boundary is
demonstrated and working engine/wire/Go paths already exist; universal driver
compatibility is not established. Reject this recommendation if these exact
Python uses must work in the first prepared adoption. That would require a
separate, finite driver/server comparison, not an assumption that changing
mariamem will fix them.

P5's observation/regression work is complete for the specified available modes,
but its functional disposition is **pending Human decision**. Original FAILs
stay FAIL; approval would record “P5 evidence complete with accepted consumer
exceptions,” not unconditional functional PASS. P6 remains unfinished. This
decision does not approve main adoption, a version, Qualification or release.

## Reviewed object and evidence

Reconstructed from the current handoff, rather than supplied as a new review
tuple: branch `experiment/prepared-consumers`, candidate/source_commit
`c5dddf36aac2d62cfe8d4edd22b41fb8da7fdd9b`; P5 base/source_commit
`371641c8df48f7593b3e008d711b9ad546a03b37` (P4 closure).
Reviewed artifacts at that candidate: [P5 candidate](v06x-prepared-p5-consumers.md)
and [comparison-gate correction](v06x-prepared-p5-ci-diagnosis.md).

[CI39769591459](https://github.com/masahitojp/mariamem/actions/runs/39769591459)
completed all six jobs successfully on the exact candidate. Its
[retained receipts](v06x-prepared-p5-pass-evidence/receipt.json) bind raw/stored
hashes, platform host binaries and guest identity. Guest SHA256 remains
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
The runtime is a development generation, not canonical adoption or Qualification.

Cross-checks: [original prepared requirement](v06x-prepared-design.md),
[production design §2, §6–§8](v06x-prepared-product-design.md),
[P4 finite closure](v06x-prepared-p4-failures.md),
[Snapshot contract](../decisions/snapshot-product-contract.md),
[routine scope](../decisions/routine-support-scope.md), and current
[status](../project-status.md). The original design and production design are
historical decisions; this proposed exception does not rewrite them.

## What a user encounters

| Exact case | Observed inconvenience | Coverage and boundary |
| --- | --- | --- |
| Connector26.7.0 `cursor(prepared=True)` calls a procedure returning two result sets, then uses `nextset()` | The first result is available, but advancing fails before the second; a subsequent SELECT on the same connection also fails. This workflow cannot be declared supported by native matching. | Pure on both OSes, C/default on Mac, and native MariaDB show the same failure. Raw prepared protocol/P3 and Go CALL work. This is not a blanket failure of procedures, ordinary text CALL, or every Python CALL variant. |
| Mac C/default projects bytes410042 through an untyped prepared character expression | Python receives only `A` instead of `A`–NUL–`B`, potentially producing a wrong value or assertion without an exception. | Server HEX returns410042 and length3; CAST AS BINARY and typed VARBINARY storage/read preserve all bytes. Pure preserves this projection too. This is not evidence of DB file corruption or truncation of all binary columns. |

Evidence: both platform `p5-consumers.json` and `p5-edges.json` under the retained
receipt; pinned native [Mac Python3.14 control](../../tests/fixtures/prepared-p5-native-macos314.json)
and [edge control](v06x-prepared-p5-ci-evidence/local-macos-edges.json).
Complete edge case objects were compared during this review: values, primary
errors, following-query errors, cleanup errors and nextset method hashes match
the reference for the actual selected implementation. No new SQL execution was
needed for that comparison.

These are reproduced consequences, not hypothetical hazards. Their occurrence
frequency in arbitrary applications is unmeasured. The exact driver root-cause
lines and behavior against MySQL are unproven. Installed source shows the
prepared cursors inherit ordinary `nextset`; that is a plausible explanation,
not a conclusive diagnosis. Do not call either issue a confirmed universal
Connector bug or claim that it occurs with every MariaDB/MySQL version.

## Accepted conditions and detection net

| Prior condition / possible gap | Judgment now | Evidence / detection |
| --- | --- | --- |
| Real Go explicit Prepare with interpolation on, implicit prepare with it off | Satisfied in bounded cases on both OSes | `p5-consumers.json` Go modes, counters, transactions/values/CALL and cleanup; matcher requires Go PASS |
| Python pure and unchanged default on each OS; additional C where available | Required executions satisfied; two functional exceptions not yet accepted | Both runtime receipts; `tests/v06_prepared_consumers.py` does not force default. Mac runs C; Ubuntu explicit C SKIP only, as allowed by design §6 |
| Native reference for actual C client | Satisfied for current Mac client | C extension and Python source hashes/ABI match; `verify_cext_profile` rejects absent/different reference. Python/OpenSSL patch versions differ and remain recorded; no claim of identical whole environments |
| Existing accepted syntax presentation exception | Satisfied for this candidate | Raw1064/42000, pure1064, Mac C2006/HY000 and following query succeeds. Production design §6's prior decision does not authorize CALL/NUL exceptions |
| Text/auth/options/routines, SQL/transaction, Snapshot/Fork/isolation/Start/Close | Satisfied in existing bounded suites on both OSes | Go installed integration/routine/auth logs; Python17 cases per OS |
| SQLAlchemy/GORM unchanged applications | Satisfied for existing anchors | Per OS: start/fork/fork/start, SQLAlchemy11 cases each and GORM8 each; summaries retained |
| P1–P4 retained controls / exact installed lifetime bindings | Satisfied in this run's scheduled gates | Both runtime jobs pass all earlier probes and binding/mutation steps; both unit jobs pass. This review does not repeat those implementations |
| Functional exception approval | Unsatisfied until Human decision | CI deliberately emits functional_acceptance FAIL / human_disposition PENDING. Approval is not detectable from green CI |
| Detailed CALL following-query failure tripwire | Current captures manually match; permanent automatic assertion still needed | Existing edge step captures errors but only rejects capture failure. P6 must preserve an exact edge comparison, including subsequent query and cleanup; do not infer this check from the normal consumer matcher |
| Ubuntu C mode availability | Explicit allowed SKIP, not C compatibility PASS | `ubuntu-p5-environment.json` directly records OPENSSL_3.2.0 missing from system libssl3. Default/pure actually run; do not alter the user's driver environment to hide it |
| Canonical generation / J1 / independent identity / normal CI placement | Unfinished P6 | Required by production design §7–§8; development CI is not their replacement |

The C-profile control uses Mac Python3.14.8/OpenSSL3.5.9 against a pinned
Linux/arm64 MariaDB container. Actual Mac CI is3.14.7/3.5.7. The comparison binds
client ABI/binary/Python sources and OpenSSL series, not every platform library.
Ubuntu's fresh reference is Linux x86_64. Neither reference is relabelled a
Mac-native MariaDB server. See the diagnosis for exact identities and limits.

## Recommendation boundaries and alternatives

Accepting the proposed exceptions preserves all demonstrated normal prepared
benefits without inventing a server workaround. It explicitly narrows what is
claimed for these client combinations, relative to an unqualified promise that
all prepared workflows work. It does not require applications to change SQL as
a condition for calling an unsupported case “complete.” The original failure
oracle and raw observations remain available after approval.

Deferring all prepared work avoids accepting these two user-visible limits but
also withholds the tested Go/Python normal prepared paths. Fixing it in the
guest or driver is not currently a scoped one-line repair: the ownership of the
cause and MySQL behavior have not been established. If the Human rejects the
exceptions, the next bounded work should compare only these two reproducers
against the intended MySQL reference with the same client builds, then identify
the responsible decoder/next-result path and return an owner-specific repair
scope. Do not silently start that investigation or promise an unsupported fix
cost. No full guest/shared-memory census is needed for this question.

If approved, P6 must:

1. Record this exact disposition in current product state; retain functional
   FAIL separately from native matching and accepted exceptions.
2. Carry the edge comparison into a deterministic gate, including an injected
   changed value/error/following-query outcome that must fail. Preserve full
   native payloads and never normalize them into useful values/results.
3. Complete canonical source ownership, fixed-input independent guest builds
   and Go regeneration, exact binding/J1, licenses/provenance/source guards,
   and choose durable normal-CI placement for selected consumers.
4. Before adoption, update current Go/Python/public guides with precise
   supported cases and version-specific exceptions; avoid “all prepared works.”
   Keep routing/one-line switching as a separate, still incomplete capability.

## Other missing-things scan and review limits

No new public API, version, guest/converter pin, Generated Go or release ledger
change was made by the P5 comparison repair. Existing public guides still say
binary prepared support awaits adoption: correct for main, not an adoption-ready
prepared contract. No contradictory newly published support claim was found;
the guide update above remains an explicit later gate.

No new issue was found in the scoped file/status scan of source ownership or
stale implementation comments. This is not an independent audit of every P1–P4
line or license. P6 inventory, independent generation and J1 remain unverified
at this candidate, rather than checked off from the old canonical inventory.
No new performance campaign, cold/warm promise, general shared-memory guarantee,
main integration, release version, Qualification or release is decided here.
