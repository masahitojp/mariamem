# Issue134: explicit-context source preparation

Parent goal: reduce recurring MariaDB upgrade work, preserving the old version.
The Human approved the next preparation integration and real source comparison.
Starting source_commit9c8ab9cafe9f3ad9bf0c2f19f2ad09e5141f6f76; branch
experiment/issue134-context-preparation. Scope: one common preparation path for
12.3.3/legacy-full,13.0.2/legacy-full,13.0.2/native-text with explicit registered
inputs and output ownership. Existing canonical entry remains the product default.

Exit: source preparation through the common path matches the original source
operations/full prepared outputs for each required combination; mixed inputs and
output collision reject. Report removed/remaining/added update work to #128 for
an initial benefit judgment before the public campaign. Do not claim total net
savings or guest/public acceptance from source equality.

Verification: focused Python tests and actual source preparation only. No SDK,
compilation, Go runtime, SQL, benchmark or CI. Fixed archive acquisition is shared
within this active task and removed afterward. Owned scratch ceiling6GiB and
free floor12GiB, active ceiling2h including tooling30min, source-preparation
wall ceiling60min. Sequential version comparisons bound storage. Preserve compact
inventories, original/new hashes and source/command identities; commit/push,
then clean owned inputs/trees/worktree. If preparation fails, preserve the exact
failure and investigate only the changed boundary within this scope. If the
scope/budget cannot establish equality, report the precise missing evidence.
