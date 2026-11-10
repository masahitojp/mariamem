"""Bind the successful development artifact; never claim runtime acceptance."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from dev_guest import verify_guest
from git_identity import require_commit

guest,out=map(Path,sys.argv[1:])
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
require_commit(ROOT,source)
assert source==os.environ['GITHUB_SHA']
record=verify_guest(ROOT,guest)
assert record['source_identity']['commit']==source
base=json.loads((ROOT/'benchmarks/timercalibration/plan.json').read_text())['baseline_guest_sha256']
assert record['guest_sha256']!=base
result=dict(result='UNQUALIFIED_GUEST_BUILT',source_commit=source,guest_sha256=record['guest_sha256'],
            baseline_guest_sha256=base,patch_sha256=hashlib.sha256((ROOT/'guest/experimental.patch').read_bytes()).hexdigest(),
            runtime_analyze='NOT_RUN',host_regeneration='NOT_RUN',calibration_change='milliseconds_resolution_probe_only',
            next='Review strict CRC/ownership binding; rerun actual SQL timing/cleanup; compare against corrected-clock baseline. No speedup claim before paired measurements.')
(out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'SHA256SUMS.json').write_text(json.dumps({f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir()) if f.is_file() and f.name!='SHA256SUMS.json'},indent=2)+'\n')
