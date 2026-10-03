#!/usr/bin/env python3
"""Repeat retained-function attribution; diagnostic only, never rewrite guest."""
import argparse
import json
from pathlib import Path
import re
import subprocess
from common import ROOT, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('linked','guest','function-map','host','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    original=json.loads((ROOT/'release/generated-license-evidence.json').read_text())
    if digest(args.guest)!=original['guest_sha256'] or digest(args.linked)!=original['linked_sha256']:
        raise ValueError('not the canonical guest/link artifact')
    if digest(args.function_map)!=original['symbol_map_sha256']:
        raise ValueError('not the recorded canonical Binaryen function map')
    names={int(i):name for i,name in (line.split(':',1) for line in args.function_map.read_text().splitlines())}
    generated={}
    for path in (ROOT/'internal/generatedgo/code').rglob('*.go'):
        for m in re.finditer(r'^func Fn(\d+)\([^\n]+\{',path.read_text(),re.M):
            generated[int(m[1])]=path.relative_to(ROOT).as_posix()
    nm=subprocess.check_output(['go','tool','nm',str(args.host)],text=True)
    retained={int(m[1]) for line in nm.splitlines()
              if (m:=re.search(r'/code/p\d+\.Fn(\d+)(?:\.abi0)?$',line))}
    for row in original['retained_symbols'].values():
        matches={i:n for i,n in names.items() if re.search(row['pattern'],n)}
        native={i:n for i,n in matches.items() if i in retained and i in generated}
        if not native: raise ValueError('missing positive retained-function evidence')
        row.update(named_matches=len(matches),generated_definitions=sum(i in generated for i in matches),
                   host_named_definitions=len(native),examples=[{
                       'index':i,'symbol':n,'generated_file':generated[i],
                       'generated_function':'Fn'+str(i),'host_symbol_retained':True}
                       for i,n in native.items()][:3])
    buildinfo=subprocess.check_output(['go','version','-m',str(args.host)],text=True)
    revision=re.search(r'vcs.revision=([0-9a-f]{40})',buildinfo)
    if not revision or 'vcs.modified=false' not in buildinfo:
        raise ValueError('host lacks clean source identity')
    original['host_check']={'source_commit':revision[1],'sha256':digest(args.host),
                            'buildinfo':buildinfo.replace(str(args.host),'mariamem-host'),
                            'note':'Diagnostic attribution, not new release approval.'}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(original,indent=2)+'\n')
    print('Retained-library evidence reproduced:',args.output)


if __name__=='__main__':main()
