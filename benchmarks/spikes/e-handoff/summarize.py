"""Summarize bounded E preparation experiments, not a full E speedup."""
import json
from pathlib import Path
import statistics
import sys

root=Path(sys.argv[1])
groups={}
for p in sorted(root.glob("*/result.json")):
    r=json.loads(p.read_text())
    key=f"n{r['rows']}-{r['mode']}"
    groups.setdefault(key,[]).append((p,r))
out={}
for key,rows in groups.items():
    timing={}
    names=list(rows[0][1]["times_ms"])
    for name in names:
        values=[r["times_ms"][name] for _,r in rows]
        timing[name]={"median":statistics.median(values),"min":min(values),"max":max(values),"all":values}
    total=[r["workflow_ms_before_validation"]+r["times_ms"]["baseline/close"] for _,r in rows]
    backings=[]
    for p,r in rows:
        b=p.parent/f"{r['setup_pid']}-backing.json"
        if b.exists():
            records=json.loads(b.read_text())
            backings.append({
                "all_nodes":len(records),"live_nodes":sum(x["Live"] for x in records),
                "logical_bytes_all":sum(x["Logical"] for x in records),
                "reserved_bytes_all":sum(x["Reserved"] for x in records),
                "remaps":sum(x["Remaps"] for x in records),
                "files":records
            })
    out[key]={"campaigns":len(rows),"timing_ms":timing,
        "whole_ms":{"median":statistics.median(total),"min":min(total),"max":max(total),"all":total},
        "backings_at_close":backings}
Path(sys.argv[2]).write_text(json.dumps(out,indent=2)+"\n")
for k,v in out.items():
    print(k,{n:round(v["timing_ms"][n]["median"],2) for n in ("setup/start","setup/migrate-seed","setup/snapshot")},'whole',round(v["whole_ms"]["median"],2))
