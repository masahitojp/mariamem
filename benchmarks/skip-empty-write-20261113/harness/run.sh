#!/bin/bash
# Run the model-case suite on pgmem and on conventional servers.
#   RUNS=5 ./run.sh                 -> results/raw.jsonl, results/summary.json,
#                                      website/src/data/modelcase.json
#   TARGETS="pgmem devbox" ./run.sh -> skip docker
# devbox needs devbox; testcontainers and docker need a running daemon with
# the image pulled (a target whose tool is missing is skipped with a note).
set -euo pipefail
cd "$(dirname "$0")"
RUNS=${RUNS:-5}
TARGETS=${TARGETS:-"pgmem testcontainers devbox docker"}
IMAGE=${IMAGE:-postgres:18-alpine}
OUT=results
mkdir -p "$OUT" bin
go vet ./...
go test -c -o bin/store.test ./store
go build -o bin/driver ./cmd/driver

: > "$OUT/raw.jsonl"
for t in $TARGETS; do
  case $t in
    docker|testcontainers)
      if ! docker info >/dev/null 2>&1; then echo "skip $t: no daemon" >&2; continue; fi
      docker pull -q "$IMAGE" >/dev/null
      # testcontainers-go looks for the daemon on its own; point it at the
      # CLI's current context (OrbStack keeps the socket outside /var/run)
      export DOCKER_HOST=${DOCKER_HOST:-$(docker context inspect -f '{{(index .Endpoints "docker").Host}}')}
      ;;
    devbox)
      if ! command -v devbox >/dev/null; then echo "skip devbox: not installed" >&2; continue; fi
      devbox install -q -c ../alternatives/devbox >/dev/null 2>&1
      ;;
  esac
  if [ "$t" = testcontainers ]; then
    # one process per run: a fresh test process starts Ryuk, and that is
    # part of what the suite waits for
    bin/driver -backend "$t" -runs 0 -warmup 1 -image "$IMAGE" >> "$OUT/raw.jsonl"
    for ((i = 1; i <= RUNS; i++)); do
      bin/driver -backend "$t" -runs 1 -warmup 0 -image "$IMAGE" >> "$OUT/raw.jsonl"
    done
  else
    bin/driver -backend "$t" -runs "$RUNS" -image "$IMAGE" >> "$OUT/raw.jsonl"
  fi
done

python3 summarize.py "$OUT/raw.jsonl" > "$OUT/summary.json"
cp "$OUT/summary.json" ../../website/src/data/modelcase.json
