# v0.6.0 wire-contract completion basis

Human decision,2026-10-31. The Human adopted the English proposal from
[PR42](https://github.com/masahitojp/mariamem/pull/42) at source_commit
`286976c79d97e7121173357a2dc23a5be574a0da`, with the explicit conditions below.
**The English text is authoritative.** The earlier Japanese conversational
summary is explanatory only and must not replace declared-client-path anchors
or named accepted exceptions with a claim of paired native comparison for every
entry. D1's separate deferral remains in its own decision.

## Adopted English text

> For v0.6.0, wire-contract completion means a source-pinned supported/unsupported
> inventory plus native/guest and declared-client-path anchors with the named
> accepted exceptions; complete per-entry packet capture is not required,
> uncaptured paths remain UNVERIFIED, and the exact release candidate must still
> pass Release CI.

The following three paragraphs are additional adopted conditions of this same
Human decision, not explanatory recommendations.

The accepted set is `wire.supported_commands`, `wire.base_capability_bits` and
`wire.conditional_ps_multi_results` in
[the fixture acceptance contract](../reviews/v06x-fixture-acceptance.json), fixed
at the adopted source286976c7; the formerly proposed LOCAL INFILE,
CHANGE_USER/STATISTICS/PROCESS_INFO and binlog/replication rows in
[Remaining-path dispositions](../reviews/v060-wire-d1-reconciliation.md#remaining-path-dispositions)
are explicitly **OUT for0.6.0**.

If a concrete required protocol sequence or native/guest/client-path discrepancy
appears, reopen that named question with a bounded, source-bound capture/probe;
retain original failures and attribution, and do not silently expand the whole
campaign or implementation scope.

Release CI remains necessary for the exact candidate's declared-profile
reacceptance; **a Release CI PASS must not be reinterpreted as additional wire
coverage or packet-capture evidence**.

## Exact set and evidence interpretation

The adopted numeric set is commands1,2,3,14,22,23,24,25,26,27; base capability
bits1,4,8,512,8192,32768,65536,131072,524288; conditional PS_MULTI_RESULTS262144
only with validated prepared execution support. This decision changes no bit,
handler or negotiated behavior. The active source hash baseline437d74d and the
later byte comparisons remain distinct from runtime acceptance. Other
commands/required capability profiles are not implicitly supported because an
application happens to pass.

Native/guest anchors and declared-client-path anchors are different evidence
categories. Their recorded scope must be retained: this decision does **not**
assert paired per-entry native comparison for G1/EP1/EG1. Separate native controls,
real client-path observations and bounded source evidence must not be relabelled
as such comparisons. The per-entry ledger's uncaptured command/flag paths remain
UNVERIFIED, not absent, zero, proven unused or PASS. Existing errno/SQLSTATE,
following-query, identity and cleanup oracles remain in force.

The [named consumer exceptions](prepared-consumer-exceptions.md), their original
functional failures, profile/version boundaries and recheck triggers remain
unchanged. This decision neither repairs an external consumer nor adds a new
exception. The fixed dbt1.7 replay and optional1.8 macro experiment retain their
own exact sources; neither becomes general dbt or wire support.

COM_RESET_CONNECTION, server-side cursors/COM_STMT_FETCH, packet continuation and
capacity raises stay OUT under the existing release scope. TLS, compression,
DEPRECATE_EOF and alternate authentication remain outside the advertised/local
root endpoint profile. The explicitly OUT loader/admin/replication paths above
have no new positive/negative runtime acceptance from this decision. SQL-file
import is not LOCAL INFILE transfer; metadata SQL is not PROCESS_INFO; Live
Reset or COM_STMT_RESET is not COM_RESET_CONNECTION. These limits must remain
visible in the usage guides.

## What this approval closes

It fixes the interpretation and disposition of the wire coverage map for0.6.0.
It does not claim universal protocol completeness or capture all client sequences.
Unfinished entry adoption/integration, #24's detection-net repair, exact candidate
qualification and publication keep their own scope and decisions. No new
implementation, CI campaign, release version change or publication is authorized.
The decision is canonical here; project-status links it, usage docs describe
limits, and the reconciliation retains the evidence and CI blind spots.
