from pathlib import Path
import subprocess,sys,json
E=Path(__file__).resolve().parent;W=E.parent/'worktree';sys.path.insert(0,str(W/'scripts'));import verify
a=[sys.executable,'-m','pytest',*verify.SOURCE_TESTS,'-q']
with (E/'source-check.log').open('w') as f:r=subprocess.run(a,cwd=W,stdout=f,stderr=subprocess.STDOUT)
(E/'source-check.json').write_text(json.dumps(dict(argv=a,returncode=r.returncode,scope='normal source-only owners; actual candidate runtime checked separately'),indent=2)+'\n')
print((E/'source-check.log').read_text()[-5000:]);sys.exit(r.returncode)
