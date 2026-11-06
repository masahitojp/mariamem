# Issue65 — native wire contract decisions

Human decision,2026-11-06. The Human accepted all three recommendations from the
[proposal at a1dfa69a](https://github.com/masahitojp/mariamem/blob/a1dfa69a4727fcedcd4b5a7ba46b8acb0fa1a610/docs/design/issue65-native-protocol/contracts.md)
after clarifying the worker/owner boundary and the effect on SQL clients.
This approves the future native endpoint's contract choices, not completion of
compatibility testing, main integration, a release or controller relocation.

## Accepted choices

| Decision | Accepted behavior |
| --- | --- |
| D1 — fatal established-session failure | Host closes every transport for that instance. SQL clients observe connection loss/EOF, with driver-dependent wording; no server ERR2013/HY000 containing the original cause is promised on an established native stream. The owning mariamem object/management diagnostics retain the original cause and cleanup disposition. |
| D2 — named malformed EXECUTE exception | For the investigated length-encoded string declaring more bytes than remain, follow the pinned MariaDB native decoder's observed empty-string acceptance. Do not implement a second Go parameter decoder. This does not authorize accepting every malformed input or weakening other packet bounds. |
| D3 — obsolete representation envelope | The native streaming route removes the old JSON/typed bridge's32MiB internal envelope limit. Existing client SQL, command and individual response-packet bounds remain separate requirements. No replacement aggregate byte limit or bounded total SQL/RSS guarantee is introduced. |

For D1, “worker” includes translated guest execution inside the host Go process;
a fatal worker/instance failure is distinct from ordinary SQL errors or idle
client retirement. “Owner” is the host-side mariamem object responsible for an
instance's lifetime and disposal, such as the DB resource owner behind Go
`mariamem.Start`, not the SQL user, `database/sql` pool or ORM. Details must be
observable through the management/error interface of the actual public route;
the isolated experiment does not yet establish that API wiring.

Ordinary SQL errors continue to return native ERR with their errno/SQLSTATE and
following-command behavior. Pre-login bounded fixed capacity/unavailable
rejection remains a separate known boundary. Independent instances retain their
isolation. Wake pending I/O promptly, preserve first cause and cleanup failures,
and never free storage still owned by running workers. EOF is not proof that
cleanup completed or capacity can be released.

## Ownership direction and remaining conditions

Prefer host lifecycle/resource policy: connection reservations, identities,
transport queue policy, Live generations, Fork leases and cleanup ownership.
Keep authoritative native session state and the atomic SQL/capture gate in guest.
The [responsibility table and acceptance profile](../design/issue65-native-protocol/contracts.md)
make the boundary and unchanged profile requirements explicit.

Substantial custom C++ controller reduction is a design target, not a measured
result or an approval to remove native lifetime/admission mechanisms. MariaDB's
C/C++ remains; thin memory-Vio/THD/NET/lifecycle hooks remain necessary unless a
later bounded proof establishes a replacement. No cgo or new shim is selected.

Carry D1–D3 into the native compatibility experiment with exact source/guest/client
identities and named oracles. In particular, verify raw prepared/login/capability
paths, capacity rejection, full-window overflow and continuous EOF monitoring,
output-packet limits and large aggregate streaming. The prior Linux/Live PASS
retains its original scope; it does not close these conditions.

Stable product behavior and legacy tests are unchanged by this documentation
commit. Preserve legacy regressions until the approved native contract is
implemented with replacement native-path coverage; do not remove them merely to
accept the fixture. Future user guides and public/source-contract CI must reflect
the actual integrated implementation, not this decision alone. No version or
publication is selected.
