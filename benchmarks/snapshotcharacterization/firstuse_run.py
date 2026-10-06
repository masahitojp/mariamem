"""Focused attribution cells; run through experiment_workspace.run."""
import os, pathlib, subprocess
root=pathlib.Path(__file__).resolve().parents[2]
temp=pathlib.Path(os.environ["MARIAMEM_EXPERIMENT_TEMP"])
evidence=pathlib.Path(os.environ["MARIAMEM_EXPERIMENT_EVIDENCE"])
for replica in range(3):
 for size in (0,10,100):
  env=dict(os.environ,FIRSTUSE_PROFILE="1" if replica==0 else "0")
  out=evidence/f"firstuse-{size}-{replica}.json"
  print(f"begin {out.name}",flush=True)
  with out.with_suffix(".log").open("w") as log:
   subprocess.run([str(temp/"characterize"),"-helper",str(temp/"process_cost"),"-out",str(out),"-mode","firstuse","-payload-mib",str(size),"-max-memory-gib","4"],env=env,stdout=log,stderr=log,check=True,timeout=240)
  print(f"done {out.name}",flush=True)
