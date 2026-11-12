#!/usr/bin/env python3
"""Source-bound diagnostic only. Never edits generated input files."""
import hashlib, json, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parents[2]
HERE = pathlib.Path(__file__).resolve().parent
OUT = ROOT.parent / 'temp' / 'overlay'
OUT.mkdir(parents=True, exist_ok=True)
bindings = json.loads((HERE / 'bindings.json').read_text())
replacements = {
 'Fn16610': [('m.T0[v554].(func(*base.Module, int32, int32, int32))(m, v494, int32(0), v552)', 'if base.PendingProbe == nil { m.T0[v554].(func(*base.Module, int32, int32, int32))(m, v494, int32(0), v552) } else { base.PendingProbe(m, "timer_suppressed", v13, 0) }')],
 'Fn16595': [('base.AtomicStore32_8(m, l0, int32(408), v25)', 'base.AtomicStore32_8(m, l0, int32(408), v25)\n if base.PendingProbe != nil { base.PendingProbe(m, "pending_clear", l0, l1) }')],
 'Fn16597': [('if v83&v81 != 0 {', 'if v83&v81 != 0 {\n if base.PendingProbe != nil { base.PendingProbe(m, "pending_refusal", l0, 0) }')],
}
files = {}
for name,b in bindings.items():
 p = ROOT / b['path']
 text = files.setdefault(p, p.read_text())
 start = text.index('func '+name+'(')
 end = text.find('\nfunc ',start+1)
 if end < 0: end=len(text)
 body = text[start:end].rstrip()
 assert hashlib.sha256(body.encode()).hexdigest() == b['sha256'], name
 for old,new in replacements.get(name,[]):
  assert body.count(old)==1, (name, old)
  body=body.replace(old,new)
 files[p]=text[:start]+body+'\n'+text[end:]
replace={}
for p,text in files.items():
 if p.read_text()==text: continue
 dest=OUT/(p.parent.name+'_'+p.name)
 dest.write_text(text)
 replace[str(p)]=str(dest)
for src,dest in [('probe.go.txt','internal/generatedgo/code/base/pending_probe.go'),('control_test.go.txt','internal/generatedgo/pending_control_test.go')]:
 replace[str(ROOT/dest)]=str(HERE/src)
(OUT/'overlay.json').write_text(json.dumps({'Replace':replace},indent=2)+'\n')
print(OUT/'overlay.json')
