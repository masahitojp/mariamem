# Prepared consumer exceptions — Human accepted, P6 remains open

On 2026-10-22 the Human explicitly accepted the two limitations below after
[P5 Human Review](../reviews/v06x-prepared-p5-human-review.md) and the
[successful MariaDB-driver replay](../reviews/v06x-prepared-mariadb-results.md).
This accepts the bounded exceptions and permits proceeding to the already
scoped P6. It does not approve main adoption, target version, Qualification,
Product Validation or publication.

## Decision and scope

**P5 evidence is complete with accepted consumer exceptions.** This is not an
unconditional functional PASS. Original consumer failures remain failures;
native matching, successful other-driver observations and Human disposition
are separate facts. Earlier CI receipts whose human_disposition says PENDING
remain immutable records from before this decision; this document owns the
later acceptance.

| Exception | Accepted user-visible consequence | Proven boundary |
| --- | --- | --- |
| Oracle mysql-connector-python26.7.0: prepared CALL emitting two result sets via nextset | First set is received, advancing fails, and the subsequent SELECT on that connection fails | Pure on both supported guest platforms and Mac C/default, with matching native MariaDB12.3.3 observations. Do not generalize to every CALL, text routines or every driver |
| Same version, Mac C/default: untyped prepared character projection of bytes410042 | Returned Python character value is A instead of A-NUL-B, without a useful error | HEX/length show all3 input bytes; explicit binary cast and typed VARBINARY storage/read preserve them. Pure preserves the projection. No conclusion of guest database file corruption |

No root-cause claim that either is a universal driver defect is accepted.
MySQL-server behavior has not been established. These exact workflows cannot
be advertised as working one-line switching with this client combination.
Do not force a different driver, pure mode, SQL interpolation or application SQL
rewriting to report an unsupported path as successfully implemented.
The earlier accepted Mac C syntax-error presentation is a separate, unchanged
disposition in [production design §6](../reviews/v06x-prepared-product-design.md).

## Evidence bound by this decision

- Reviewed prepared candidate source_commit
  `c5dddf36aac2d62cfe8d4edd22b41fb8da7fdd9b`,
  [CI39769591459](https://github.com/masahitojp/mariamem/actions/runs/39769591459):
  both-OS native matching and existing installed/ORM regressions PASS, original
  Python functional FAILs retained.
- Added MariaDB replay source_commit
  `4ce9422e8b5a49727f9a1e3ee81706545e4a8f0d`,
  [CI39776208952](https://github.com/masahitojp/mariamem/actions/runs/39776208952):
  all six jobs PASS, with the same Oracle limitations retained.
- MariaDB Connector/Python1.1.14 binary execution passes both cases, following
  SQL and cleanup on actual Mac/Ubuntu guests and native12.3.3. Go driver1.9.3
  passes the corresponding prepared value/result cases. Neither result repairs
  Oracle Connector/Python or establishes every other driver/API combination.
- Guest SHA256 in these development candidates:
  `8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`.
  These are not canonical generation or Qualification receipts.

The raw JSON, exact client versions/hashes, environment SKIPs and source-bound
host identities remain linked from the reviews. Ubuntu's additional Oracle C
mode import failure is an explicit allowed SKIP, not C compatibility PASS;
required default/pure actually executed.

## Conditions carried into P6 and adoption

1. Keep the original strict functional failures and exact native payloads;
   distinguish an accepted exception from PASS or a newly different failure.
2. Add deterministic comparison of the detailed edge captures, including
   subsequent-query and cleanup outcomes, with mutations proving changed
   values/errors cannot pass. Preserve native/client profile binding.
3. Complete canonical ownership, fixed-input independent Wasm builds and Go
   regeneration, exact lifetime/data/J1 rebinding and failure controls,
   license/provenance/source inventories and release guards. Choose durable
   normal-CI placement for selected consumers. Do not hand-edit Generated Go.
4. Before main adoption, align the public guides with tested prepared support
   and these precise version-specific exceptions; avoid blanket claims that all
   prepared or one-line-routing workflows work. Keep the positive MariaDB replay
   scoped to its two tested cases.
5. Driver/engine/toolchain changes require rechecking applicability. This is not
   blanket approval of future errors, missing results or truncation. Any new
   difference outside these observations returns for diagnosis and disposition.

P6 implementation and evidence remain unfinished. Main integration and release
remain separate Human decisions.
