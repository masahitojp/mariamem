#!/usr/bin/env python3
"""Compare unchanged release and isolated legacy guests after inspect_guest.py."""
import argparse
import json
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--before',type=Path,required=True)
p.add_argument('--after',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
before=json.loads(a.before.read_text())
after=json.loads(a.after.read_text())
if 'guest_inventory' in before:before=before['guest_inventory']
def imports(x):return {(i['module'],i['name']):i for i in x['imports']}
b=imports(before);n=imports(after)
changed=[]
for key in sorted(b.keys() & n.keys()):
    if b[key]['kind']!=n[key]['kind'] or b[key].get('signature')!=n[key].get('signature'):
        changed.append({'import':list(key),'before':b[key],'after':n[key]})
ops=('try_table','throw_ref','try','catch','catch_all','delegate','rethrow','throw',
     'memory.grow','memory.size','memory.init','data.drop','memory.copy','memory.fill')
result={
    'before_sha256':before['guest_sha256'],'after_sha256':after['guest_sha256'],
    'bytes':{'before':before['guest_bytes'],'after':after['guest_bytes']},
    'sections':{'before':before['sections'],'after':after['sections']},
    'opcodes':{k:{'before':before['opcode_counts'].get(k,0),'after':after['opcode_counts'].get(k,0)} for k in ops},
    'added_imports':[list(k) for k in sorted(n.keys()-b.keys())],
    'removed_imports':[list(k) for k in sorted(b.keys()-n.keys())],
    'changed_import_signatures':changed,
    'memory_declarations':{'before':[i['declaration'] for i in b.values() if i['kind']=='memory'],
                           'after':[i['declaration'] for i in n.values() if i['kind']=='memory']},
    'atomic_instruction_count':{'before':sum(v for k,v in before['opcode_counts'].items() if '.atomic.' in k or k.startswith('atomic.')),
                                'after':sum(v for k,v in after['opcode_counts'].items() if '.atomic.' in k or k.startswith('atomic.'))},
    'notes':['Static counts are not execution frequency or semantic equivalence.',
             'Full inventories retain SIMD, tables, tag exports and per-import signatures.']
}
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
