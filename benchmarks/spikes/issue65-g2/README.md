# Issue65 G2: fixed-guest metadata,result chains and representative state

Human continuation after G1 CI42316326944,2026-11-07: proceed to G2.
Observe fixed guest/checked host source_commit
`65b49e3dc31e9b2da63b317e015f8f471e79a83e`,guest SHA256
`7103c8116151a386b1359e9ea02fda7e31fe8145f37a221001f97e7de2ce9a91`.
Binding and runtime remain those confirmed by G1. Frozen main remains61973daa.
This task observes;guest repairs,new exceptions,controller relocation,public
adoption and release are separate. Original mismatches must remain visible.

Budget:active2h/tooling30min,local native plus at most one Linux CI;
owned builder/runtime12GiB each,free floor12GiB. Reproduce the guest once,repeat
the strict G1 baseline,then add exactly one pinned G2 Go test source and compile
a separate binary. Full inventory must be baseline plus that one file before
and after execution;the baseline binary also remains unchanged. G1 reference
comparison retains its explicit one-line capture-debt idle synchronization.

## Named observation set

11 groups,241 named observations,required in full. Missing cases,duplicates,
SKIP,timeout or failed metadata reachability/setup preconditions cannot pass.
A completed contract mismatch is NOT_READY. Failed setup remains INCOMPLETE,
with observed mismatches retained separately. No candidate-output oracle refresh.

| Group | Finite set | Observations |
| --- | --- | --- |
| PREPARE metadata | existing P1 six cases,140 descriptors,exact raw packets/warnings,following PING |12|
| Typed values | existing19 raw vectors,signed/unsigned,NULL,float/decimal/string/blob/temporal;fresh/reused descriptors and PING |57|
| Additional types | existing P2 matrix13 type cases,exact native metadata/row/terminal on fresh/reuse,following PING |39|
| CALL chains | all14 existing P3 cases:zero/one/several/129 results,IN/OUT/INOUT/reuse,metadata change,initial/later SQL errors,PS_MULTI_RESULTS on/off;full trace,following SQL and CLOSE/PING |48|
| LONG_DATA | six captured native cases plus malformed descriptor after pending data,reset/fresh/following state |17|
| CLOSE/RESET bodies | lengths0..5,zero-extension/surplus,unknown handles,no-response adjacency |18|
| Text multiple statements | handshake-enabled,SET_OPTION on/off,terminal status and following SQL |8|
| Normal metadata names | ASCII/unicode255-byte aliases and64KiB literal label,unaffected value and PING |9|
| Large metadata | table-alias4096 reachability control,internally generated SQL at exact/max+1 packet size,following PING |8|
| Login/session | initial DB,unknown DB,short fixed header,truncated auth,explicit charset;peer/state checks |10|
| D1 representatives | partial body,mid-output native prefix/EOF,buffered future commands;peer EOF,owner cause,independent root,cleanup |15|

[Oracle inputs](oracle-inputs.json) pin the existing native captures and their
probe source. The fixture embeds their original packet bytes;setup explicitly
uses their utf8mb4_general_ci,sql_mode and UTC settings. It does not compare new
UCA defaults to old capture defaults accidentally. Error text containing opaque
IDs is retained but only the previously promised errno/state is asserted for
lifecycle handles. New helper workload bounds(160 results/128 columns/2000 rows)
are test bounds and cover the129-result oracle;they are not product ceilings.

Metadata's [source audit](metadata-reachability.json) distinguishes short normal
column names from table aliases and internal SQL. SQL packet1MiB does not itself
bound a statement constructed in a server variable. The large-metadata probe
first verifies alias4096,derives actual descriptor overhead,then uses SQL PREPARE
from a variable to reach exact0xfffffe/max+1 without sending oversized client SQL.
If prepare/reachability is unavailable,it is INCOMPLETE,not accepted impossibility.
Normal and large metadata capture only sizes/content checks in logs,not16MiB
copies. Temporal modes beyond selected vectors,dynamic SQL combinations and
other unobserved paths are not inferred PASS.

D1 output fixture uses known40x1MiB rows,reads a native prefix,waits for the actual
owner cause,and validates remaining row bytes until EOF while allowing a final
truncated native packet. It forbids a host-injected ERR or a reply to a queued
future command. This finite workload is not a new aggregate or RSS guarantee.
Every OPEN remains within the fixed100..10000ms prototype envelope. Public30s
and owner API integration remain P1;declared consumers/performance remain P2.

## Reproduction

Use Python3.14 and Go1.26.10,owned workspaces at source65b49e3d. Rebuild the fixed
guest with the G1 repair probe's native-arm64 `build` stage and transfer its
verified development artifact. Then run:

```sh
python3.14 benchmarks/spikes/issue65-g2/probe.py local --workspace "$HOST_WORK"
# Hosted native Linux x86_64:
python3 benchmarks/spikes/issue65-g2/probe.py runtime --workspace "$HOST_WORK"
```

The existing workflow file targets experiment/issue65-g2,with native Linux arm64
guest build and x86_64 execution. Retain raw logs/results even on NOT_READY,dispose
SDK/converter/generated code/binaries/caches/worktrees and transit,then hand off
exact SHA/run URL/operation and stop. Linux execution has not been observed yet.

## Native macOS observation,2026-11-07

Fixed guest7103c811 was reproduced. At tooling source_commit
`18c546b2e3ad431c9383ab7fe198a8a9c0b02bae`,all241 G2 observations completed:
230 PASS,11 contract mismatches,0 missing. The result is **NOT_READY**.
[Original result](evidence/macos/g2-result.json) and [raw log](evidence/macos/g2-suite.txt)
retain every expectation and actual outcome. No oracle,guest or acceptance
exception was changed to obtain this result.

| Remaining difference | Observations | Expected / observed |
| --- | --- | --- |
| BIT16,GEOMETRY255,INT24 9,YEAR13 input |8| original native rows on fresh/reuse /1835 HY000 |
| LONG_DATA with wrong LONG type |1|1210 HY000 /1835 HY000;following fresh execution recovers|
| Pending LONG_DATA after rejected descriptor |1|stream retained /cached execution1835;fresh execution recovers|
| Short fixed handshake header |1|legacy1045/28000 /native1043/08S01 Bad handshake|

These are observed differences;the precise patch causes have not been isolated.
The short-header result needs a contract decision or a scoped compatibility fix;
it is not silently accepted as another exception. Four type failures are eight
fresh/reuse observations,not eight independently established bugs.

All named metadata,19 typed-value vectors,CALL chains(including129 results),
CLOSE/RESET,text multi-statements and three D1 fatal-state workloads pass.
Large table-alias metadata is reachable through internal SQL:exact0xfffffe bytes
passes,max+1 produces1153/08S01 before an oversized header,and following PING
works. Normal255-byte column-name truncation is not a general packet-size proof.

The unchanged strict baseline passes22 lifecycle,88 compatibility,38 limit and
234 G1 observations,plus existing controls/supporting checks. The283-file G1
reference comparison retains its explicit capture-fixture idle adjustment.
[Build summary](evidence/macos/build-summary.json) pins the separate G2 binary,
284 staged Go/assembly/data files and the full7372→7373-file inventory extension:
exactly one test source,no runtime or guest change. Full inventories and original
command receipts remain in the owned workspace evidence outside Git.

Recommendation:use the one authorized Linux observation to establish whether the
same finite differences reproduce,then isolate native type decoding/LONG_DATA
preservation repairs separately. This G2 result does not qualify public adoption;
P1 ownership/public wiring and P2 declared consumers/performance still remain.

Local builder,runtime and bootstrap-tool workspaces have been disposed with
[cleanup debt0](evidence/macos/cleanup-summary.json). Compact originals and full
inventory receipts remain under owned evidence;Git contains the reduced report,
raw observation log and checksummed results. Public command/build receipts replace
only the local workspace prefix with `<owned-runtime-workspace>`.
