import argparse,importlib.util,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
spec=importlib.util.spec_from_file_location('timeout_baseline',Path(__file__).with_name('probe_baseline.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
subprocess.run(['go','test','-trimpath','-buildvcs=false','-v','-count=1','-run=^TestNativeTimeoutPublicDefaults$','.'],cwd=w/'temp/host/product',env=m.go_env(w),check=True)
print('PASS',flush=True)
