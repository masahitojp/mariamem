# Bounded shared-access semantic investigation

Read [the judgment record](../../../docs/reviews/v050-semantic-audit.md) and the
[R1–R5 contract](../../../docs/reviews/v050-access-review.md) first. This tooling
adds no product fix and is not release qualification. The fixed runtime is
`f66727dda49d1b4ca2c7e814e218587c051f7f97`; the investigation started at commit
`67549402ff4d4a5ddda2a3a56961e12828c8ffa5`. Preserve that runtime/input identity
when reproducing the recorded failures.

Use a disposable experiment workspace with a fresh output directory. The
recorded budget was 8 GiB with 8 GiB minimum free space. Keep Go caches under
owned scratch. From the worktree root:

```sh
python3 scripts/git_identity.py inspect HEAD
export GOTOOLCHAIN=go1.26.8
export GOPATH="$AUDIT/temp/gopath"
export GOCACHE="$AUDIT/temp/gocache"
python3 benchmarks/spikes/v050-semantic-audit/ledger.py --output "$AUDIT/evidence"
python3 benchmarks/spikes/v050-semantic-audit/callbacks.py --output "$AUDIT/evidence"
python3 benchmarks/spikes/v050-semantic-audit/run_probe.py \
  --output "$AUDIT/temp/protocol" --evidence "$AUDIT/evidence/probe"
```

Set `AUDIT` to the prepared workspace root before these commands. `package.py`
copies the exact 20-function direct closure, canonical helpers and selected host
methods; it checks source provenance and records body/fixture hashes. Test TLS,
32 MiB memory and the parked-queue observer are fixture scaffolding. Heap and
production mmap allocation are separate runs. `run_probe.py` is intentionally
native Go 1.26.8 darwin/arm64 for this approved executable scope; other native
platforms require their own receipts and were SKIP here.

The runner expects functional checks to pass and **two correctness oracles to
fail on the unchanged implementation**. Runner exit zero means the receipt
matched those expectations, not that the runtime is correct. `go vet` also
reports four unreachable-code diagnostics in unchanged copied guest bodies;
that is recorded as FAIL, not disabled. An unexpected outcome stops the runner.
The final saved probe receipt supersedes an earlier harness attempt which
stopped when these vet diagnostics were not yet classified.

## Source and stage reproduction

Download MariaDB and WASIX source archives using the URLs and SHA256 values in
`release/inputs.lock.json`. Extract with a safe tar reader into fresh directories.
For MariaDB apply `guest/input.json`'s ordered patches using the canonical
`scripts/guest_input.py:apply_series`; reject hash/preimage/postimage failures.
This is a source-review corpus, not a substitute for `prepare_guest.py` and the
formal guest build. `collect_sources.py` independently checks archive content,
reconstructs the diagnostic overlays in a temporary tree and verifies selected
modified files against `release/generated-go-build.json` before extracting
anchors. It does not mislabel pristine line numbers as prepared-source lines.

For converter input use `release/generated-go-toolchain.json`'s `converter`
archive (goccy commit `730057c146463f663e8774587bc96fb2bea91af8`). Verify the
archive SHA256, extract it, initialize its own Git directory, then apply
`benchmarks/spikes/generated-go-integration/translate_guest.py:PATCHES` in that
exact order with `git apply --unidiff-zero`. Build from that directory using:

```sh
go build -mod=readonly -trimpath -buildvcs=false -o "$AUDIT/temp/wasm2go" ./cmd/wasm2go
```

No shibukawa fork or converter update is involved. The saved
`converter-patches.json` records all 11 patch hashes. Fetch the `sysroot` archive
from the same toolchain descriptor, verify its SHA256, and extract only
`lib/wasm32-wasi/libc.a`. The Binaryen source review uses the `version_133` archive
from `https://codeload.github.com/WebAssembly/binaryen/tar.gz/refs/tags/version_133`;
its observed archive hash is in `source-inputs.json`. Go compiler sources are
from the Go 1.26.8 toolchain, not the default local Go version.

```sh
python3 benchmarks/spikes/v050-semantic-audit/collect_sources.py \
  --mariadb "$AUDIT/temp/mariadb/server-83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e" \
  --wasix "$AUDIT/temp/wasix/wasix-libc-2026-07-03.1" \
  --go "$GOPATH/pkg/mod/golang.org/toolchain@v0.0.1-go1.26.8.darwin-arm64" \
  --converter "$AUDIT/temp/converter/wasm2go-730057c146463f663e8774587bc96fb2bea91af8" \
  --binaryen "$AUDIT/temp/binaryen-source/binaryen-version_133" \
  --mariadb-archive "$AUDIT/temp/mariadb.tar.gz" \
  --wasix-archive "$AUDIT/temp/wasix.tar.gz" --output "$AUDIT/evidence"
python3 benchmarks/spikes/v050-semantic-audit/run_fences.py \
  --output "$AUDIT/temp/fences" --evidence "$AUDIT/evidence" \
  --converter "$AUDIT/temp/wasm2go" \
  --converter-source "$AUDIT/temp/converter/wasm2go-730057c146463f663e8774587bc96fb2bea91af8" \
  --libc "$AUDIT/temp/libc.a"
```

The fence runner uses the recorded existing Docker image by immutable local
image ID (see its source/receipt), WASIX LLD 21.1.2 and Binaryen 133. The tag
`mariamem-wasix-build:0.4.7` alone is not an identity. A rebuilt image with a
different ID needs a new tool identity record; do not claim byte-for-byte
reproduction based on the name. The adopted full guest used LLVM 23.1.0, so
this reduction is deliberately **not** an independent guest rebuild. Exact
commands, diagnostics, decoder bodies, generated fence sites and file hashes
are in `fence-results.json`. It observes three linked fences becoming zero after
`-O2` with the canonical enabled feature flags, while explicit fence fixtures
survive both converter output modes. Prior ad-hoc reduction files are superseded
by this scripted receipt; their file hashes need not match different link flags.

`ledger.py` verifies all 147 writer statements and 65 selected ordinary reads;
it also saves all 99 literal thread-list references, including inlined joins.
`callbacks.py` classifies all 47 indirect call lines in the 17 writer functions
and corroborates selected fixed table/data slots. These scripts establish
mechanical coverage, not automatic alias analysis or proof of the manual
ownership arguments in `targets.json`.

## Evidence preservation and cleanup

The evidence manifest distinguishes raw SHA256 from saved SHA256 when local
workspace/toolchain paths are normalized and trailing whitespace in text logs
is removed. Hash fields inside execution receipts
refer to their original raw logs/artifacts; do not silently rewrite them to claim
unchanged bytes. Ordinary test logs are retained in full. Full compiled binaries,
source archives, generated probe trees and caches are reproducible and disposable.
Commit/push the report, fixtures and compact receipts, then follow the repository
experiment-workspace finalization/cleanup workflow. Preserve existing user work
and shared Docker images. No production source regeneration is required for this
analysis-only change; canonical source verification still runs.
