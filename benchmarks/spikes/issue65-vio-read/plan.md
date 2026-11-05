# Issue65 — read framing only

Human authorization2026-11-05: proceed with step1 only. Reuse the isolated
NET/Vio source-extraction style; no SQL, THD, prepared or coherent server build.
Question: does the pinned upstream read/framing code work with memory Vio,
including malformed/partial inputs and uncompressed0xffffff continuation?

Fixed inputs: MariaDB12.3.3 commit83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e,
three source hashes from the previous send seam; baseline product47121e1.
Profile: EMBEDDED_LIBRARY defined, MYSQL_SERVER unset (as net_serv.cc does for
embedded), HAVE_COMPRESS undefined, pkt_nr_can_be_reset0, retry0, no extensions.
Native client-side previous-sequence ERR exception must be observed honestly;
this profile is not proof of the full native server command path.

Exit: exact reconstruction under short reads, multiple packets, sequence mismatch,
0xffffff+continuation, exact0xffffff+empty terminator, missing terminator/EOF,
configured buffer growth limit and header/body EOF. Preserve raw errors and
source identities. Test the upstream code rather than a rewritten packet reader.
No change to the product's1MiB budget or advertised continuation support.

Budget: active20 minutes, harness tooling at most10 minutes, heavy CI0,
compile/run outer timeout90s, own disk1GiB/free8GiB, CPU1 and memory512MiB.
If complete-header/engine dependencies are needed, stop rather than expanding.
Preserve code/compact evidence in the experiment branch and clean owned copies,
compiler output, container and worktree. Existing four user changes stay untouched.
