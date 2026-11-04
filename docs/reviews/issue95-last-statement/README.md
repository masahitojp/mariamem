# Issue95: connection-local last-statement alias

Runtime candidate source_commit: `04245cc5851e8236b118c840a6679f3c038480a0`.
Main base: `df75666e3e46f6ebd4e2541c89586ad7b43275f9`.
The [environment](environment.json) and [runtime identity](runtime.json) record
the native image ID/digest, driver pins, actual clean Go VCS stamp and host hash.
Later inventory/evidence commits do not change this runtime/test tree.

The candidate implements MariaDB `0xFFFFFFFF` as a physical-connection-local
alias for the last successfully installed binary prepared statement. It reserves
that wire ID, resolves EXECUTE/RESET/CLOSE/LONG_DATA through the same owned mapping,
and shares that mapping's bind/long-data/deferred-error state. Alias execution
requires fresh parameter descriptors; actual-ID execution can reuse its cache.

Any new PREPARE invalidates the alias until metadata is installed. SQL/local-length/
transport/metadata failures never fall back to older handles. Closing the latest
statement invalidates the alias; closing/executing an older actual ID does not
retarget it. Sessions start independently. Commands, capabilities, guest/generated
code and query-time disconnect/pipelining monitoring are unchanged.

## Native and candidate controls

[Native12.3.3](native.json) and [candidate macOS arm64](candidate.json) have the
same26 checks and expected results, with healthy following SQL. These are
sequential commands; PREPARE responses are consumed before EXECUTE is sent.

- Alias before prepare, after failed prepare and after close returns1243.
- Latest prepare wins; older explicit IDs remain usable and cannot revive or
  retarget the alias. A new successful prepare restores the alias.
- Alias parameter-type reuse returns1835; explicit-ID reuse of types sent via
  alias succeeds. This detail comes from native direct-execute sanity checking.
- RESET preserves the alias and clears long-data/deferred errors. LONG_DATA and
  alias EXECUTE use the same target; CLOSE retires its actual mapping and caches.
- Other physical connections have their own independent alias.
- Canonical zero-parameter alias EXECUTE succeeds. A duplicate-key SQL error
  does not retire the alias; another correctly typed execution succeeds.

The classic PyMySQL handshake is sufficient in the native controls; no new
MariaDB extension-capability negotiation is needed. The pinned native source
[find_prepared_statement](https://github.com/MariaDB/server/blob/mariadb-12.3.3/sql/sql_prepare.cc)
uses the alias without a capability gate; its direct-execute sanity check
requires fresh descriptors for positive parameter counts. The
[protocol](https://mariadb.com/docs/server/reference/clientserver-protocol/3-binary-protocol-prepared-statements/com_stmt_execute)
defines the alias and invalidation after a failed PREPARE. Native allocation-OOM
behavior was not injected; host-side publication failures conservatively leave
no alias. COM_MULTI,bulk execute,cursors and general pipelining are not added.

## Prisma condition: still open behind Issue94

Node24.22.1, Prisma/client/official adapter7.10.1, mariadb3.5.4. The exact prior
Prisma probe/lock source is `604a0c588f0a602bf6ea67d811b97bae2748c3ea` under
`benchmarks/spikes/prisma-dogfood`. [Native Prisma](prisma-native.json) passes
both target cases with default pipelining. [Candidate Prisma](prisma-candidate.json):

| Mode | nested create | expected duplicate-key handling |
| --- | --- | --- |
| pipelining:false | PASS | PASS |
| pipelining:true | FAIL2013 | FAIL2013 |

Both remaining failures report "unexpected client input during running query",
Issue94's existing abort policy. Alias lookup is independently accepted by the
26-case comparison, but these failures can mask later default-mode behavior.
Thus this is an alias implementation candidate, not normal-pipelining Prisma
acceptance. **Issue95's final Prisma checklist item remains open until Issue94
is fixed and these normal operations are rerun.** Issue93's optional zero-parameter
flag fix is a separate PR and is not copied into this main-based candidate.

## Reproduce

Use [alias_probe.py](alias_probe.py) with `--source REPO --port PORT --output JSON`
on a fresh native/candidate endpoint. It creates only disposable test schema/data;
all26 commands wait for previous responses and do not test pipeline support.
The run used Linux arm64 native MariaDB12.3.3 with a tmpfs data directory and a
local-only published port. The container was removed afterward; the pre-existing
image was retained.

Build a clean candidate after `scripts/git_identity.py inspect HEAD`. This run
used Go1.26.10 and a standalone clone with `go build -trimpath -buildvcs=true`
for a real source stamp. Start that host with the source Python package and pass
its endpoint port to the probe. [prisma_probe.py](prisma_probe.py) takes
`--source REPO --prisma PRIOR_SPIKE --output JSON` plus either `--host HOST` or
`--native-port PORT`. Restore the pinned prior spike, install its lock with
`npm ci --no-audit --no-fund`, and generate the Client with a throwaway DATABASE_URL.
Native mode recreates prisma_matrix only in the disposable native DB. Candidate
mode verifies the stamped host and starts an independent instance per case.

Focused complete preparedproto/mysqlwire tests pass. The regression first failed
against the base registry/dispatcher. They cover prepare failures, metadata
unwind, alias-cache ownership, stream/reset/close behavior, and reserving the
last ID without wrap/reuse. No heavy Release CI or permanent Node job is added.
Full hosted/platform/installed qualification, publication and performance remain
separate. The active fixture inventory is reconciled in
[issue95-wire-inventory.md](../issue95-wire-inventory.md); prior inventory records
retain their original source and evidence context.

## Final local checks

[Validation](validation.json): canonical daily check passes at inventory commit
`efb357e9c1f79e14bc78c5c5fd50015e7e77cfad` (runtime/tests identical to04245cc5).
The main Python phase is1847 passed/92 skipped; source oracles run separately.
The failed initial inventory run is not relabelled as PASS. Reconciled fixture
contract tests24/24 and the full canonical daily rerun both pass. Python/Go Live
source smoke passes on runtime04245cc5, preserving capacity timeout,busy and
closed-parent refusals. Optional skipped profiles and both-platform Release
qualification are not implied. Evidence-only changes after these checks do not
alter the runtime/test candidate or the reconciled inventory.
