# v0.4.4 Product Contract Audit: discussion status

Status: exploration; Decisions 1–6 are not adopted.

The maintainer clarified that discussion remains insufficient and no product
decision has been made. Earlier assistant records interpreted support and
"proceed" as adoption. Those records were incorrect and are withdrawn.
Do not use `d3620f5189cc4b06f3a25bc8d0fc7a711e0cc0cc` as adoption authority.

Current user-facing documents have been restored to the audit main baseline
`c8bd25a56e9d5221abaf40b2c98102bd60c217ae`. The prior documentation cleanup is
withdrawn as an implementation/alignment change. Git history preserves the draft;
review documents below are discussion material, not current user contracts.

- [Product model proposal](v044-product-model-proposal.md).
- [Owned integrity proposal and existing PoC evidence](v044-owned-integrity-proposal.md).
- [API alignment explanation](v044-api-alignment-explained.md).
- [Original audit](https://github.com/masahitojp/mariamem/blob/25a537c9fdb112c89d3e17c69ca078ffc4ad1f82/docs/reviews/v044-product-contract-audit.md).

The fixed PoC assumptions and previously collected measurements are evidence;
they are distinct from adopting a production contract. No runtime code or API
was changed, no OwnedPrepared merge occurred, and no release is authorized.
Continue one question at a time with concrete behavior, source evidence and
code examples. Distinguish constraints from recommendations; make no adoption
record or implementation change until the maintainer explicitly decides it.
