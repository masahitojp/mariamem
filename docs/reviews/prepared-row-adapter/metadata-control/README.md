# CI42796334150: column-count change

Guest installation, compilation and the transaction/Snapshot/3-Fork smoke passed.
The prepared test reached its last assertion: C-extension Connector26.7.0 raised
2057 when an already-executed statement changed from one result column to two.
Earlier type/NULL/binary/empty/repeat and same-statement duplicate-error recovery
assertions passed. CALL was not reached.

Local control reproduced2057 against the fixed12.3.3 MariaDB image using
Connector26.7.0 C extension on macOS/Python3.11. The local Python3.14 distribution
cannot import this Connector because of missing legacy SSL constants; no SSL
monkeypatch was used. The Python-minor difference is explicit; CI now independently
observes the native control under its actual Python3.14, rather than treating the
local result as that cohort's proof. Native CI is Linux x86_64; guest CI remains
macOS arm64, so this is not a claim of identical connector binary/platform.

The raw-wire control prepares once, executes, alters the table, executes the same
statement again, and asserts metadata count1→2 and exact row bytes. It succeeds
against native. Guest must match the complete before/after column, EOF/status,
and row packets from CI's native control. The high-level C-extension result must
also match that native control; it is not merely xfailed, skipped or swallowed.
This retains the original column-change guarantee while using an API capable of
reading the changed result. No product runtime code was changed for this repair.
