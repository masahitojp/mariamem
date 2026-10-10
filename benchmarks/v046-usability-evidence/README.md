# Compact v0.4.6 evidence

72 non-pilot product JSON records, summary.csv (all cells, not only medians),
inputs/build hashes, Ubuntu external consumer identity/results, type records and
validation scope. JSON preserves individual operations, CPU and available resource
samples; reports do not imply missing counters were measured. SHA256SUMS covers
these durable files. No binaries, wheels, SDK archives, caches or data trees retained.

## Reproduction

Use a disposable workspace with budget 12 GiB/minimum free 8 GiB; run only one
benchmark campaign per machine. Source, image and compiler pins are in inputs.json.
Go binaries used commit 5824ed1f205c84fc67574d6896afba412b57188b; final Python
harness used ff43ffef6ded67b3f37079831acc9f8e5bad8226. All retain the same library
source fingerprint. Existing reproduction scripts expect cwd=worktree and sibling
temp/evidence directories. They require clean Git source and use DiskGuard.
Reproduction creates new measurements, not identical wall times.

Build the following into sibling temp, with GOTOOLCHAIN=local and task-local
GOCACHE/GOMODCACHE. Record actual go version and binary hashes before execution:

```sh
go build -p 1 -trimpath -o ../temp/mariamem-host ./cmd/mariamem-host
go build -p 1 -trimpath -o ../temp/ownedprepared ./benchmarks/ownedprepared
# competitive is a separate module: run in benchmarks/competitive
# go build -p 1 -trimpath -o ../../../temp/competitive .
cc -O2 -o ../temp/process-cost benchmarks/tools/process_cost.c
python3 -m venv ../temp/venv
../temp/venv/bin/pip install -r benchmarks/v046-usability-evidence/python-dependencies.txt
```

Copy run-product.py and run-large.py to sibling evidence, install the digest-pinned
native image and execute in that order. Python adapter uses source SDK via PYTHONPATH;
matching host binary must be supplied. Official Python dependencies used are recorded
in python-dependencies.txt. The repeated Go suite reuse in run-product.py checks prior
successful JSON; do not reuse unknown files when reproducing another identity.
Prepare isolated fresh output directories for new trials.

Ubuntu uses the official Go1.27.2 linux-amd64 archive checksum in ubuntu-consumer.json
and the Ubuntu image digest recorded there. Mount workspace at /w, unpack SDK under
/w/temp/linux-sdk, and use scripts/consumer_module.prepare_proxy to create an exact-source
private proxy (no replace). Copy tests/godefault, the integration LoadSnapshot test
with package renamed to godefault, and transactions_test.go into the external module.
Run ubuntu-run.sh in a linux/amd64 Ubuntu24.04 container, then ubuntu-app.sh for the
ordinary app (scripts/guest_smoke/main.go). The scripts preserve compiler/env/residue.
This receipt represents emulated execution; native supported-platform qualification
remains separate. Public tag verification must use public artifacts rather than this
private fixture version.

Types: run TestRepresentativeTypes and tests/test_type_compatibility.py once with the
candidate, once with MARIAMEM_TYPE_DSN / MARIAMEM_TYPE_PORT pointing at native MariaDB.
Use UTC and the same driver configuration. Recorded driver-level metadata/value output
is in types.json. See source tests for deterministic DDL/values.

After preserving new compact results and Git changes, delete the workspace/toolchain/
module/build caches using the experiment-workspace workflow. Cache is disposable.
