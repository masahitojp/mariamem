#!/bin/sh
set -eu
TASK=$(cd .. && pwd -P)
export PYTHONPATH="$TASK/temp/dev-native/product/python"
for MODE in baseline proc-only damaged-proc base-fix; do
 "$TASK/temp/venv314/bin/python" "$TASK/temp/probe.py" --mode "$MODE" --source "$TASK/temp/source" --host "$TASK/temp/dev-native/mariamem-dev-host" --output "$TASK/evidence/guest-$MODE.json" > "$TASK/evidence/guest-$MODE.log" 2>&1
done
