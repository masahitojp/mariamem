# Direct-link consumer build probe

This is an isolated distribution experiment. It does not select or change the
production runtime. Scripts write module fixtures/caches/binaries under an
ignored `build/` child and external consumer projects under the OS temporary
directory. Go source templates use `.go.txt` to stay outside package discovery.

## mariamem

Use the source commit recorded in
[`direct-link-consumer-experience.md`](../../direct-link-consumer-experience.md).
Have Go 1.26.8 and its ordinary MySQL driver dependencies available first.

```sh
python3 benchmarks/spikes/distribution/prepare.py \
  --work build/consumer-probe --mod-cache /path/to/go/pkg/mod
python3 benchmarks/spikes/distribution/build.py \
  --work build/consumer-probe --go /path/to/go1.26.8/bin/go \
  --label cold1 --fetch
python3 benchmarks/spikes/distribution/build.py \
  --work build/consumer-probe --go /path/to/go1.26.8/bin/go \
  --label ci1 --test-first
python3 benchmarks/spikes/distribution/baseline.py \
  --work build/consumer-probe --go /path/to/go1.26.8/bin/go \
  --cache-label ci1
```

The external project has `require github.com/masahitojp/mariamem
v0.4.0-direct-consumer-probe`, **no `replace`**, and `GOWORK=off`. Its local file
proxy is necessary because this branch has no published direct-linked API.
The synthetic version is local fixture metadata; no tag/release is created.
`GOSUMDB=off` applies to this unpublished fixture; Go still computes/verifies its
module content hash. The consumer uses ordinary `Start`, `DSN`, MySQL SQL, and
`Close`; it cannot access internal packages.

The fixture copies canonical generated functions/data/assembly without changing
them. Three fixture-only adapters replace executable delivery/`guest.StartKind`
with per-instance generated module/WASI/MemFS execution. Public host/protocol/API
files are copied unchanged. No native image is materialized or executed.
Cancellation, abnormal failure containment, and full optional API acceptance are
**not** provided by this adapter. Normal startup/SQL/Close are the test boundary.

The zip contains buildable source/licenses/locks, excluding embedded platform
images, repository docs/diagnostics and dependency tests. This models the source
dependency being investigated, not the current public module's complete zip or
a finalized packaging layout. Input hashes and exact fixture zip digest are
written to `fixtures.json`. Subsequent measurements reuse the identical zip.

Each label owns an initially empty `GOCACHE`; the module cache is separate and
reused. Dependency acquisition precedes build timing. macOS `/usr/bin/time -l`
reports maximum RSS (bytes), **not aggregate simultaneous compiler RSS**.
Do not run competing builds during measurement. Default Go parallelism applies;
there is no `-p 1`, compiler workaround, source reduction, or generator change.
`--compat-only` stops after build; otherwise SQL smoke tests execute. A consumer
marker used by `smoke` changes for the incremental test, ensuring test results
cannot silently stay cached. `--test-first` measures fully cold CI-like testing.
`cold_test` in the original evidence means the first test after a cold **build**,
not an independent empty-cache test.

## pgmem

Use a fresh ignored work directory and download the actual public module with
normal checksum-database verification:

```sh
env GOMODCACHE=/absolute/path/to/build/pgmem-probe/mod-cache \
  /path/to/go1.26.8/bin/go mod download -json github.com/shibukawa/pgmem@v1.18.1
python3 benchmarks/spikes/distribution/prepare_pgmem.py --work build/pgmem-probe
```

In the external consumer directory reported by that script, run `go mod download
all` with the same module cache, then run `build.py --work build/pgmem-probe
--go /path/to/go1.26.8/bin/go --label pgmem1`. This uses the same SQL/CRUD workflow
over loopback TCP with `database/sql` + pgx, no replacement module or custom dialer.
Keep pgmem download time separate from mariamem's **local-proxy** transfer time.

## Go compiler reproduction

Copy `compiler-repro.go.txt` to `repro.go` in a separate module with
`go 1.26.0`, and build using each absolute compiler path, `GOTOOLCHAIN=local` and
fresh/version-specific caches. It contains no MariaDB/generated package:

```sh
/path/to/go/bin/go build -gcflags=-S .
```

For upstream validation, the report pins both fix and master SHA, archive digest,
bootstrap version and resulting compiler identity. Download the pinned Go source
archive, verify its digest, and set its `VERSION` metadata before `src/make.bash`
when unpacking beneath another Git repository:

```text
go1.28-devel_ff48d740
time 2026-10-02T14:40:32Z
```

This prevents `cmd/dist` from accidentally labeling the SDK with the enclosing
mariamem Git revision. It changes version metadata only; do not patch compiler
code. Bootstrap using Go 1.26.8, `CGO_ENABLED=0`, isolated `GOCACHE`, and
`GOROOT_BOOTSTRAP`. Test both the reduced reproduction and `build.py` against the
same mariamem module zip, using the newly built absolute Go binary.
