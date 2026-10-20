#!/bin/sh
set -eu
TASK=$(cd .. && pwd -P)
export GOTOOLCHAIN=go1.26.8 GOCACHE="$TASK/temp/gocache" GOMODCACHE="$TASK/temp/modcache" GOPATH="$TASK/temp/gopath"
cd "$TASK/temp/dev-native/product"
go build -p 1 -trimpath -buildvcs=false -o "$TASK/temp/routine-cost" ./tests/guest_system_schema_cost
"$TASK/temp/routine-cost" -input "$TASK/temp/cost-sql.json" -output "$TASK/evidence/cost-alternating.json" > "$TASK/evidence/cost-alternating.log" 2>&1
for MODE in control proc base-fix; do
 "$TASK/temp/routine-cost" -input "$TASK/temp/cost-sql.json" -output "$TASK/evidence/cost-$MODE.json" -only "$MODE" > "$TASK/evidence/cost-$MODE.log" 2>&1
done
