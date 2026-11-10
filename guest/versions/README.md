# Versioned embedded source preparation

`registry.json` pins complete descriptors for the current 12.3.3 legacy input
and a frozen historical 13.0.2 legacy input. This is source preparation only:
13.0.2 is neither the product default nor an adopted runtime. The future target
is 13.3 LTS; registering or preparing a version does not accept that version.
No native protocol profile is registered.

The existing command remains the canonical 12.3.3 preparation path:

```sh
python3 scripts/prepare_guest.py
```

For isolated, explicitly selected preparation (Python 3.14, Git and `patch`):

```sh
python3 scripts/git_identity.py inspect HEAD
python3 scripts/prepare_guest.py --engine 12.3.3 --profile legacy-full \
  --work-dir /tmp/mariamem-12-source
python3 scripts/prepare_guest.py --engine 13.0.2 --profile legacy-full \
  --work-dir /tmp/mariamem-13-source
```

Use previously nonexistent work directories. Archives are fetched from the URLs
and checked SHA256 values in each descriptor's effective lock. No SDK/compiler
is required for preparation. An optional `--archive-cache` selects an explicitly
owned download cache; existing files still undergo checksum validation. Remove
owned work directories and downloads after saving compact evidence. Budget for
up to 6 GiB of scratch with 12 GiB free reserve for the comparison below.

The selected path never rewrites canonical `guest/input.json`, source patches,
release locks or generated runtime. It creates an input view, `source/`,
`resolved-input.json` and an explicitly release-ineligible `prepared-source.json`.
It rejects unknown versions/profiles, changed hashes, patch order/images,
symlink inputs and existing/overlapping outputs. `verify_receipt(root, engine,
profile, work_dir)` in `guest_preparation_context` checks selection freshness and
recorded prepared-file hashes. A receipt is not a signed artifact or a runtime
acceptance result. Build and release consumers are not switched to this path.

## Register the next version

1. Verify `source_commit` and `tag_object_sha` with `scripts/git_identity.py`.
   A tag object is not a source commit; a source with no tag records JSON null.
2. Add a descriptor, a hash-bound shared lock and version-specific data under
   `guest/versions/<version>/`. List source/recipe archive hashes, ordered patches
   with complete pre/postimages, prepared/TIME proofs, routine and UCA inputs,
   and every copied include. Preserve previous entries. Reference maintained
   shared files when identical; freeze version-specific bytes when required.
3. Specify `preparation_features`: the existing UCA, lexer and startup-concurrency
   steps are implemented once. Derive the exact `stages` with `stage_order` and
   register the descriptor, guest-input, effective-lock and stage hashes.
   Hashes use SHA256; semantic hashes use sorted compact JSON plus a newline.
4. Run the input tests and a complete prepared-source comparison. Review any
   intended difference, rather than accepting a newly computed hash as proof.
   Registering a new version is data-only while these existing stages and helper
   contracts apply. Changes to upstream patch semantics, recipe layout, UCA,
   lexer source-bound constants or routine parsing may require reviewed helper
   changes. This tool does not promise arbitrary versions need no code edits.
5. Separately review source patches/internal API meaning, generate the guest,
   review exact bindings and perform public runtime/consumer acceptance when
   actually adopting that version. Those upgrade obligations remain.

The 13.0.2 entry preserves its original observation patch and old includes for
source reproduction; they are not silently applied to current 12.3.3 or treated
as production-approved 13.x changes. Current 12.3.3 retains UCA, lexer and startup
concurrency preparation; historical 13.0.2 uses only its original UCA stage.
The copied lexer generator in a staged input view is used for provenance hashing;
execution uses maintained scripts. UCA's existing pinned checker is preserved.

## Source equality, without guest compilation

From a clean committed checkout with Git history and network access:

```sh
python3.14 tests/compare_selected_preparation.py \
  --scratch /tmp/mariamem-source-comparison \
  --evidence /tmp/mariamem-source-evidence
```

This existing comparison recipe is narrowed to the two legacy profiles. It uses
frozen producer commits as independent oracles, compares all paths/bytes/modes/
link targets, and also checks the refactored default against current main.
Historical worktrees exist only during this comparison. Ordinary selected
preparation needs no old checkout, untracked inputs or spike-generated artifact.
The bounded script uses a 6 GiB scratch budget, 12 GiB free reserve and a one-hour
command budget. After retaining logs and `comparison.json`, remove owned scratch
and download cache; on failure inspect/preserve evidence before removing owned
oracle worktrees. No guest, Go runtime, benchmark or release is built here.
