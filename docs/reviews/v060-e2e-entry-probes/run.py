"""Bounded stdlib/fake-owner probes; exits nonzero on an unexpected oracle."""
import hashlib,json,os,platform,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OUT=ROOT/"build/e2e-entry-probes"
OUT.mkdir(parents=True,exist_ok=True)
TEMP=OUT/"temp";TEMP.mkdir(exist_ok=True)
ENV=dict(os.environ,GOTOOLCHAIN="go1.26.10",GOCACHE=str(TEMP/"gocache"),GOTMPDIR=str(TEMP),TMPDIR=str(TEMP))
sha=subprocess.check_output([sys.executable,"scripts/git_identity.py","inspect","HEAD"],cwd=ROOT,text=True)
identity=json.loads(sha)
assert not subprocess.check_output(["git","status","--porcelain","--untracked-files=normal"],cwd=ROOT,text=True).strip(),"clean source required"
results=[]
def run(name,args,expected=0,marker=None,mutation=None,cwd=HERE):
    env=dict(ENV)
    if mutation:env["PROBE_MUTATION"]=mutation
    p=subprocess.run(args,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=150)
    (OUT/(name+".txt")).write_text(p.stdout)
    ok=p.returncode==expected and (marker is None or marker in p.stdout) and "DATA RACE" not in p.stdout
    results.append(dict(name=name,returncode=p.returncode,expected=expected,marker=marker,pass_oracle=ok))
    if not ok:raise RuntimeError(name+" failed oracle: "+p.stdout[-4000:])
run("build",["go","test","-c","-race","-o",str(TEMP/"probe.test"),"."])
binary=str(TEMP/"probe.test")
run("healthy",[binary,"-test.v","-test.run","TestParallelLease|TestDebtStopsNext|TestIndependentOwners|TestPartialStart","-test.count=20"])
run("goexit",[binary,"-test.v","-test.run","TestFatalCleanup"],1,"GOEXIT_CLEANUP_OK")
run("early-release-mutant",[binary,"-test.v","-test.run","TestParallelLease"],1,"overlap admitted before active case cleanup",mutation="early-release")
run("late-register-mutant",[binary,"-test.v","-test.run","TestPartialStart"],1,"partial handle not stopped",mutation="late-register")
run("python-registration",[sys.executable,str(HERE/"registration.py"),"-v"])
report=dict(source_commit=identity["source_commit"],platform=platform.platform(),python=sys.version,go=subprocess.check_output(["go","version"],env=ENV,text=True).strip(),scope="controlled owners only; no actual guest/native/browser/CI acceptance",results=results,inputs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.is_file()})
(OUT/"assessment.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
