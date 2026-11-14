from pathlib import Path
import shutil,subprocess,json
E=Path(__file__).resolve().parent;X=E.parent;R=X.parents[2];T=X/'temp';donor=R/'build/experiment-work/modelcase-matched/evidence/harness'
for name in ['suite','probe']:
 H=T/name;H.mkdir(exist_ok=True);shutil.copytree(donor/'store',H/'store',dirs_exist_ok=True);shutil.copy2(donor/'go.sum',H/'go.sum')
 if name=='suite':
  shutil.copytree(donor/'internal',H/'internal',dirs_exist_ok=True);shutil.copy2(donor/'go.mod',H/'go.mod')
 else:
  for p in (H/'store').glob('*_test.go'):p.unlink()
  (H/'go.mod').write_text('module github.com/masahitojp/mariamem/benchmarks/forkcurrentprobe\n\ngo 1.27\n\nrequire (\n github.com/go-sql-driver/mysql v1.9.3\n github.com/masahitojp/mariamem v0.0.0\n)\nrequire filippo.io/edwards25519 v1.1.0 // indirect\nreplace github.com/masahitojp/mariamem => ../../worktree\n')
  (H/'main.go').write_bytes(subprocess.check_output(['git','show','bb459758917ebb82842e57aed29ecbefc9d5a1a1:benchmarks/forkcost/results-20261113-current/harness/main.go'],cwd=R))
base=T/'canonical-runtime-instance.go';base.write_bytes(subprocess.check_output(['git','show','eb175ae23292c1c40cfbeb4b9b73132873c4cc6f:internal/generatedgo/runtime_instance.go'],cwd=R))
(T/'canonical-overlay.json').write_text(json.dumps({'Replace':{str(X/'worktree/internal/generatedgo/runtime_instance.go'):str(base)}}))
