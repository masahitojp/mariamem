# Current fixture-contract wire inventory — prepared output

Inspected source_commit d8f66d9a5605b3b738b2175268a3734ee1c89a4a.
The [previous Issue94 inventory](issue94-wire-inventory.md) retains its source
and bounded pipeline/disconnect contract. That contract, command/capability sets,
input sequencing and session ownership remain the fixture baseline.

Within the four-file boundary checked by the fixture lint, only resident.inc
changes from the prior inspected baseline: Ready advertises private prepared
protocol version2 instead of1. wire.go, prepared_session.go and wire_core.inc
retain the recorded bytes. The full output change is broader than this inventory:
prepared_api.inc copies raw cached rows, and the host raw-row receiver/validator
uses that version. Those changed boundaries and runtime acceptance are tracked
by#134/#132 and the prepared-output-product reports, not proven by this lint.

The current source pin/checksums are reconciled without changing any fixture
oracle, capability or admission policy. Old/new private protocol rejection,
full-chain validation, malformed hidden OUT, ownership and packet/frame limits
remain required. No additional architecture or release is authorized here.
