#!/bin/bash
set -eu
WORK=/Users/masahito/src/mysqlmem/publish/mariamem/build/experiment-work/v05-stable-guest-feasibility
export GOTOOLCHAIN=go1.26.8 GOCACHE="$WORK/temp/gocache" GOMODCACHE="$WORK/temp/modcache" GOPATH="$WORK/temp/gopath" GOTMPDIR="$WORK/temp/go-tmp" TMPDIR="$WORK/temp/tmp"
export GOWORK=off GOENV=off GOFLAGS='' GOEXPERIMENT='' GOMAXPROCS=2
export MARIAMEM_PHASE_TRACE="$WORK/evidence/native-phases.jsonl"
export MARIAMEM_DEV_EXPECTED_VERSION=12.3.3 MARIAMEM_DEV_SQL_VERSION_EVIDENCE="$WORK/evidence/sql-version-original-host.json"
unset MARIAMEM_DEV_WORKSPACE MARIAMEM_TEST_HOST MARIAMEM_TEST_DEFAULT
cd "$WORK/worktree"
exec "$WORK/temp/venv/bin/python" scripts/regenerate_release_guest.py --development --guest-dir "$WORK/temp/dev-guest" --output "$WORK/temp/dev-native"
