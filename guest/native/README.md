# Native glue ownership

The selected 13.2.0/native-text input installs five self-owned source files from
this directory after applying `embedded-wire.patch`. The relative paths below
`guest/native/` are their destinations in the prepared engine tree. They are
ordinary source inputs, not generated copies from an experiment workspace.

`embedded-wire.patch` contains edits to existing engine/build/recipe files only.
The descriptor's `native_overlay` binds its exact bytes and complete pre/postimages;
`native_glue` binds the five additions separately. The resolver verifies their
input hashes. Preparation rejects any pre-existing destination or symlink,
validates every input before writing, installs mode0644, and records each final
file hash. Source receipts must include the same glue inventory and postimages.
If upstream introduces one of these filenames, review the collision instead of
overwriting it, even when the bytes happen to match.

The files deliberately retain their current names, include locations, callback
ABI and implementation. This extraction changes ownership and delivery, not
state placement, protocol behavior or MariaDB's internal dependencies. It does
not remove the prepared conversion repair, atomic dispatch/capture gate, rollback
observation, native stop/join or guest deadline enforcement. The TIME repair and
pagecleaner observation remain unchanged. Future edits must justify their effect
on MariaDB upgrade work, rather than count moved lines as improvement.

The frozen 12.3.3 and 13.0.2 descriptors retain their original inputs. The selected
13.2 descriptor reuses these five common sources; future versions can reference
them after their source/ABI review, without copying an old experiment folder.
Canonical `guest/source.patch` remains unchanged. This is still an experimental,
release-ineligible route, not a second canonical product patch.

## Receipts and verification

Changing the descriptor changes selected-input identity even if the complete
prepared tree is identical. The existing producer/binding receipts remain valid
only for their original inputs. The installer still rejects different
host/producer selections: this extraction is not permission to relabel the old
guest, relax identity checks, or claim a new runtime PASS. The next planned
producer cohort must use matching inputs and binding receipts; no cost-only
rebuild is required for this source ownership check.

Focused verification:

```sh
python3 -m pytest -q tests/test_guest_native_glue.py \
  tests/test_guest_input_resolver.py tests/test_guest_preparation_context.py \
  tests/test_preview_guest_inputs.py tests/test_selected_guest.py \
  tests/test_selected_binding.py tests/test_prepared_source_patch.py
```

For the actual equivalence check, prepare 13.2.0/native-text once from the frozen
pre-extraction commit `fee63426c77937306eb8eea887aeb22a792616f5` and once from the
new candidate, using disposable experiment checkouts and the same hash-verified
archives. Compare every prepared source path, file byte hash, mode and symlink
target, not just the five added files. Source receipts are expected to differ;
the prepared tree is not. Preserve compact identities/results, then remove the
source trees, archives and temporary checkouts. No compile or runtime acceptance
is implied by source equality.
