#!/usr/bin/env python3
"""Prove actual candidate build evidence and reject independently mutated records."""
import argparse
import copy
import json
import shutil
from pathlib import Path
import subprocess
import tempfile
from common import ROOT
from generated_release import verify_build
from git_identity import require_commit


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    require_commit(ROOT,commit)
    positive=verify_build(ROOT,commit)
    results=[]
    for name in ('contract','source','guest','linked','one-build','different-builds','experimental',
                 'source-file','overlay','toolchain','regen-source','regen-result','inventory','provenance','converter','patch','translation'):
        guest=copy.deepcopy(positive['guest']);regen=copy.deepcopy(positive['regeneration'])
        if name=='contract':guest['contract']='unqualified'
        elif name=='source':guest['source_commit']='0'*40
        elif name=='guest':guest['guest_sha256']='0'*64
        elif name=='linked':guest['repetitions']=[dict(guest['repetitions'][0],linked_sha256='0'*64)]*2
        elif name=='one-build':guest['repetitions']=guest['repetitions'][:1]
        elif name=='different-builds':guest['repetitions'][1]['guest_sha256']='0'*64
        elif name=='experimental':guest['prepared_source']['experimental_patch']={'sha256':'0'*64}
        elif name=='source-file':guest['prepared_source']['modified_files'][next(iter(guest['prepared_source']['modified_files']))]='0'*64
        elif name=='overlay':guest['prepared_source']['overlays'][next(iter(guest['prepared_source']['overlays']))]='0'*64
        elif name=='toolchain':guest['toolchain']['archives_sha256']['converter']='0'*64
        elif name=='regen-source':regen['source_commit']='0'*40
        elif name=='regen-result':regen['result']='FAIL'
        elif name=='inventory':regen['generated_inventory'][next(iter(regen['generated_inventory']))]='0'*64
        elif name=='provenance':regen['provenance_sha256']='0'*64
        elif name=='converter':regen['raw_translation']['converter_commit']='0'*40
        elif name=='patch':regen['raw_translation']['patches_sha256'][next(iter(regen['raw_translation']['patches_sha256']))]='0'*64
        elif name=='translation':regen['raw_translation']['files_sha256'][next(iter(regen['raw_translation']['files_sha256']))]='0'*64
        with tempfile.TemporaryDirectory(prefix='prepared-build-negative-') as tmp:
            directory=Path(tmp)
            (directory/'guest.json').write_text(json.dumps(guest))
            (directory/'regeneration.json').write_text(json.dumps(regen))
            shutil.copyfile(ROOT/'build/generated-release/mariamem.wasm',directory/'mariamem.wasm')
            try:
                verify_build(ROOT,commit,directory)
            except ValueError as e:
                results.append({'mutation':name,'rejected':True,'error':str(e)})
            else:
                raise AssertionError('build guard accepted mutation: '+name)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({'source_commit':commit,'positive':'PASS','negative':results,'result':'PASS'},indent=2)+'\n')
    print('PASS: actual canonical build and17 independently rejected evidence mutations')


if __name__=='__main__':main()
