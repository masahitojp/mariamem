# Direct-link architecture probe

Investigation only; production runtime remains unchanged. The template is `.go.txt`
so normal package discovery does not compile the probe. `prepare.py` copies the
canonical host adapter (only package declaration changes) and records its hashes.
All generated guest functions are imported directly from canonical source.

```sh
python3 benchmarks/spikes/direct-link/prepare.py --output build/directlink-probe
cd build/directlink-probe
GOTOOLCHAIN=go1.26.8 go build -p 1 -mod=mod -trimpath -o probe .
cd ../..
python3 benchmarks/spikes/direct-link/run.py \
  --work build/directlink-probe --output build/directlink-probe/evidence.json
```

This runs 3 functional campaigns (two sequential instances, then two simultaneous
instances) and two separate fault probes. Fault probes intentionally exit the
harness process. Normal execution uses per-instance pipes, WASI/FS/Module/Threads,
without native guest image materialization or a guest subprocess. The command
adapter's global diagnostic flag is set once before any worker starts.

Optional existing-executable control needs installed Python mariamem + PyMySQL,
an existing accepted generated host executable and localhost listener permission:

```sh
build/sqlalchemy-dogfood/py314/bin/python \
  benchmarks/spikes/direct-link/shared_executable.py \
  --host build/mariamem-host --output build/directlink-probe/shared.json
```

No cache, library lifecycle fix, ready heap restore or production API integration
is implemented. The first io.Pipe attempt's zero-length write deadlock is described
in the report; the final probe uses ordinary OS pipes within its own process.
``ready_ms`` is a secondary New-to-ready observation, not a public first-SQL
benchmark. No cross-platform direct-link acceptance or race-detector claim.
