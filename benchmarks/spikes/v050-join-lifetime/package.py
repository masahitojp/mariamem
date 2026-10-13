"""Package the actual J1 bodies, applying only the owned candidate adapter in prototype mode."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_thread_lifetime import apply

def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--prototype',action='store_true');a=p.parse_args()
 subprocess.run([sys.executable,str(ROOT/'benchmarks/spikes/v050-join-check/package.py'),'--output',str(a.output)],check=True)
 out=a.output.resolve();base=out/'module/internal/generatedgo/code/base/base.go';functions=out/'module/probe/functions.go'
 if a.prototype:
  base.write_text(apply('code/base/base.go',base.read_text()))
  functions.write_text(apply('code/p3/p3_pure.go',functions.read_text()))
 (out/'module/probe/probe_test.go').write_text(Path(__file__).with_name('probe_test.go.txt').read_text())
 d=json.loads((out/'identities.json').read_text());d['candidate']={'prototype':a.prototype,'base_sha256':hashlib.sha256(base.read_bytes()).hexdigest(),'functions_sha256':hashlib.sha256(functions.read_bytes()).hexdigest(),'test_sha256':hashlib.sha256(Path(__file__).with_name('probe_test.go.txt').read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256((ROOT/'scripts/runtime_thread_lifetime.py').read_bytes()).hexdigest()};(out/'identities.json').write_text(json.dumps(d,indent=2)+'\n')
if __name__=='__main__':main()
