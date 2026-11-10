#!/bin/sh
set -eu
stage="$MARIAMEM_EXPERIMENT_TEMP"
evidence="$MARIAMEM_EXPERIMENT_EVIDENCE"
repo=$(pwd)
python3 scripts/git_identity.py inspect HEAD > "$evidence/candidate-identity.json"
python3 benchmarks/spikes/embedded-raw-rows/acquire.py "$stage" > "$evidence/acquisition.txt"
python3 benchmarks/spikes/embedded-raw-rows/prepare_baseline.py "$stage/baseline.inc" "$stage/lite4mariadb.c" > "$evidence/baseline-extraction.json"
runtime=$(sed -n '1s/ .*//p' benchmarks/spikes/embedded-raw-rows/images.txt)
builder=$(sed -n '2s/ .*//p' benchmarks/spikes/embedded-raw-rows/images.txt)
docker run --rm --network none --mount "type=bind,src=$stage,dst=/trial" --mount "type=bind,src=$repo,dst=/source,readonly" "$builder" sh -c 'mkdir -p /trial/packages; for p in /trial/*.deb; do dpkg-deb -x "$p" /trial/packages; done; gcc --version; gcc -std=c11 -O1 -g -Wall -Wextra -Wno-unused-function -Wno-unused-variable -D_GNU_SOURCE -DEMBEDDED_LIBRARY -I/trial/packages/usr/include/mariadb/server -I/trial /source/benchmarks/spikes/embedded-raw-rows/probe.c -L/trial/packages/usr/lib/aarch64-linux-gnu -Wl,--allow-shlib-undefined -lmariadbd -o /trial/probe' > "$evidence/compile.txt" 2>&1
# The data directory is fresh and belongs to this experiment only.
docker run --rm --network none --mount "type=bind,src=$stage,dst=/trial" "$runtime" sh -c 'mariadb-install-db --no-defaults --datadir=/trial/datadir --auth-root-authentication-method=normal --skip-test-db --user=root' > "$evidence/init.txt" 2>&1
docker run --rm --network none --mount "type=bind,src=$stage,dst=/trial" "$runtime" sh -c 'LD_LIBRARY_PATH=/trial/packages/usr/lib/aarch64-linux-gnu /trial/probe /trial/datadir' > "$evidence/rows.jsonl" 2> "$evidence/probe.txt"
GOCACHE="$stage/gocache" GOMODCACHE="$stage/gomodcache" go run ./benchmarks/spikes/embedded-raw-rows/compare "$evidence/rows.jsonl" > "$evidence/comparison.json"
