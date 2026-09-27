#!/usr/bin/env bash
# Canonical Linux guest build host packages; recipe participates in reuse identity.
set -euo pipefail
test "$(uname -m)" = x86_64
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  build-essential cmake ninja-build bison pkg-config curl ca-certificates git \
  libssl-dev zlib1g-dev libpcre2-dev libncurses-dev xz-utils
