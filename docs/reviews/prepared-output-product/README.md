# Prepared output — fresh guest and translation checkpoint

The authorized product source is90a505cbad9799c1bc8f918d4280793d4284fe6b.
CI43436504181 passed its fresh12.3.3 single-build UNQUALIFIED input stage.
`bootstrap.json` records acquisition identity. The full immutable producer
receipt is retained in `guest-receipt.json`; it is not canonical acceptance.

Fixed translation completed. Replaying postopt from the linked artifact with
Binaryen133 Mac (archive hash in binding.json) reproduces the exact CI guest.
`function-map.txt` therefore identifies the same optimized functions, not an
approximation from a different build. `translation.json` records converter,
patches and complete raw-source hashes.

Whole worker bodies are retained. Fn131 is unchanged. Fn153/dlfree and
Fn214/wasi_thread_start contain address relocations; their full diffs are retained.
The actual CRC validator is now Fn18142/buf_page_is_corrupted, still in p4;
Fn18145 is now a different function and must never be rebound just by number.
The actual full-body diff is crc-actual.diff. It includes static addresses,
called function indices and a diagnostic string relocation, not only a renamed
function. The CRC4096-byte table is unchanged and moves from7930560 to7929536.

This checkpoint intentionally does not update accepted hashes or canonical Go.
Before installation, review every body relocation and associated references,
then update exact complete preimages and symbol-specific tests together. No
runtime matcher may normalize arbitrary addresses/function indices into
acceptance. The current canonical guest and input pins are still the baseline.
The new source does not yet form a usable product.

The first translation attempt used system Python3.9 and stopped at the tar
safe-extraction API. Repeating with installed Python3.14 succeeded; no project
requirements were changed for that environment error.

Remaining: complete relocation/reference review; formal input and worker/CRC
rebinding; canonical installation and ownership/inventory; focused binding
negative tests; independent regeneration and same-candidate public acceptance
under#134/#132. No new engine patch, contract waiver or#138 restart follows.
