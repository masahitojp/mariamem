import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
root=Path.cwd().resolve();task=root.parent
sys.path.insert(0,str(root/'scripts'))
from generated_release import verify_build
from common import digest

guest=task/'temp/builder-build/generated-release'
origin=json.loads((guest/'guest.json').read_text())['source_commit']
verify_build(root,origin,guest)
results={'build_origin_source_commit':origin,'canonical_build_provenance':'PASS','negative_checks':{}}
negative=task/'temp/negative-build';negative.mkdir()
for name in ('guest.json','regeneration.json','mariamem.wasm'): shutil.copy2(guest/name,negative/name)
original=json.loads((guest/'guest.json').read_text())
for name in ('wrong-contract','one-build','experimental'):
    record=copy.deepcopy(original)
    if name=='wrong-contract':record['contract']='development-unqualified-v1'
    elif name=='one-build':record['repetitions']=record['repetitions'][:1]
    else:record['prepared_source']['experimental_patch']={'sha256':'0'*64}
    (negative/'guest.json').write_text(json.dumps(record))
    try: verify_build(root,origin,negative)
    except ValueError as exc: results['negative_checks'][name]={'result':'PASS','rejection':str(exc)}
    else: raise AssertionError('bad build accepted: '+name)
try: verify_build(root,subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),guest)
except ValueError as exc: results['negative_checks']['different-source-commit']={'result':'PASS','rejection':str(exc)}
else: raise AssertionError('build origin relabeled to another commit')
# Reconstruct the actual adopted guest source without network.
offline=task/'temp/offline-source';offline.mkdir()
for directory in ('scripts','guest'):
    shutil.copytree(root/directory,offline/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
(offline/'release').mkdir();shutil.copy2(root/'release/inputs.lock.json',offline/'release/inputs.lock.json')
(offline/'build/downloads').mkdir(parents=True)
for entry in json.loads((root/'release/inputs.lock.json').read_text())['inputs']:
    if entry['name'] in ('mariadb','lite4mariadb','libmariadb','wolfssl','pcre2','libfmt'):
        shutil.copy2(root/'build/downloads'/entry['file'],offline/'build/downloads'/entry['file'])
program="import sys,runpy,urllib.request\nsys.path.insert(0,'scripts')\ndef offline(*a,**k):raise RuntimeError('unexpected network')\nurllib.request.urlopen=offline\nrunpy.run_path('scripts/prepare_guest.py',run_name='__main__')"
subprocess.run([sys.executable,'-c',program],cwd=offline,check=True)
assert json.loads((offline/'build/prepared-source.json').read_text())==original['prepared_source']
results['offline_source_preparation']='PASS'
(task/'evidence/source-guards.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
