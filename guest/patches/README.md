# Canonical MariaDB portability series

`../input.json` is the selection and application manifest for exactly MariaDB
12.3.3's pinned archive. `scripts/prepare_guest.py` applies these patches before
`guest/source.patch`; neither file is an experimental overlay.

| Order | Patch | Purpose and origin |
| --- | --- | --- |
| 1 | `common-portability.patch` | 17-file CMake/WASIX/libc/filesystem/VM port. Derived from lite4 commit `24be9371a2f6c71250a2356631ad6feab2280b02` relative to MariaDB `b2a8c2234dbc276fe3947633c9ffea454badf48f`, with the experimentally verified NULL allocation/protect adaptation. Common context is preserved from comparison commit `06ad7abf8c38248ceff0b0105af02c010f51f4fc`. |
| 2 | `12.3.3-redo.patch` | Inherited WASIX protection limitation in 12.3.3's `HAVE_PMEM && is_pmem` redo mapping branch. Taken from `5f14221463b6400e72e72a115bd1cc1a3acee88d`; no 13.2 variant is adopted. |

The manifest binds both patch hashes, application order, per-file preimages and
postimages to the source archive digest and checksum-bound six-file lite4 recipe.
A null preimage means the file must not exist. Application is batch/forward,
fuzz=0, checked return status; postimages are then verified. Fuzz and whitespace
ignoring are not compatibility strategies. Registered input changes need review,
new evidence and updated pins, not an automatic major-version selector.

The [approved inventory](../../docs/decisions/guest-patch-management.md) owns each
file's purpose and inherited VM/file-lock/directory-fsync constraints. The
[integration report](../../docs/reviews/v050-ad-integration.md) owns this adoption's
actual build/generation/runtime evidence. Fifteen original per-file diff blocks
were byte-identical, while seventeen files can use the common patch; see its
repeated comparison for line-context and comment differences.
