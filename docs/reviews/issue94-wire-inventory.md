# Wire inventory reconciliation for Issue #94

Inspected source_commit `e1eb9c2f6395413aef7444dccdd300b0d083798f`, based on merged Issue #93 and Issue #95.
This is the active fixture-contract wire inventory. [Issue #95's inventory](issue95-wire-inventory.md)
retains its original sequential alias evidence and source pin.

The four-file boundary changes only `internal/mysqlwire/wire.go`. Prepared-session
ownership, `guest/wire_core.inc` and `guest/resident.inc` are unchanged from the
previous inventory. No guest patch, generated source or capability changes.

The disconnect monitor now retains pending input, up to 1,048,581 raw bytes per
physical connection, while the current guest operation runs. The dispatcher still
executes commands and writes responses serially. Pending headers and payloads
are consumed through the same framing, sequence and admission checks. The reader
is joined before the dispatcher resumes. EOF still aborts the instance, including
when pending input fills the buffer; one further byte fails closed with the
explicit buffer-limit cause. Other DB instances remain independent. This is the
[Human-approved bounded policy](../decisions/issue94-bounded-pipeline.md), including
the accepted risk that larger valid bursts abort the affected DB instance.

Supported commands remain 1,2,3,14,22,23,24,25,26,27. Base capability bits remain
`1|4|8|512|8192|32768|65536|131072|524288`, with PS_MULTI_RESULTS conditional on
validated support. This does not add COM_MULTI, bulk execute, RESET_CONNECTION,
parallel SQL execution or blanket Node ORM support. Existing remaining-path and
resource/capture contracts are unchanged.

`internal/mysqlwire/pipeline_test.go` covers buffer bounds, ordered framing,
partial frames, EOF, overflow, sequence validation, admission and reader joining.
`tests/test_python_wire.py` adds real TCP ordering, malformed-sequence and
EOF/overflow/owner-close controls with independent roots. Real-host cases keep
the existing runtime opt-in gate; daily source checks do not establish that
acceptance. The fixture lint continues checking actual bytes against this commit,
command/capability sets and negative mutations. No oracle is relaxed.
