#!/bin/bash
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
apt-get -qq update
apt-get -qq install -y --no-install-recommends build-essential cmake ninja-build bison pkg-config curl ca-certificates git python3 libssl-dev zlib1g-dev libpcre2-dev libncurses-dev xz-utils
git -c safe.directory=/pin.git clone --no-hardlinks /pin.git /src
cd /src
python3 scripts/git_identity.py inspect HEAD | tee /out/builder-identity.json
test "$(git rev-parse HEAD)" = 5a7ec57bba4c4021c0bc1d3f34f00eed892bf19c
# The canonical producer records all archive hashes before creating /guest.
# At that point its large LLVM download is no longer an input to any later step.
(
  while [[ ! -d /guest ]]; do sleep 2; done
  rm -f /src/build/downloads/LLVM-23.1.0-Linux-ARM64.tar.xz
) &
MARIAMEM_PHASE_TRACE=/out/build.jsonl python3 -u scripts/build_generated_guest.py --development-output /guest
sha256sum /guest/linked.wasm /guest/mariamem.wasm | tee /out/guest-hashes.txt
cd /work
/root/.wasixcc/binaryen/bin/wasm-opt --version
/root/.wasixcc/binaryen/bin/wasm-opt -O2 \
  --enable-threads --enable-mutable-globals --enable-bulk-memory \
  --enable-bulk-memory-opt --enable-exception-handling --enable-simd \
  --enable-relaxed-simd --enable-extended-const \
  --symbolmap=/out/functions.txt /guest/linked.wasm -o /out/guest.wasm
sha256sum /out/guest.wasm /out/functions.txt
