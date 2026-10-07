# Continuing product decisions

These documents record human decisions that continue to constrain development.
They do not replace the current [Go](../go.md) and [Python](../python.md) API guides,
[current architecture](../v04-generated-go-architecture.md), or exact-source tests.
Accepted target contracts are explicitly distinguished from shipped behavior.

- [Disposable database and reusable initial state](product-contract.md): accepted
  core uses, concepts, Snapshot/Fork naming and documentation responsibilities.
- [Owned Snapshot integrity](snapshot-integrity.md): accepted acquisition and
  ownership contract; production implementation remains to be qualified.

The [Product Contract Audit](https://github.com/masahitojp/mariamem/blob/25a537c9fdb112c89d3e17c69ca078ffc4ad1f82/docs/reviews/v044-product-contract-audit.md)
contains the complete current API/documentation inventories and supporting evidence.
Its Decision 4 API-removal table remains a proposal, not an accepted migration list.
Do not turn every experiment into a decision document; retain historical measurements
in their reports with exact source identities.
