#!/bin/sh
set -eu
apt-get update > /w/evidence/ubuntu-app-apt.log 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends ca-certificates gcc >> /w/evidence/ubuntu-app-apt.log 2>&1
export PATH=/w/temp/linux-sdk/go/bin:$PATH
export GOTOOLCHAIN=local GOWORK=off GOENV=off
export GOCACHE=/w/temp/linux-gocache GOMODCACHE=/w/temp/linux-gomodcache
export GOPROXY=file:///w/temp/ubuntu-module/proxy,https://proxy.golang.org
export GONOSUMDB=github.com/masahitojp/mariamem
export TMPDIR=/w/temp/linux-runtime
cd /w/temp/ubuntu-consumer
go version > /w/evidence/ubuntu-ordinary-go-version.txt
go env -json GOTOOLCHAIN GOARCH GOOS CGO_ENABLED > /w/evidence/ubuntu-ordinary-go-env.json
go build -p 1 -mod=readonly -o app-bin ./app > /w/evidence/ubuntu-ordinary-build.log 2>&1
./app-bin > /w/evidence/ubuntu-ordinary-smoke.log 2>&1
find /w/temp/linux-runtime -mindepth 1 > /w/evidence/ubuntu-ordinary-residue.txt
