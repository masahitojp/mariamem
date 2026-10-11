"""Bounded semantic probes on byte-identical canonical helpers; no runtime edits."""
import argparse,hashlib,json,os,platform,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);module=out/'module';module.mkdir()
subprocess.run(['python3',str(ROOT/'scripts/git_identity.py'),'inspect','HEAD'],cwd=ROOT,check=True)
inventory={}
for src in sorted((ROOT/'internal/generatedgo/code/base').iterdir()):
 if src.suffix not in {'.go','.s'} or src.name.endswith('_test.go'):continue
 shutil.copy2(src,module/src.name);inventory[src.name]=hashlib.sha256(src.read_bytes()).hexdigest()
shutil.copy2(Path(__file__).with_name('probe_test.go.txt'),module/'probe_test.go')
(module/'go.mod').write_text('module correctnessprobe\n\ngo 1.26.0\n')
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2')
checks=[('TestAllocateControls',False),('TestAllocatePreservesExistingData',False),('TestZeroBulkBounds',False),('TestAtomicValuesAndBounds',False)]
checks += [(name,race) for race in (False,True) for name in ['TestAtomicReadRead8','TestAtomicReadRead16','TestAtomicNeighbor8','TestAtomicNeighbor16','TestReadOnlyWordNeighbor']]
rows=[]
for name,race in checks:
 cmd=['go','test','-p','1',*(('-race',) if race else ()),'-count=1','-v','-run','^'+name+'$','.']
 r=subprocess.run(cmd,cwd=module,env=env,text=True,capture_output=True,timeout=180)
 key=name+('-race' if race else '');log=out/(key+'.txt');log.write_text(r.stdout+r.stderr)
 rows.append({'test':name,'race':race,'exit_code':r.returncode,'result':'PASS' if r.returncode==0 else 'FAIL','log':log.name,'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'race_report':'WARNING: DATA RACE' in log.read_text()})
 print(key,rows[-1]['result'],flush=True)
report={'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'platform':platform.platform(),'toolchain':'go1.26.8','canonical_helpers_sha256':inventory,'checks':rows,'scope':'Unmodified helper semantics and reduced host-memory conflicts; not full guest qualification or race census.'}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
