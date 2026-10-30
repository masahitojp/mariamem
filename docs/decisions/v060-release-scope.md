# v0.6.0 release scope

Human decision, 2026-10-30. This record states what the 0.6.0 release contains.
It consolidates decisions that are recorded in their own entries; it does not
re-adopt them or replace their receipts. **Publication is not approved by this
record**: the release order below is the 2026-10-29 sequencing decision and
remains in force.

## Subsequent scope correction, 2026-10-30

The Human confirmed that wire-contract establishment is the main 0.6.0 objective.
[P1's fixed exit](p1-fixed-exit-v060.md) preserves entry correctness and cleanup;
detailed resource characterization and tuning move to v0.7.x. Earlier dogfood
resource requirements no longer block 0.6.0. Other inclusion/exclusion and
adoption/publication decisions below remain unchanged.

## D1 disposition,2026-10-31

The Human approved explicit D1 prepared-entry deferral from0.6.0 and consideration
in0.6.1. [Decision](d1-v060-deferral.md) and [Issue43](https://github.com/masahitojp/mariamem/issues/43)
record the obstacle, user impact and remaining work. This satisfies the allowed
D1 disposition branch below, not D1 runtime acceptance. P1/G1/EP1/EG1 and shared
defects remain required; no0.6.1 implementation or publication promise follows.

## Included in 0.6.0

Everything below is already adopted on main and unreleased. Targeting 0.6.0
means they ship together in the first 0.6.0 release.

| Capability | Own decision / receipt | Boundary carried into 0.6.0 |
| --- | --- | --- |
| Stored procedures/functions with bounded DEFINER | [routine scope](routine-support-scope.md); mysql.proc structure owned by the product | Packages/package bodies OUT (not tested, no guarantees); scheduled events OUT (embedded restriction 1235) |
| Server-side prepared statements | [consumer exceptions](prepared-consumer-exceptions.md) | Three named accepted exceptions only; no interpolation or driver forcing; experimental capacity limits not promoted |
| Connection switching (`shadow_maria`) | connection-routing contract; CI40061580952 | Explicit allowed Connector C SKIP on Ubuntu; default/pure required |
| `mariamem.import_dump` (bounded Python dump reader) | [dump reader final review](../reviews/v06x-dump-reader-final-review.md) | Finite MariaDB12.3.3 producer profile; views/triggers and other producers OUT; no Go dump API |
| Internal MariaDB status projected to 16-bit protocol flags | main commit `02b58b3` | Engine-internal bit 16 never crosses the wire; existing framing bounds unchanged |
| Live stable endpoints for sequential E2E | [Human decision](../reviews/v06x-live-main-adoption.md); PR1 merge `212bb07` | **Human placement decision, 2026-10-30: Live is part of the 0.6.0 scope.** Quiescence and physical SQL session retirement remain required before `Reset`; delayed jobs/session continuity/parallel shared Live are outside the first contract |
| Go 1.26.10 toolchain (GO-2026-6809 remediation) | P6 record; forward-compat pin 1.27.3 is not a 0.6.0 PASS | Minimum Go stays 1.26.0; the 1.27.3 external-consumer check belongs to later Qualification |

## Release prerequisites (2026-10-29 sequencing decision)

Acceptance tracking: [#18](https://github.com/masahitojp/mariamem/issues/18) owns
the five dogfood entries; [#19](https://github.com/masahitojp/mariamem/issues/19)
owns the separately declared dbt workload, not a sixth dogfood entry. See
[current work tracking](../project-status.md#current-work-tracking) for disposition.

1. Complete the five named dogfood entries (P1 Python pytest/`shadow_maria`,
   G1 Go helper, D1 Django, EP1 Python browser E2E, EG1 Go HTTP E2E) with the
   declared-profile acceptance campaign on both supported hosts — or record the
   concrete D1 deferral obstacle and remaining work.
2. Then version/notes (`NOTES-v0.6.0`), final Qualification of the exact
   0.6.0 candidate, Product Validation and publication — each its own gate.
   The dogfood acceptance campaign is not Qualification, and neither is
   component PASS, unit tests or single-platform runs.

## Explicitly not in 0.6.0

- v0.7.x scheduled work: guest-initialization optimization candidate selection,
  large-scale tuning including the preparation-heavy/100 MiB workflows (the
  100 MiB Go Fresh investigation stays closed until recurrence), and the
  config/host levers before guest patches.
- Live extended contract: automatic pool retirement, physical session
  continuity, job fencing, parallel shared Live and W8 resource bounds.
- Dump reader profile extensions (views/triggers, other producers, large-input
  performance) and prepared OUT commands (COM_RESET_CONNECTION, server-side
  cursors, packet continuation, capacity raises) until demand and a design
  justify them.
- Scheduled events and packages: OUT per their separate reasons; reversing
  either needs a new Human scope decision.
- The shared-memory purge-order premise remains an accepted stated limitation;
  resolving it is not scheduled into 0.6.x.

Usage documents (README, docs/go.md, docs/python.md, docs/live.md) must, at
publication time, describe exactly this scope: adopted features as supported,
the exceptions as named, and nothing from the excluded lists as implied.
