#!/bin/bash
set -euo pipefail
TASK_ROOT=/Users/masahito/orca/workspaces/mariamem/v06-live-usage-main/build/experiment-work/live-examples-check
exec > "$TASK_ROOT/evidence/campaign.txt" 2>&1
export GOTOOLCHAIN=go1.26.10
export GOCACHE="$TASK_ROOT/temp/gocache"
export GOPATH="$TASK_ROOT/temp/gopath"
export GOMODCACHE="$TASK_ROOT/temp/modcache"
export PLAYWRIGHT_BROWSERS_PATH="$TASK_ROOT/temp/browsers"
export PYTHONDONTWRITEBYTECODE=1
export PKG_CONFIG_PATH=/opt/homebrew/opt/mariadb-connector-c/lib/pkgconfig
export MYSQLCLIENT_CFLAGS="$(pkg-config --cflags libmariadb)"
export MYSQLCLIENT_LDFLAGS="$(pkg-config --libs libmariadb)"
git clone --no-hardlinks --no-checkout /Users/masahito/orca/workspaces/mariamem/v06-live-usage-main "$TASK_ROOT/temp/source"
cd "$TASK_ROOT/temp/source"
git checkout --detach 342e63ea4233eeea5f03f05292041e2c56df2e38
python3 scripts/git_identity.py inspect HEAD
mkdir -p "$TASK_ROOT/temp/bin"
go build -p 1 -trimpath -o "$TASK_ROOT/temp/bin/mariamem-host" ./cmd/mariamem-host
go build -p 1 -trimpath -o "$TASK_ROOT/temp/bin/go-orders" ./tests/live_acceptance/goapp
"$TASK_ROOT/temp/venv/bin/python" -m pip install --no-cache-dir -r tests/e2e_native_control/requirements.lock.txt
"$TASK_ROOT/temp/venv/bin/python" -m playwright install chromium --only-shell
"$TASK_ROOT/temp/venv/bin/python" docs/examples/live/verify.py --host "$TASK_ROOT/temp/bin/mariamem-host" --go-app "$TASK_ROOT/temp/bin/go-orders" --expected-source-commit 342e63ea4233eeea5f03f05292041e2c56df2e38 --output "$TASK_ROOT/evidence/functional"
