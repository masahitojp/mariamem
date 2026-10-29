# Wire inventory reconciliation for G1 integration

The original [wire inventory](v06x-wire-current-inventory.md) is preserved at
its historical source `cc00ccd98e29a1f5d5088a082be90a3cdaa4f469`. For the active
fixture contract, source `437d74d9d11d8dc2a03dc94bba0d37346131ebff` is inspected.
The intervening wire change checks `p.Err()` before command dispatch and routes
a fatal worker error to `commandFailure`; it changes no supported command or
capability set. It comes from the adopted [worker-failure repair](issue5-main-adoption.md).
The prepared-session and guest wire files are unchanged. The contract lint
compares all four files with that source and checks dispatch and capability bits.
This source comparison is not a new protocol or G1 runtime PASS. The G1
integration candidate requires fresh both-host receipts.
