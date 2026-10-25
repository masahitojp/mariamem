# Dump spike SQLSTATE and experimental host exit gate

The Human requires an exact reader SQLSTATE assertion before closing this spike
as comparison complete. Source9494e755a5e7d79a9702e1d1dc7c1caae993e801 and
CI40192797648 remain the earlier observed PASS; their receipts are not relabeled
as evidence of this stronger gate. No productization decision follows here.

The reader sql_failure classifier now requires errno1146 **and SQLSTATE42S02**,
in addition to phase, cause, original-file span, partial DDL, cleanup and no
Snapshot/test admission. Focused mutation tests accept the correct state and
reject HY000,42000 and absent state for both reader and native routes. The
existing bounded CI executes those tests, then the same fresh producer/binding,
native references, guest native client, reader, two-child and failure matrices
on Ubuntu x86_64/macOS arm64 and Python3.11/3.14. SQL corpus and runtime stay
unchanged from9494e75.

## Experimental host dependency, not adoption

Every spike PASS is **conditional on the experimental host correction** first
introduced in9494e75 after5a9661d failed. Host adoption remains a separate
post-spike decision. The
[delta manifest](../../tests/dump_import_spike/approved-host-delta.json) records
the full before/after SHA256s and the status contract. Binding verifies the same
three allowed runtime files and their hashes; this gate does not widen them.

| File | Before SHA256 | After SHA256 |
| --- | --- | --- |
| internal/guest/guest.go | 77b696866b1cb1e3015389519ba4a74b2aeb62977aec18c1b44d157e2094db54 | 9927caadd560d36f54f39d683fbfd2874c64857cdced63662fef0554b1fc54d0 |
| internal/guest/status_test.go | absent | dda4dd3dc5209ac183677faba9ae508d9c9576ee37ae2f3506b56c9241d8694c |
| internal/mysqlwire/status_decode_test.go | absent | 5f010095915f8d95eff890ca93f38fa3587e92fdf627b9ea2dc88a6ddce19fd1 |

The input domain is an unsigned32-bit integer,0 through4294967295. Protocol
status is the low16 bits; all existing protocol flags are preserved, including
transaction/autocommit, MORE_RESULTS, cursor/last-row and prepared OUT flags.
Internal RETURNED_ROW does not escape onto the wire. Negative, fractional,
out-of-range, nonnumeric and explicit-null input is rejected; missing status
remains zero for startup envelopes. Nested results use the same validation;
failed decoding does not partially replace a Result. Existing guest-decoder
and text/prepared wire regression checks run in the bounded CI on both hosts.

## Exit decision

Close the spike as **comparison complete** only after the new exact-source
bounded CI passes and its independently checksummed receipt is saved, with this
experimental delta recorded. Until then the stronger exit gate is open.
After closure, a separate spike review chooses library / external client /
defer / productization and separately assesses host correction adoption.
No route/productization/main/Qualification/release decision is made by this
gate. Views/triggers, cold Mac and setup-cost remain outside scope.
