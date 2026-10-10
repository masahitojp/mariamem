# v0.5.x single-pass dev guest — validation

## Implementation plan / pending measurement

Phase 1 was integrated and pushed to main `70ac70ce0a4ccda403aa290dffa1d0bac0d8728b`.
The canonical Python check passed 563 tests, skipped 35 real-host/platform cases,
and passed 18 subtests. Generated inventory/input/guest identity passed. Runtime,
v0.4.6 tag/assets and Release workflows/guards were unchanged.

Phase 2 starts at that main on `experiment/v05-dev-guest-build` and follows the
[approved design](v05-dev-guest-build-design.md).

1. Extend the existing guest builder with explicit external development output.
   Keep Release default two builds/accepted hash intact; development records the
   actual single build as `development-unqualified-v1`, never accepted evidence.
2. Extend the existing regeneration entry with an explicit dev boundary. Verify
   source/patch/tool/actual WASM binding, use the existing converter and source
   adapter, then install only into a fresh product copy outside the checkout.
   Do not copy prior generated code or native binaries into that product.
3. Build a fresh host from that exact generated tree, bind the guest compatibility
   constant only in the disposable copy, check binary identity and execute small
   SQL/commit/rollback/Snapshot/Fork/normal-Close cases through the existing SDK.
4. Test wrong source/Wasm/tool/provenance, stale/mixed generation, partial failure,
   namespace mistakes and actual existing Release guard rejection. Partial output
   is FAILED or has no completion proof; a successful route remains UNQUALIFIED.
5. Validate current guest on a fresh isolated Linux arm64 builder and macOS native
   host. Record phase metrics with the integrated observer. Do not claim native
   Ubuntu product acceptance or Release qualification for this dev result.
6. Preserve compact hashes/receipts/measurements; remove owned source/build/cache,
   worktree and container residue. Commit/push and stop for Human Review.
