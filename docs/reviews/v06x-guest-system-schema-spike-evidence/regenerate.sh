#!/bin/sh
set -eu
TASK=$(cd .. && pwd -P)
unset GOPATH GOCACHE GOMODCACHE
export MARIAMEM_DEV_WORKSPACE="$TASK"
export MARIAMEM_PHASE_TRACE="$TASK/evidence/host-phases.jsonl"
export GOTOOLCHAIN=go1.26.8
exec "$TASK/temp/venv314/bin/python" scripts/regenerate_release_guest.py --development --guest-dir "$TASK/temp/dev-guest" --output "$TASK/temp/dev-native"
