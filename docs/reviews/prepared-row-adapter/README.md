# Prepared row structural validator — first implementation slice

Base source_commit: b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50.
Branch: experiment/prepared-row-adapter.

Adds ValidateBinaryRow using existing valueShape, validValue, readLength and
lengthPrefixSize. It borrows the row, validates metadata-driven widths, NULL
bitmap, canonical prefixes, temporal lengths, exact suffix consumption and
packet budget. It neither allocates decoded values nor reconstructs rows.

Verification: go test ./internal/preparedproto PASS on macOS arm64, including
all supported type codes against the existing independent EncodeBinaryRow
oracle, 250/251/65535/65536 byte boundaries, multi-byte bitmaps and malformed
headers, bitmaps, NULL/unknown types, temporal widths and length encodings.
Source identity checked with scripts/git_identity.py before testing.

This is one prerequisite implementation slice, not the integrated candidate.
C cached-row copying, private prepared protocol v2, host result integration,
whole-chain/hidden OUT fault tests and C ownership/OOM tests remain outstanding.
No generated guest, runtime integration, CI or maintenance improvement is claimed.
Existing production conversion remains. This slice adds code; it cannot yet
justify formal generation or prove a net maintenance reduction.

Issue ownership: #131 design; #134 integrated implementation; #128 cost judgment;
#132 public acceptance. #150 remains independent. The implementation must remove
output conversion before the actual added/removed responsibilities can be judged.
