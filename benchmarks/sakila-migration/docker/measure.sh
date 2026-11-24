#!/bin/sh
set -eu
if [ "$#" -ne 5 ]; then
    echo "usage: $0 /absolute/controller /absolute/sakila.test /absolute/docker mariadb-image docker-cli-image" >&2
    exit 2
fi
controller=$1
binary=$2
cli=$3
image=$4
cli_image=$5
network="sakila-four-$(uuidgen | tr -d '-' | tr '[:upper:]' '[:lower:]')"
extract=
network_created=
cleanup() {
    if [ -n "$extract" ]; then
        docker rm -fv "$extract" >/dev/null
    fi
    if [ -n "$network_created" ]; then
        for container in $(docker ps -aq --filter "network=$network"); do
            docker rm -fv "$container" >/dev/null
        done
        docker network rm "$network" >/dev/null
    fi
}
trap cleanup EXIT
extract=$(docker create --platform linux/arm64 "$cli_image")
docker cp "$extract:/usr/local/bin/docker" "$cli"
docker network create "$network" >/dev/null
network_created=true

docker run --rm --init --platform linux/arm64 --network "$network" \
    --mount "type=bind,source=$controller,target=/controller,readonly" \
    --mount "type=bind,source=$binary,target=/sakila.test,readonly" \
    --mount "type=bind,source=$cli,target=/usr/local/bin/docker,readonly" \
    --mount type=bind,source=/var/run/docker.sock,target=/var/run/docker.sock \
    --env "SAKILA_NETWORK=$network" --env "SAKILA_IMAGE=$image" \
    --env NATIVE_READY_PREBUILT_TLS=1 --env "SAKILA_RUNS=${RUNS:-5}" \
    --env TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal \
    --entrypoint sh "$image" -ceu '
        mkdir -p /control/data
        mariadb-install-db --no-defaults --datadir=/control/template \
            --auth-root-authentication-method=normal --user=root >&2
        openssl req -x509 -newkey rsa:4096 -nodes -subj /CN=localhost -days 1 \
            -keyout /control/key.pem -out /control/cert.pem >&2
        trial=0
        while [ "$trial" -le "$SAKILA_RUNS" ]; do
            case $((trial % 4)) in
                0) modes="mariamem native testcontainers docker" ;;
                1) modes="native testcontainers docker mariamem" ;;
                2) modes="testcontainers docker mariamem native" ;;
                3) modes="docker mariamem native testcontainers" ;;
            esac
            for mode in $modes; do
                # Testcontainers derives its Ryuk session from the parent PID.
                # A fresh parent gives each measured arm its own session.
                env sh -c "set -e; \"\$@\"; :" sh \
                    /controller /control/template /control/data /sakila.test \
                    "$SAKILA_IMAGE" "$SAKILA_NETWORK" "$mode" "$trial"
            done
            trial=$((trial + 1))
        done
    '
