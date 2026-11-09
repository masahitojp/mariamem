# Explicit preparation inputs (experimental)

The registry selects three engine/profile descriptors. These feed the common
`prepare_guest.py` pipeline; no version switch overwrites the canonical input or
lock. Run `python3 scripts/prepare_guest.py --engine 13.0.2 --profile native-text
--work-dir <fresh-directory>` on an experiment branch. An optional
`--archive-cache <directory>` shares only checksum-checked archives; do not run
multiple writers against one cache. No SDK or compilation is performed.

Identical existing inputs are referenced directly. Different version/profile
bytes are kept under readable `inputs/` paths. Logical historical names inside
descriptors are retained for proof compatibility, including old spike labels;
the registry references maintained physical files here, never a local checkout.
A fresh private data-only input view adapts existing root-aware helpers. It does
not load executable code, change module globals, or rewrite product selection.

Corrected TIME and unchanged-file proofs follow edc703f. Original historical
producer fixtures remain unchanged in tests/fixtures/guest-input-resolver.
The recorded original commit is evidence provenance, not this new producer's
identity. Selected preparation uses a distinct receipt schema and remains
release-ineligible, including the stable engine comparison. Experimental native
classification survives physical relocation of its patch. Formal build/binding
and public-source acceptance still require later work.
