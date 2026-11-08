# Compiled lexer source input

This bundle is the numeric input and private C wrapper for638 compiled startup
charset descriptors, deduplicated into28 pairs of512 bytes. The generator is
`scripts/lexer_prepared.py`; `prepare_guest.py` validates pristine MariaDB input
hashes and writes the header before applying canonical `guest/source.patch`.

`input.json` contains stable IDs, numeric data and source hashes, with no guest
addresses. Its origin is the reviewed experiment8d5f8284; original full-table
C/guest comparison remains in that immutable evidence. `wrapper.c.inc` retains
the reviewed fallback and private verifier semantics. The header's descriptive
comment changes during canonical packaging; runtime bytes must still reproduce
the accepted guest hash. The two-builder gate detects any binary difference.

`actual_guest_test.go.txt` is the future canonical integration-test input. It is
not installed or claimed executed by Stage1. Stage2 moves it to the handwritten
runtime ownership list and runs it against the canonical installed guest.

Stage1 workflow `lexer-canonical-input.yml` is manually dispatched; automatic CI
belongs to Development. It runs two independent C builders and
records a normal/binary-prepared native SQL reference. It leaves product runtime,
adapters and release pins unchanged until source evidence is available. Follow
[the approved fixed gates](../../docs/decisions/prepared-lexer-maps.md).
