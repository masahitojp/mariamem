# J1 actual-body completion/reclamation comparison

This fixture preserves the original lifetime failure oracle. A failing
`early-free` case is the reproduced defect, not a passing safety check.
It is disposable instrumentation, not a production runtime repair.

Inputs: guest SHA256
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`,
goccy converter `730057c146463f663e8774587bc96fb2bea91af8`, the ordered
patches in `translate_guest.py`, Go1.26.8, and Node26.9.0 for the saved results.
Use an isolated workspace; `WASM`, `OUT`, and `CONVERTER_SRC` below refer to
the accepted guest, a fresh scratch directory, and the extracted converter
source from the canonical translation route. Check source identity using
`scripts/git_identity.py` before rebuilding inputs.

```sh
mkdir -p "$OUT" "$CONVERTER_SRC/cmd/j1-decode"
cp benchmarks/spikes/v050-join-check/decode.go.txt "$CONVERTER_SRC/cmd/j1-decode/main.go"
(cd "$CONVERTER_SRC" && GOTOOLCHAIN=go1.26.8 go run ./cmd/j1-decode "$WASM") > "$OUT/decoded.json"
python3 benchmarks/spikes/v050-join-check/export_fixture.py --wasm "$WASM" --output "$OUT/original.wasm"
node benchmarks/spikes/v050-join-check/original.js "$OUT/original.wasm" "$OUT/decoded.json" > "$OUT/original.json"
python3 benchmarks/spikes/v050-join-check/package.py --output "$OUT/go-probe"
```

Run each Go command separately from `$OUT/go-probe/module`, retaining its
exit code and output:

```sh
JOIN_BACKING=heap GOTOOLCHAIN=go1.26.8 go test -count=1 -v ./probe
JOIN_BACKING=mmap GOTOOLCHAIN=go1.26.8 go test -count=1 -v ./probe
JOIN_BACKING=heap GOTOOLCHAIN=go1.26.8 go test -race -count=1 -v ./probe
JOIN_BACKING=mmap GOTOOLCHAIN=go1.26.8 go test -race -count=1 -v ./probe
```

Expected current result: all four Go commands exit nonzero because `early-free`
changes a replacement-allocation byte from 165 to 1. Both control cases PASS.
Node exits zero only when it observes that same failure plus the two passing
controls; its receipt labels the lifetime oracle separately. Do not invert the
Go oracle to make the defective lifetime look correct.

The Node fixture adds exports and removes automatic start only. It shares one
memory between two instances, initializes the original data, uses actual guest
malloc/join/unlock functions, and records unchanged section hashes. The Go
fixture copies the exact direct-call closure, verifies generated function source
hashes against provenance, and adds one callback in a disposable host wake.
No generated production function is edited.

Both fixtures seed allocation/pthread/waiter state and force a serialized actor
interleaving while wake is in progress. They do not run pthread creation or a
complete SQL session. The host wake follows mariamem's output-byte ABI; the
comparison is not an independent qualification of another WASIX host. The
callback is a scheduling intervention, so no-observer behavior is not measured.
Deferred reclamation and absence of post-unlock wake are the two controls.
Zero race reports for these serialized schedules, mmap, or assembly do not
establish concurrent safety. See the [judgment and saved receipts](../../../docs/reviews/v050-boundary-join-fixes.md).
