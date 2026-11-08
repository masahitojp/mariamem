# Canonical lexer source inputs:42448601842

Source_commit `fd615a53495b615ca2fec6007006f4a24f98d902`.
[CI](https://github.com/masahitojp/mariamem/actions/runs/42448601842) passed.
`assessment.json` owns the bounded conclusion; `receipt.json` retains compact
run/job/artifact identities and ZIP digests, the two-build comparison, native
normal/prepared SQL, source-inventory proof and installation/local-validation
results. `SHA256SUMS.json` covers these published files.

Two separate clean builders128632763844/128632763727 both reproduced guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1` and linked
`69dbde341c47149463d57b9f6cd4d2683506e7936dc756a4793f5425b788a722`.
Reference128632763882 and comparison128634390912 passed. The native result
contains COM_STMT_PREPARE/EXECUTE with Unicode/NUL/quotes/backslash and numeric
parameters. This run is source-input/native evidence; installed acceptance
belongs to the later42463414255 receipt.

## Reduction and verification

The prior reviewed representation is pinned at source381c0ae0 (full commit and
per-file hashes in receipt.json). Original ZIPs and source inventories were
verified before reduction. Both repeated guest metadata objects were checked
equal to the exact committed canonical prepared-source/toolchain values; their
reference and canonical digests replace the duplicated payload. The source
inventory proof independently compares all6856 tracked blobs at fd615a53.
No acceptance observation is inferred from a hash alone: concrete comparison,
native SQL, control outcomes and cleanup/preflight results remain structured.

Routine logs, duplicated metadata and full API responses are omitted according
to [compact CI receipt policy](../../development.md#compact-ci-receipts), rather
than packed as opaque raw data. Original hashes/source anchors remain available
for forensic comparison; the compact outcomes do not depend on artifact retention.
The original experimental/raw translation origin b1a265cc remains separate, and
no prior receipt is relabelled. No new performance or release claim is added.
