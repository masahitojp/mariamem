# Snapshot allocation attribution (diagnostic only)

Source: `c21ec0a3ee05f098e63f69521524e21c0ec4cf82`, macOS arm64.
Selected candidate and pinned guest/converter inputs: README.md.
No allocation strategy, guest source, SQL, synchronization or trust semantics change.
Generated code and binaries remain in an independent module under ignored `build/`.

Copy `build/generated-go-integration/final-stable-candidate/module` to a new
isolated diagnostic directory, then decode `snapshot-audit-patch.json` and apply with `patch -p1`
inside the copied module. Decode with `python3 -c 'import json,sys; sys.stdout.write(json.load(sys.stdin)["patch"])' < /absolute/path/snapshot-audit-patch.json | patch -p1`. Do not apply to normal packages. Dry-run application
against the unmodified source passed. The patch observes fragmented Snapshot
request frames, destination mkdir, guest return/worker join, native export, and
MemFS grow allocation/copy. `cmd/fs-growth` writes equal bytes in different blocks.

Build inside the copied module:

```sh
GOTOOLCHAIN=go1.26.8 go build -p 1 -trimpath -o ../snapshot-probe .
GOTOOLCHAIN=go1.26.8 go build -trimpath -o ../fs-growth ./cmd/fs-growth
```

Copy the selected native bundle to the diagnostic directory. Replace only its
historical `wasmer-headless` binary with `snapshot-probe`; update its SHA-256/size
in native-manifest.json. Preserve host/module/sidecar identities and
`public_release_ready=false`. The normal host still verifies bundle and Snapshot
metadata. Do not replace release or normal candidate artifacts.

From repository root, with an absolute audit-file path:

```sh
SNAPSHOT_AUDIT_FILE=$PWD/build/generated-go-integration/snapshot-audit/stages-counter.jsonl \
  build/bench/isolation-go \
  --native-dir build/generated-go-integration/snapshot-audit/native \
  --json build/generated-go-integration/snapshot-audit/trial-counter.json \
  --runs 2 --warmup 0 --workers 1 --rows 1000 --queries 1 --stage-timing
build/generated-go-integration/snapshot-audit/fs-growth --mib 96 --chunk 65536
build/generated-go-integration/snapshot-audit/fs-growth --mib 96 --chunk 1048576
build/generated-go-integration/snapshot-audit/fs-growth --mib 96 --chunk 100663296
```

Use a new JSONL file per invocation; records append. Run sequentially. Optional
`SNAPSHOT_CPU_PROFILE=/absolute/path/cpu.pprof` collects Snapshot CPU, but profile
start/stop adds overhead: measure separately. Local profile collection succeeded;
symbol analysis was unavailable (`go tool pprof`: no such tool). No profile symbol
percentages are claimed. Counter timing adds overhead too: these two Snapshot
trials do not replace the unchanged canonical 30-run benchmark.
