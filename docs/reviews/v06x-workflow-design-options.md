# v0.6 connected workflow design options

2026-10-18. Design starting point: `7b3f96b` and its
[capability map](v06x-capability-map.md). The Human approved that planning
direction, not any implementation below. This document compares mechanisms;
no API spelling or transparent-routing implementation is selected.

## 1. Two journeys, one lifecycle

New application: enable the test integration, run its migration/seed once,
acquire a fresh child for each test, use the application's ordinary connections,
then close test-owned connections and the child. Add the second test using the
same setup. Existing application: enable integration before application connection
creation, prepare from available schema/dump/seed, exercise one existing behavior,
and add a second isolated test without building a new database environment.

Shared lifecycle proposal:

`enable -> prepare -> close preparation connections -> seal baseline -> acquire child
-> bind application connections -> test -> close owned connections -> close child
-> restore binding -> eventually close baseline`

Each step must have a failure/cleanup counterpart. A failed preparation must not
be presented as a usable baseline. A test assertion failure must still release
owned resources without losing the assertion error. Baseline ownership must
outlive admitted child creation, following the existing contract.

## 2. Entry, connection routing and ownership alternatives

| Option | User experience | Strength | Cost / applicability limit |
| --- | --- | --- | --- |
| Explicit test configuration injection | One helper supplies endpoint/DSN to the application's existing configuration seam | Destination and lifetime visible; naturally scoped | Requires a configuration seam; does not satisfy unchanged settings for every legacy app |
| Framework adapter | Fixture/marker/helper configures a named framework and owns its test pool | Can integrate migrations and teardown with framework lifecycle | Per-framework versions and pool rules need maintained coverage |
| Driver connection interception | Test entry redirects supported driver connection creation | Closest to unchanged application code/settings | Already-created pools, aliases, async tasks and same-process parallel tests need explicit handling; broad global replacement is not automatically sound |
| Stable endpoint/relay | Application keeps endpoint while test DB changes | Candidate for long-lived applications | Port stability alone does not preserve or reset SQL sessions; guest/session replacement requires separate lifecycle design |

These can share a lifecycle core and coexist; they need not become four user
concepts. One-line use means a small test integration entry, not that migration,
seed data or assertions cease to exist. Python and Go may need different
mechanisms to provide the same experience. Do not assume Python interception
translates into arbitrary Go application connection interception.

Questions common to all options: when is binding installed, which connections
belong to this test, what happens to pre-existing pools, how is parallel scope
identified, and what is restored after setup/test/cleanup failure? An unmatched
connection must not silently go to the original application database under an
assumed redirect. Choose its behavior explicitly; this is part of the one-line
entry contract, not an implementation detail for users to discover.

## 3. Preparation alternatives

| Input path | Mechanism to compare | Required explanation and failure behavior |
| --- | --- | --- |
| Existing migration/seed | User callback/command vs framework prepare adapter | When it runs, which endpoint it receives, commit/connection closure, failure stage |
| SQL dump | Existing MariaDB client orchestration vs library importer | Supported dump producer/version/options, delimiters and multi-statement behavior, external client requirement, statement/location failure context |
| Generated data | Existing user loader vs structured SQL/CSV helper | Encoding, types, nulls, transaction/partial load behavior and target schema |

Existing command orchestration can reduce SQL parser work but introduces an
external executable requirement that conflicts with a frictionless library
experience. A built-in importer avoids that requirement but must define SQL
dialect/client directives and partial-failure semantics; splitting on semicolons
is not an acceptable general dump contract. Neither is selected here.
Prepared callbacks and importers should end in the same baseline lifecycle, so
changing the preparation source does not change how the next test is written.
This is importing database contents, not restoring a public saved Snapshot.

## 4. Compatibility and actionable failure contract

Design the information at the boundaries above, before choosing message wording:

| Field | Purpose |
| --- | --- |
| Operation and stage | Identify preparation, binding, connection, SQL, capture or cleanup |
| Stable category and original cause/code | Preserve driver/SQL errors and distinguish a known mariamem restriction from an unclassified failure |
| Observed context | Engine/library versions, selected adapter, test DB identity and relevant capability; omit credentials and sensitive query/data contents by default |
| Action | One concrete next step, with a reason; identify when advice changes the behavior being tested |
| Detail/reference | More diagnostics and version-relevant official compatibility guidance when identified |

Do not infer "application bug" from a SQL error. If a table is missing, report
that fact and known preparation state; the cause may still be schema selection,
preparation, compatibility or an application defect. Generic SQLState 42000
alone does not identify a mariamem unsupported-feature error. Trusted origin
information is needed before giving origin-specific advice.

Three delivery choices remain open: enrich existing typed errors and messages;
add an optional structured diagnostic object/report; or have adapters enrich
driver failures using owned lifecycle context. These can be combined. Preserve
normal driver exception handling and original causes; users/AI should not need
to request each missing fact separately. Official MariaDB references need a
separate version-specific source check before becoming user-facing links.

## 5. Human Review — design direction approved

The Human approved this design direction on 2026-10-18 and requested adding the
existing Snapshot product contract to the cross-check basis. That reference is
included below. Approval advances the source investigation; it does not select
an implementation mechanism or change the lifecycle contract.

Recommendation: retain explicit injection, framework adapters and driver routing
as complementary options until targeted source review determines their scope.
Evaluate them against the same lifecycle and both journeys above, alongside
preparation and error contracts. Stable endpoint remains a separate visible
branch for long-lived apps, rather than a requirement for every test.

The strongest concern is that a one-line entry may hide connection ownership or
leave an existing pool connected elsewhere. Before a spike, specify rejection,
rebinding and cleanup behavior for existing pools and concurrent scopes. This
can change which mechanism fits each language; it does not invalidate the goal.

Next evidence work: inspect the existing application connection seams in the
SQLAlchemy/GORM anchors, then pinned representative routing/framework source
patterns from the kickoff reference list. Record actual API/lifecycle limits
before choosing a prototype. Separately inventory a concrete dump and a migration
path. No new dependency installation or runtime experiment has occurred here.

Basis: [current Go lifecycle](../go.md), [Python fixtures/lifecycle](../python.md),
[Snapshot product contract](../decisions/snapshot-product-contract.md)
(Lifecycle and persistence; Integrity follows ownership),
[pytest implementation](../../python/mariamem/pytest_plugin.py),
[wire capability rejection](../../internal/mysqlwire/wire.go),
[SQLAlchemy explicit engine construction](../../tests/consumer/test_sqlalchemy_dogfood.py),
[GORM explicit DSN construction](../../tests/consumer/gorm/dogfood_test.go).
These support current-state claims, not feasibility proof of the alternatives.
