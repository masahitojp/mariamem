#!/bin/bash
set -eu
WORK=/workspace/mariamem/build/experiment-work/v05-mariadb-132-feasibility
export PATH="/toolchains/go1.26.8/bin:$PATH"
export GOTOOLCHAIN=go1.26.8 GOCACHE="$WORK/temp/gocache" GOMODCACHE="$WORK/temp/modcache" GOPATH="$WORK/temp/gopath" GOTMPDIR="$WORK/temp/go-tmp" TMPDIR="$WORK/temp/tmp"
export GOWORK=off GOENV=off GOFLAGS='' GOEXPERIMENT='' GOMAXPROCS=2
export MARIAMEM_PHASE_TRACE="$WORK/evidence/native-phases.jsonl"
export MARIAMEM_DEV_EXPECTED_VERSION=13.2.0 MARIAMEM_DEV_SQL_VERSION_EVIDENCE="$WORK/evidence/sql-version-original-host.json"
unset MARIAMEM_DEV_WORKSPACE MARIAMEM_TEST_HOST MARIAMEM_TEST_DEFAULT
go version > "$WORK/evidence/go-version.txt"
cd "$WORK/worktree"
exec "$WORK/temp/venv/bin/python" scripts/regenerate_release_guest.py --development --guest-dir "$WORK/temp/dev-guest" --output "$WORK/temp/dev-native"
