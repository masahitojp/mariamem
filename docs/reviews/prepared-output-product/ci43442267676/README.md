# Canonical output CI43442267676 — fixture rebinding repair

Candidate be62515fe6f8a13ceb0e1d67972cdfb2ecaa3405 passed the fresh independent
C builds, native reference, full Go regeneration and build guards on both OSes.
Both product jobs then failed compiling the integration-test package: the
handwritten dictionary regression still called old guest function indices and
partitions. The old FAIL logs are preserved here.

This repair updates only fixture references/addresses, exact source-guard pins,
and CI detection. Generated guest bodies/inputs/ownership are unchanged. The
14 dictionary helper bodies were compared against eb175ae2: nonnumeric operations
are unchanged after explicit function-index mapping; operand differences are
recorded in ../dictionary-rebinding.json. The existing notification-removal,
lock-removal/order, pending/late/uncontended/nonpool, exclusion and disposal
assertions remain. The timer table slot moves12330→12329, with its vtable address
read from the new initialized data.

After compilation was repaired, replaying the entire failed step exposed the
UCA flag-table corruption fixture's old address. The original12288-byte table
was found uniquely at10143200 and matched the existing full SHA256 unchanged;
only the injected-corruption address moves. Neither the table hash nor the
functional/rejection expectations change.

Local replay passes:21 actual dictionary cases; the entire failed step including
UCA/private copy, lexer, prepared UCA and worker trap;68 dictionary source-guard,
mutation and generated-inventory checks. Normal generated inventory and public
source checks pass. The workflow now explicitly includes dictionary runtime and
source-guard tests, rather than merely compiling that fixture incidentally.

Both-platform runtime acceptance still needs the corrected CI run. No previous
FAIL or single-build bootstrap is relabeled, and this repair is not main/release
approval or all of#132 acceptance.

Public Python transaction/Snapshot/Fork and UCA child resnapshot smoke:2 PASS.
