#!/bin/sh
set -eu

bench=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
repo=$(CDPATH= cd -- "$bench/../.." && pwd)
runtime_ref=${SAKILA_RUNTIME_REF:-3831bd3c9cfa82931b0ae6956ac3dbdb9ffa9d3d}
result=${RESULTS_DIR:-"$bench/results/latest"}
runs=${RUNS:-5}
python=${PYTHON:-python3}
cli=docker@sha256:9190b0613792e658a7783cf14b2d5ace5941bb68ede7276922ea36ee457d76ad
ryuk=testcontainers/ryuk@sha256:31b31269d06603366cbfd0284708dcd2e281e8a4188e53fce3d3304439d0df3d

case "$runs" in
    ''|0|0*|*[!0-9]*) echo "RUNS must be a positive integer" >&2; exit 2 ;;
esac
"$python" -c 'import matplotlib'
docker info >/dev/null
runtime=$("$python" "$repo/scripts/git_identity.py" inspect "$runtime_ref" | \
    "$python" -c 'import json,sys; print(json.load(sys.stdin)["source_commit"])')

mkdir -p "$repo/build" "$result"
trial=$(mktemp -d "$repo/build/sakila-migration.XXXXXX")
trap 'rm -r "$trial"' EXIT
mkdir -p "$trial/source/benchmarks"
git -C "$repo" archive --output="$trial/runtime.tar" "$runtime"
tar -xf "$trial/runtime.tar" -C "$trial/source"
rm "$trial/runtime.tar"
module="$trial/source/benchmarks/.sakila-migration-measure"
mkdir "$module"
cp "$bench/go.mod" "$bench/go.sum" "$module/"
cp -R "$bench/cmd" "$bench/internal" "$bench/store" "$module/"
(
    cd "$module"
    package=github.com/masahitojp/mariamem/benchmarks/sakila-migration
    CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build \
        -ldflags "-X main.runtimeCommit=$runtime" -o "$trial/controller" ./cmd/driver
    CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go test -c \
        -ldflags "-X $package/store.sourceCommit=$runtime" -o "$trial/sakila.test" ./store
)
sh "$bench/docker/build.sh" "$trial/mariadb-image.id"
image=$(cat "$trial/mariadb-image.id")
image=$(docker image inspect --format '{{.Id}}' "$image")
docker image inspect "$cli" >/dev/null 2>&1 || docker pull --platform linux/arm64 "$cli"
docker image inspect "$ryuk" >/dev/null 2>&1 || docker pull --platform linux/arm64 "$ryuk"
docker tag "$ryuk" testcontainers/ryuk:0.13.0

RUNS="$runs" sh "$bench/docker/measure.sh" "$trial/controller" "$trial/sakila.test" "$trial/docker" \
    "$image" "$cli" > "$trial/samples.jsonl"
"$python" "$bench/summarize.py" "$trial/samples.jsonl" "$trial"
cp "$trial/samples.jsonl" "$trial/median.csv" "$trial/benchmark.png" "$result/"
printf '%s\n' "$result/benchmark.png"
