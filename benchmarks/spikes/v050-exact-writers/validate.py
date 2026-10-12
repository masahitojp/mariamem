"""Preserve positive/negative ownership and deterministic-construction results."""
import argparse
import json
from pathlib import Path
import subprocess
import shutil
import sys

ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser()
p.add_argument("--task",type=Path,required=True)
a=p.parse_args();task=a.task.resolve()
checks=[]
def run(name,cmd,cwd,expected,needle=None):
 r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=30)
 log=r.stdout+r.stderr
 (task/"evidence"/(name+".txt")).write_text(log)
 assert (r.returncode==0)==expected,log
 if needle:assert needle in log,log
 checks.append({"name":name,"exit_code":r.returncode,"expected_success":expected})
run("canonical-source",["python3","scripts/verify_generated_runtime.py"],ROOT,True)
run("candidate-source-rejected",["python3","scripts/verify_generated_runtime.py"],task/"temp/observed-candidate",False,"generated source inventory changed")
run("candidate-repeat-rejected",[sys.executable,str(Path(__file__).with_name("install_candidate.py")),str(task/"temp/observed-candidate"),str(task/"temp/rejected-repeat")],ROOT,False,"AssertionError")
first=json.loads((task/"temp/candidate-installation.json").read_text())
second=json.loads((task/"temp/observed-independent-installation.json").read_text())
assert first["adapted_base_sha256"]==second["adapted_base_sha256"] and first["added_files"]==second["added_files"]
checks.append({"name":"independent-prototype-source-identity","result":"PASS","adapted_base_sha256":first["adapted_base_sha256"]})
run("public-source-existing-failure",["python3","scripts/check_public.py"],ROOT,False,"generated/binary file in publication set: docs/reviews/v050-correctness-fixes-evidence/")
scope=task/"temp/public-boundary"
for rel in ("benchmarks/spikes/v050-exact-writers","docs/reviews/v050-exact-writers-evidence"):
 shutil.copytree(ROOT/rel,scope/rel,dirs_exist_ok=True)
for rel in ("docs/reviews/v050-exact-writers-design.md","docs/reviews/v050-shared-impact.md"):
 (scope/rel).parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(ROOT/rel,scope/rel)
sys.path.insert(0,str(ROOT/"scripts"))
from check_public import check
receipt=check(scope)
checks.append({"name":"public-source-scoped-new-and-touched-files","result":"PASS","file_count":len(receipt["files"]),
               "scope":"Does not replace the full public-source guard; existing tracked .log failure remains."})
(task/"evidence/ownership-checks.json").write_text(json.dumps(checks,indent=2)+"\n")
print("PASS: canonical ownership retained; candidate/repeated input rejected; independent source matched")
