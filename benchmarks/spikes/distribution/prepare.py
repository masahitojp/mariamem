"""Private tagged direct-link module + actual external consumer. No production edits."""
import argparse, hashlib, json, re, shutil, tempfile, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
MODULE = 'github.com/masahitojp/mariamem'
TAG = 'v0.4.0-direct-consumer-probe'
p = argparse.ArgumentParser()
p.add_argument('--work', type=Path, required=True)
p.add_argument('--mod-cache', type=Path, required=True)
a = p.parse_args()
work = a.work.resolve()
if not work.is_relative_to(ROOT / 'build') or work == ROOT / 'build':
    raise ValueError('use isolated ignored build/ child')
if (work / 'fixtures.json').exists():
    raise ValueError('use a fresh fixture workdir')
work.mkdir(parents=True, exist_ok=True)
proxy = work / 'proxy'
dest = proxy / MODULE / '@v'
dest.mkdir(parents=True, exist_ok=True)
for name in ('github.com/go-sql-driver/mysql', 'filippo.io/edwards25519'):
    shutil.copytree(a.mod_cache / 'cache/download' / name / '@v', proxy / name / '@v', dirs_exist_ok=True)
stage = work / 'source'
stage.mkdir()
paths = [*ROOT.glob('*.go'), *ROOT.joinpath('internal').rglob('*.go'), *ROOT.joinpath('internal').rglob('*.s')]
paths += [ROOT / n for n in ('go.mod', 'go.sum', 'LICENSE', 'NOTICE', 'THIRD_PARTY_LICENSES', 'release/inputs.lock.json', 'release/generated-go-inputs.json')]
paths += list((ROOT / 'licenses').rglob('*'))
records = {}
for src in paths:
    if not src.is_file() or src.name.endswith('_test.go'):
        continue
    rel = src.relative_to(ROOT)
    if rel.parts[:2] == ('internal', 'builtinruntime'):
        continue
    out = stage / rel
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, out)
    records[rel.as_posix()] = hashlib.sha256(src.read_bytes()).hexdigest()
entry = stage / 'internal/generatedgo/consumer_fixture.go'
entry.write_bytes((Path(__file__).parent / 'direct-entry.go.txt').read_bytes())
provider = stage / 'internal/builtinruntime/runtime.go'
provider.parent.mkdir(parents=True)
provider.write_text('package builtinruntime\nimport "context"\nfunc Prepare(ctx context.Context,_ string)(string,error){return "direct-linked-consumer-fixture",ctx.Err()}\n')
guest = stage / 'internal/guest/guest.go'
text = guest.read_text()
begin = text.index('func StartKind(')
end = text.index('func (p *Process) PID()', begin)
text = text[:begin] + (Path(__file__).parent / 'guest-entry.go.txt').read_text() + text[end:]
text = text.replace('\t"github.com/masahitojp/mariamem/internal/timing"\n', '')
text = text.replace('"syscall"', '"github.com/masahitojp/mariamem/internal/generatedgo"').replace('return p.cmd.Process.Pid', 'return 0').replace('_ = syscall.Kill(-p.PID(), syscall.SIGKILL); ', '')
guest.write_text(text)
zipname = dest / (TAG + '.zip')
with zipfile.ZipFile(zipname, 'w', zipfile.ZIP_DEFLATED) as z:
    for f in sorted(stage.rglob('*')):
        if f.is_file():
            z.write(f, MODULE + '@' + TAG + '/' + f.relative_to(stage).as_posix())
(dest / (TAG + '.mod')).write_bytes((stage / 'go.mod').read_bytes())
(dest / (TAG + '.info')).write_text(json.dumps({'Version': TAG, 'Time': '2026-10-02T00:00:00Z'}))
(dest / 'list').write_text(TAG + '\n')
consumer = Path(tempfile.mkdtemp(prefix='mariamem-direct-consumer-'))
(consumer / 'main.go').write_bytes((Path(__file__).parent / 'consumer.go.txt').read_bytes())
(consumer / 'main_test.go').write_text('package main\nimport "testing"\nfunc TestConsumer(t *testing.T){if e:=smoke();e!=nil{t.Fatal(e)}}\n')
(consumer / 'go.mod').write_text('module example.com/mariamem-direct-consumer\n\ngo 1.26.0\n\nrequire (\n' + MODULE + ' ' + TAG + '\n github.com/go-sql-driver/mysql v1.9.3\n filippo.io/edwards25519 v1.1.0\n)\n')
row = {'tag': TAG, 'consumer': str(consumer), 'source_bytes': sum((f.stat().st_size for f in stage.rglob('*') if f.is_file())), 'module_zip_bytes': zipname.stat().st_size, 'module_zip_sha256': hashlib.sha256(zipname.read_bytes()).hexdigest(), 'canonical_input_hashes': records, 'fixture_only_changes': ['internal/generatedgo/consumer_fixture.go', 'internal/builtinruntime/runtime.go', 'internal/guest/guest.go']}
(work / 'fixtures.json').write_text(json.dumps(row, indent=2) + '\n')
print(json.dumps({k: v for k, v in row.items() if k != 'canonical_input_hashes'}))
