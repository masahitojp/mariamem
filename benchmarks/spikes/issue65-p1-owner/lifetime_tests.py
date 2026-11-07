import argparse,importlib.util,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
spec=importlib.util.spec_from_file_location('p1_baseline',Path(__file__).with_name('probe_baseline.py'));probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)
subprocess.run(['go','test','-v','-run=^(TestWorkerReclaim|TestDetachedSelfReclaim|TestCompletedJoin|TestConcurrentWorkerReclaims|TestFailedSpawn|TestCallerOwnedStack|TestReclaimerAddressReuse|TestWorkerAllocationBinding|TestDeferredAllocatorFailure|TestLateReclaimerYield)','./internal/generatedgo/code/base'],cwd=w/'temp/host/product',env=probe.go_env(w),check=True)

# The enclosing binary-log scope checker requires a final successful sentinel.
print("PASS",flush=True)
