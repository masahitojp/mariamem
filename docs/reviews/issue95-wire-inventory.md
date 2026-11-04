# Wire inventory reconciliation for Issue95

Inspected source_commit `04245cc5851e8236b118c840a6679f3c038480a0`.
This is the active fixture-contract wire inventory for the last-statement alias
candidate. [Issue78's inventory](issue78-wire-inventory.md) remains the historical
credential-change record at source9a667656; its original evidence is not relabelled.

The four-file fixture boundary changes only `internal/mysqlwire/prepared_session.go`.
`internal/mysqlwire/wire.go`, `guest/wire_core.inc` and `guest/resident.inc` are
unchanged. The complete candidate also updates the executor and long-data caller
and reserves the alias ID in the host registry; the candidate diff and focused
Go tests own these additional files. No guest patch or generated source changes.

`0xFFFFFFFF` resolves to the current connection's last successfully installed
binary prepared statement. Every new PREPARE attempt invalidates the alias until
metadata and the owned mapping are installed. SQL/length/transport/metadata
failures do not fall back to an older statement; existing actual IDs remain owned.
Closing the latest statement invalidates its alias without fallback. Executing
or closing an older actual ID does not retarget the alias. Each physical session
starts independently, and the registry never allocates the reserved alias ID.

EXECUTE,RESET,CLOSE and LONG_DATA resolve through the same owned ID. Bind types,
long-data presence and deferred errors remain keyed by that actual mapping.
As in native12.3.3, alias EXECUTE with parameters requires new type descriptors;
actual-ID execution can still reuse the descriptors consumed through an alias.
RESET clears streams/deferred errors without losing the alias; CLOSE retires
mapping and caches. Unknown CLOSE/LONG_DATA retain their no-response behavior.

Supported command numbers remain1,2,3,14,22,23,24,25,26,27. Base capability bits
remain `1|4|8|512|8192|32768|65536|131072|524288`, with PS_MULTI_RESULTS conditional
on validated support. The alias needs no new capability bit: native12.3.3 accepts
it with the existing classic PyMySQL handshake; the inspected native lookup has
no capability gate. This does not implement COM_MULTI,bulk execute or pipelining.
The remaining command/capability gaps and resource/capture contracts are unchanged.

Native26-case sequential lifecycle controls and the candidate's matching controls
are saved with the [Issue95 acceptance record](issue95-last-statement/README.md).
`prepared_alias_test.go` covers ownership,prepare failures,type/cache/stream cleanup
and session isolation; `registry_test.go` covers the reserved-ID boundary.
Default-pipelining Prisma still needs Issue94; alias acceptance alone does not
qualify normal pipelining or overall Node support.

The first daily Python run correctly rejected the old prepared-session source
hash. The active source/hash pin now points to the inspected candidate, and the
lint continues validating working bytes against that actual commit, command/cap
sets and negative mutation controls. This is inventory bookkeeping, not new
runtime/fixture adoption, release qualification or publication approval.
