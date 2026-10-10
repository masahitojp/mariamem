#!/bin/sh
set -eu
apt-get update > /w/evidence/ubuntu-apt.log 2>&1
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates gcc >> /w/evidence/ubuntu-apt.log 2>&1
export PATH=/w/temp/linux-sdk/go/bin:$PATH
export GOTOOLCHAIN=local GOWORK=off GOENV=off
export GOCACHE=/w/temp/linux-gocache GOMODCACHE=/w/temp/linux-gomodcache
export GOPROXY=file:///w/temp/ubuntu-module/proxy,https://proxy.golang.org
export GONOSUMDB=github.com/masahitojp/mariamem
export MARIAMEM_TEST_DEFAULT=1
mkdir -p /w/temp/linux-runtime
export TMPDIR=/w/temp/linux-runtime
cd /w/temp/ubuntu-consumer
go version | tee /w/evidence/ubuntu-go-version.txt
cat /etc/os-release > /w/evidence/ubuntu-os-release.txt
go env -json GOTOOLCHAIN GOARCH GOOS CGO_ENABLED > /w/evidence/ubuntu-go-env.json
go mod tidy > /w/evidence/ubuntu-tidy.log 2>&1
go list -m -json github.com/masahitojp/mariamem > /w/evidence/ubuntu-resolved-module.json
go test -p 1 -tags=integration -c -o consumer.test . > /w/evidence/ubuntu-build.log 2>&1
./consumer.test -test.v -test.timeout=10m > /w/evidence/ubuntu-consumer.log 2>&1
find /w/temp/linux-runtime -mindepth 1 > /w/evidence/ubuntu-runtime-residue.txt
