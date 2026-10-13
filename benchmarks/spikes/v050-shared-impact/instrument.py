"""Bounded deterministic observation in disposable copies; no canonical edits."""
from pathlib import Path
import hashlib,json,re,shutil,sys
root=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve()
assert not out.exists()
shutil.copytree(root,out,ignore=shutil.ignore_patterns('.git','build','__pycache__','.pytest_cache'))
base=out/'internal/generatedgo/code/base'
selected={4053,4054,4055,16684,17888,17889,17950,18010,17994,18090,18114,18218,18221,18241,18511,20878,16535,16537,18497,18500,17770,17772,18168,17161}
manifest={'baseline_source_commit':'82f3c2bcef1518dadf5138a03e11dcfeb3db2de6','selected_ordinary_functions':sorted(selected),'changes':{},'sites':[]}
for p in sorted((out/'internal/generatedgo/code').glob('p*/*.go')):
 old=p.read_text(); lines=old.splitlines(keepends=True); fn=None
 for n,line in enumerate(lines):
  m=re.match(r'func Fn(\d+)\(',line)
  if m: fn=int(m[1])
  if fn is None:continue
  site=n+1
  # Every remaining subword writer site, irrespective of selected ordinary functions.
  for name in ['AtomicStore32_8','AtomicStore32_16','AtomicRmwAdd32_8u','AtomicRmwXchg32_8u']:
   token='base.'+name+'(m, '
   if token in line:
    line=line.replace(token,f'base.Impact{name}(m, {fn}, {site}, ')
    manifest['sites'].append({'fn':fn,'line':site,'operation':name,'file':p.relative_to(out).as_posix()})
  if fn in selected or re.search(r'base.MemoryEA\(m, (?:24020808|24020811), 0, [12]\)',line):
   # Preserve the checked effective address and exact original pointer/dereference.
   kind='ordinary-load'
   if re.match(r'\s*\*\(',line):kind='ordinary-store'
   line=line.replace('base.MemoryEA(m, ',f'base.ImpactEA(m, {fn}, {site}, "{kind}", ')
   akind='atomic-load' if 'atomic.Load' in line else 'atomic-write-or-rmw'
   line=line.replace('base.AtomicEA(m, ',f'base.ImpactAtomicEA(m, {fn}, {site}, "{akind}", ')
   for name in ['AtomicLoad32_8u','AtomicLoad32_16u']:
    line=line.replace('base.'+name+'(m, ',f'base.Impact{name}(m, {fn}, {site}, ')
  lines[n]=line
 new=''.join(lines)
 if new!=old:
  p.write_text(new);manifest['changes'][p.relative_to(out).as_posix()]={'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()}
p=base/'base.go';old=p.read_text();needle='\t\tif atomic.CompareAndSwapUint32(word, cur, next) {\n\t\t\treturn lane\n\t\t}\n'
assert old.count(needle)==1
new=old.replace(needle,needle+'\t\tImpactRetry(m,ea,bits)\n');p.write_text(new)
manifest['changes'][p.relative_to(out).as_posix()]={'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()}
shutil.copyfile(Path(__file__).with_name('observer.go.txt'),base/'impact_observer.go')
p=out/'cmd/mariamem-host/main.go';old=p.read_text();new=old.replace('"bufio"','"bufio"\n "github.com/masahitojp/mariamem/internal/generatedgo/code/base"').replace('func run() error {','func run() error {\n defer base.ImpactDump()')
p.write_text(new);manifest['changes'][p.relative_to(out).as_posix()]={'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest()}
manifest['observer_sha256']=hashlib.sha256((base/'impact_observer.go').read_bytes()).hexdigest()
(out.parent/'instrumentation.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Instrumented',len(manifest['sites']),'writers; ordinary/atomic address checks in',len(selected),'selected functions')
