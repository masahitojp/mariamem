FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build bison pkg-config curl ca-certificates git \
    libssl-dev zlib1g-dev libpcre2-dev libncurses-dev python3 xz-utils
RUN mkdir -p /root/.wasixcc/bin && \
    curl -fLsS https://github.com/wasix-org/wasixcc/releases/download/v0.4.7/wasixcc-aarch64-unknown-linux-gnu.tar.gz \
      | tar xz -C /root/.wasixcc/bin
ENV PATH="/root/.wasixcc/bin:${PATH}"
RUN wasixccenv install-executables /root/.wasixcc/bin && \
    wasixccenv download-all --llvm-tag 21.1.206 --sysroot-tag v2026-07-03.1 --binaryen-tag version_133
WORKDIR /work
