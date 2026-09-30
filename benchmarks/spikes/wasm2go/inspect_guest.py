#!/usr/bin/env python3
"""Inventory a hashed guest with wasm-tools; static counts are not execution counts."""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--guest',type=Path,required=True)
    p.add_argument('--wasm-tools',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(a.wasm_tools),'validate',str(a.guest)],check=True)
    wat=out/'guest.wat'
    subprocess.run([str(a.wasm_tools),'print',str(a.guest),'-o',str(wat)],check=True)
    text=wat.read_text();lines=text.splitlines()
    types={int(m[1]):m[2] for l in lines if (m:=re.match(r'^  \(type \(;([0-9]+);\) (.*)\)$',l))}
    calls=collections.Counter(int(m[1]) for l in lines if (m:=re.match(r'^\s+call ([0-9]+)(?:\s|$)',l)))
    opcodes=collections.Counter()
    for l in lines:
        tokens=l.strip().split()
        if tokens and re.match(r'^[a-z][a-z0-9_.]*$',tokens[0]):opcodes[tokens[0]]+=1
    imports=[]
    for l in lines:
        m=re.match(r'^  \(import "([^"]+)" "([^"]+)" (.*)\)$',l)
        if not m:continue
        i=dict(module=m[1],name=m[2])
        f=re.search(r'func \(;([0-9]+);\) \(type ([0-9]+)\)',m[3])
        if f:
            i.update(kind='function',function_index=int(f[1]),signature=types[int(f[2])],static_direct_calls=calls[int(f[1])])
        else:i.update(kind='memory',declaration=m[3])
        imports.append(i)
    sections={k:sum(l.startswith('  ('+k+' ') for l in lines) for k in ('func','global','table','tag','data','export','start')}
    sections['mutable_globals']=sum(l.startswith('  (global ') and '(mut ' in l for l in lines)
    relevant=('__wasm_call_ctors','__stack_pointer','__tls_base','__tls_size','__tls_align','__wasm_init_tls','wasi_thread_start','__wasm_signal','__wasm_sigaction','_start','l4m_open','l4m_close','l4m_query_v2','l4m_query','l4m_exec_multi','malloc','free')
    result=dict(guest_bytes=a.guest.stat().st_size,guest_sha256=hashlib.sha256(a.guest.read_bytes()).hexdigest(),
                wasm_tools_version=subprocess.check_output([str(a.wasm_tools),'--version'],text=True).strip(),
                sections=sections,imports=imports,import_namespaces=dict(collections.Counter(i['module'] for i in imports)),
                opcode_counts=dict(sorted(opcodes.items())),
                relevant_exports=[l.strip() for l in lines if l.startswith('  (export ') and any('"'+x+'"' in l for x in relevant)],
                notes=['Function count excludes imported functions.','Static direct-call count is not reachability or runtime frequency.','Imports may include linked but unused facilities.'])
    (out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('guest_bytes','guest_sha256','sections','import_namespaces')},indent=2))

if __name__=='__main__':main()
