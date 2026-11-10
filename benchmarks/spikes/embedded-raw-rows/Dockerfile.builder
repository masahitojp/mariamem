# Small reproduction compiler; WASIX SDK is not needed for this native trial.
# Record the resulting image ID and gcc version for each new run.
FROM ubuntu:24.04@sha256:008173c23f95b170204355c12626cb5a965d779a7e1283b09e9cffbb1bf33ca3
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends gcc libc6-dev binutils && rm -rf /var/lib/apt/lists/*
