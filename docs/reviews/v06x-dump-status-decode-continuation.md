# Approved bounded host status correction

The Human approved the host-only correction proposed after failed comparison
source_commit `5a9661d821150b3992466fa49a071a213cbaab78`, CI40188523035.
The failure review is preserved in design-branch commit
`7b098b57ffa37ee0b2ce37297fa28f54f711d3aa`. This approval permits the bounded
decoder correction, focused regressions, explicit input-binding delta and the
unchanged dump comparison rerun. It does not approve productization, main
integration, Qualification or release.

`internal/guest/guest.go` now decodes internal server_status as unsigned32-bit,
then projects its low16 protocol bits into the existing Result.Status field.
Nested Result values use the same decoding. Missing status remains valid for
startup envelopes; explicit null, negative, fractional, nonnumeric and values
beyond uint32 are rejected. A failed decode does not partially replace a Result.
Guest serialization and network packet code remain unchanged.

Regression tests cover the observed65538, transaction/autocommit/more-results,
cursor/last-row flags, uint32 limits, invalid input and nested values. Text
multi-result OK packets retain their exact status bytes. A prepared chain with
internal RETURNED_ROW added to every status produces the same packets as the
existing pinned native fixture. CI runs both affected Go test packages on both
observed OSes before the comparison campaign.

The [approved delta manifest](../../tests/dump_import_spike/approved-host-delta.json)
pins before/after hashes for the decoder and its two regression files. Binding
requires this exact runtime file set and hashes in the candidate and working
tree. Mutations of those files or extra guest/generated/command/build paths are
rejected. Canonical application.sql, its original source manifest, migration
inputs, producer options, definer routines and comparison/failure oracles remain
unchanged. Each new candidate must still reproduce the canonical dump bytes with
its own fresh producer and rerun the native references before guest routes.

Local verification on Mac arm64: Go1.26.10 guest/mysqlwire package tests PASS;
Python3.14/pytest9 binding/framing/classifier tests32 PASS; existing acquisition
unittests25 PASS; public source check and diff whitespace check PASS. These
focused checks are not a successful application comparison. The new exact-source
CI must establish guest routine behavior, full semantic comparison, subsequent
SELECT, two-child behavior and failure controls on both OSes/Python versions.
No cold-host/setup-cost, views/triggers or broader format support is claimed.
