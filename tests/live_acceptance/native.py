"""Fresh native control bound to the reconnecting Go application's source variant."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--go-app',type=Path,required=True)
    p.add_argument('--expected-source-commit',required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    app='tests/live_acceptance/goapp/main.go'
    digest=hashlib.sha256((ROOT/app).read_bytes()).hexdigest()
    assert digest==json.loads((HERE/'input-manifest.json').read_text())['files'][app]
    code=subprocess.call([sys.executable,str(HERE.parent/'e2e_native_control/run.py'),'--port',str(args.port),'--go-app',str(args.go_app.resolve()),'--expected-source-commit',args.expected_source_commit,'--output',str(args.output.resolve())],cwd=ROOT)
    if code:return code
    observed=json.loads((args.output/'result.json').read_text())
    assert observed['source_commit']==args.expected_source_commit and observed['result']=='PASS_NATIVE_CONTROL'
    assert '\tpath\tgithub.com/masahitojp/mariamem/tests/live_acceptance/goapp' in observed['go_buildinfo']
    (args.output/'app-variant.json').write_text(json.dumps(dict(source_commit=args.expected_source_commit,source_path=app,source_sha256=digest,binary_sha256=observed['go_app_sha256'],result='PASS_NATIVE_VARIANT'),indent=2)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
