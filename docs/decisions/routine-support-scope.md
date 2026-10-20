# Routine support scope

Human decision, 2026-10-20. The minimum procedure/function bootstrap is approved
for canonical adoption preparation. **This is an adoption-scope decision, not a
claim that the current published release already includes it.** The Human
subsequently approved main adoption on 2026-10-20 after the
[both-OS adoption review](../reviews/routine-canonical-ci-review.md). Main contains
the reviewed routine/text implementation; binary prepared productization remains
separate. Target version, final Qualification and publication remain separate
decisions. Published v0.5.3 does not contain this change.

| Feature | Product scope | Reason / boundary |
| --- | --- | --- |
| Stored procedures and functions | IN | Ordinary migration/seed/dump routines and reusable isolated test DBs; use the bounded bootstrap and lifecycle/consumer acceptance |
| DEFINER on procedures/functions | BOUNDED | Accept and retain the clause and SQL SECURITY metadata; verify minimum execution and Snapshot/Fork retention. With `--skip-grant-tables`, the embedded test guest does not enforce definer account existence or privileges. Clause acceptance does not establish native account/security-context equivalence |
| Packages / package bodies | OUT | Outside product support; no package compatibility tests or guarantees |
| Scheduled events | OUT | The adopted embedded build lacks the event scheduler; CREATE EVENT returns1235 |

## Packages: schema representation is not product support

The pinned `mysql.proc.type` enum includes `FUNCTION`, `PROCEDURE`, `PACKAGE`
and `PACKAGE BODY`. The schema can represent package records; these enum values
must remain intact for source/signature compatibility. Their presence does not
promise package SQL execution support. Packages/package bodies are **not supported,
not compatibility-tested and not guaranteed** by mariamem. No package execution
experiment or compatibility test is part of this adoption.

This exclusion is a product-scope decision, not a claim that embedded MariaDB
necessarily rejects package statements. The Human's reasons are:

- Packages are a MariaDB-specific Oracle PL/SQL compatibility feature without
  an equivalent MySQL package feature. This does not mean that modern MariaDB
  requires Oracle SQL_MODE for every package statement.
- They are outside the main one-line-switching workflows: ORM/driver prepared
  statements and procedures/functions carried by ordinary dumps.
- Package behavior is outside the product test scope; do not imply support from
  shared system-table enum values or successful ordinary-routine tests.

Schema-signature tests that retain the exact upstream enum are not package
behavior tests. Do not delete enum values, reject valid source signatures or add
package probes to make the scope declaration look consistent.

Events and packages are both OUT, for different reasons: **events are an embedded
build restriction (1235); packages are outside product scope.** Do not collapse
the two reasons into "both impossible in embedded".

## DEFINER: syntax and persistence, not grant enforcement

Procedures/functions in the adoption candidate accept explicit DEFINER clauses.
`SQL SECURITY DEFINER` and `INVOKER` metadata survive Snapshot/Fork. The guest
continues to run with `--skip-grant-tables`; it does not reproduce real-server
account existence or privilege enforcement. Metadata describing a definer does
not mean that the guest switches to that native account/security context.

The bounded check covers omitted/CURRENT_USER/explicit root/nonexistent definers,
DEFINER/INVOKER and both routine kinds (16 combinations), then the same
execution/definitions in two children. It deliberately does not add CREATE USER,
GRANT, a full system schema or a general privilege-compatibility promise.

For example, the observed guest executes routines whose absent definer is stored
in metadata; the ordinary grant-enforcing MariaDB12.3.3 control rejects the two
SQL SECURITY DEFINER executions with1446. Guest CURRENT_USER stayed root@localhost
in this cohort. Access-control or CURRENT_USER-sensitive assertions therefore need
an appropriate real-server check; this does not invalidate ordinary routine
logic and isolation tests. See the
[bounded evidence](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-routine-adoption-bounds.md). The
[both-OS CI receipt](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-routine-adoption-bounds-ci.md) subsequently
confirmed the same bounded guest behavior on macOS arm64 and Ubuntu x86_64.

## Adoption boundaries

Keep the product-managed proc-structure contract from the
[Snapshot decision](snapshot-product-contract.md#approved-routine-candidate-boundary--not-yet-adopted).
Fresh initializes before ready; incompatible restored structure is rejected,
not repaired. Routine rows remain mutable, private child data.

Only the minimum production-quality source/generation/contract changes are to
be adopted. Do not merge exploratory history or silently promote experimental
prepared limits. The text multi-result prerequisite and prepared production
acceptance remain separately recorded in the
[prepared/multi review](https://github.com/masahitojp/mariamem/blob/9250ff5/docs/reviews/v06x-prepared-multi-spike.md#conditions-for-production-and-review-limits).
The routine decision does not waive those conditions. Public usage documents
must retain the same package/event exclusion and the bounded DEFINER statement
when procedure/function support is published.
