# Unreleased candidate notes

### Owned E2E entry candidate (not adopted)

Adds Python `mariamem.e2e.BrowserEntry` and Go `mariamemtest.NewHTTP/Case(t)`:
preparation once, exclusive sequential Live reset/admission, fresh browser context
or owned HTTP client per case, partial-app cleanup registration and stop after
setup/cleanup debt. These are source-build candidates pending full #18 acceptance
and main adoption. No published version, guest or wire contract is changed.
